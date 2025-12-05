from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from fastapi import Depends, HTTPException, Form, FastAPI, APIRouter
from auth.user_utils import *
from auth.db_handler import DatabaseHandler

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

@router.post("/register")
async def register_user(user_data: UserCreate):
    """
    Register a new user
    
    Args:
        user_data: User registration data (username, password, email, full_name, role)
    
    Returns:
        Success message with username
    """
    try:
        # Hash the password
        hashed_password = generate_hashed_password(user_data.password)
        
        # Prepare user document for database
        user_doc = {
            "username": user_data.username,
            "hashed_password": hashed_password,
            "email": user_data.email,
            "full_name": user_data.full_name,
            "role": user_data.role,
            "disabled": False
        }
        
        # Create user in database
        created_user = await DatabaseHandler.create_user(user_doc)
        
        return {
            "message": "User created successfully",
            "username": created_user["username"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

@router.post("/token")
def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    print("username: " + form_data.username + " password: " + form_data.password)
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    print(f"user: {user}")
    access_token = create_access_token(data={"sub": user.username, "user_id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=User)
def read_users_me(current_user: Annotated[User, Depends(get_current_active_user)]):
    return current_user
