from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.session import get_db
from services.user_service import UserService
from schemas.user import UserCreate, UserResponse, CurrentUserResponse
from dependencies.auth import get_current_user
from models.user import User

users_router = APIRouter(prefix="/users", tags=["Users"])

def require_admin(current_user: User):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


@users_router.post("/create_user", response_model=UserResponse)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)

    return UserService.create_user(
        db=db,
        email=payload.email,
        password=payload.password,
        role=payload.role,
        current_user=current_user
    )


@users_router.get("/get_all_users", response_model=list[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    return UserService.get_all_users(db, current_user.enterprise_id)


@users_router.get("/get_user/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    temp_var_db_response = UserService.get_user_by_id(db, user_id, current_user.enterprise_id)
    if not temp_var_db_response:
        raise HTTPException(404, "User not found")

    return temp_var_db_response


@users_router.delete("/delete_user/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user)
    temp_var_db_response = UserService.delete_user(db, user_id, current_user.enterprise_id)
    if not temp_var_db_response:
        raise HTTPException(404, "User not found")

    return {"message": "deleted"}


@users_router.get("/me", response_model=CurrentUserResponse)
def get_current_profile(current_user: User = Depends(get_current_user)):
    return current_user