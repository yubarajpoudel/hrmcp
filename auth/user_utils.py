from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Depends, HTTPException, status
from typing import Union, Annotated, Optional
from datetime import datetime, timedelta
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher
from auth.db_handler import DatabaseHandler
import jwt
from core.env.env_utils import get_settings

settings = get_settings()

password_hash = PasswordHash([Argon2Hasher(), BcryptHasher()])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

class User(BaseModel):
    id: Union[str, None] = None  # MongoDB _id field
    username: str
    full_name: Union[str, None] = None
    hashed_password: str
    email: Union[str, None] = None
    role: Union[str, None] = None
    disabled: Union[bool, None] = False

class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = "user"

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Union[str, None] = None
    user_id: Union[str, None] = None


def generate_hashed_password(plain_password: str) -> str:
    if not plain_password or not isinstance(plain_password, str):
        raise ValueError("Password must be a non-empty string.")
    return password_hash.hash(plain_password)

def verify_password(plain_password, hashed_password):
    try:
        return password_hash.verify(plain_password, hashed_password)
    except Exception as e:
        print(f"Verification failed: {e}")
        return False

async def get_user(username: str) -> Optional[User]:
    user_dict = await DatabaseHandler.get_user(username)
    if user_dict:
        # Map MongoDB's _id to id field for Pydantic model
        if "_id" in user_dict:
            user_dict["id"] = user_dict.pop("_id")
        return User(**user_dict)
    return None

async def authenticate_user(username: str, password: str):
    user = await get_user(username)
    print(f"authenticate_user :: user: {user}")
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user 
    
async def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials"
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        if username is None or user_id is None:
            raise credentials_exception
        token_data = TokenData(username=username, user_id=user_id)
    except Exception as e:
        raise credentials_exception
    user = await get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

