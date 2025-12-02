from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Depends, HTTPException, status
from typing import Union, Annotated
from datetime import datetime, timedelta
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

password_hash = PasswordHash([Argon2Hasher(), BcryptHasher()])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

import jwt

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

fake_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "role": "admin",
        "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$eqqkynvwEBqajmgERFcOEA$euvR/vJE4lfVxQnFtKTjskFTVQRGnPZPDUBtnLPQNMc",
        "disabled": False,
    }
}

class User(BaseModel):
    username: str
    full_name: Union[str, None] = None
    hashed_password: str
    email: Union[str, None] = None
    role: Union[str, None] = None
    disabled: Union[bool, None] = False

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Union[str, None] = None


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

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return User(**user_dict)

def authenticate_user(username: str, password: str):
    user = get_user(fake_db, username)
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
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except Exception as e:
        raise credentials_exception
    user = get_user(fake_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

