from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import hash_password, verify_password
from database.session import get_db
from dependencies.auth import get_current_user
from models.user import User
from schemas.user import (
    CurrentUserResponse,
    MemberUpdate,
    PasswordChange,
    ProfileUpdate,
    UserCreate,
    UserResponse,
)
from services.user_service import UserService

users_router = APIRouter(prefix="/users", tags=["Users"])


def require_admin(current_user: User):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


@users_router.post("/create_user", response_model=UserResponse)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    try:
        return UserService.create_user(
            db=db,
            email=payload.email,
            name=payload.name,
            password=payload.password,
            role=payload.role,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@users_router.get("/get_all_users", response_model=list[UserResponse])
def get_all_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user)
    return UserService.get_all_users(db, current_user.enterprise_id)


@users_router.get("/get_user/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    temp_var_db_response = UserService.get_user_by_id(db, user_id, current_user.enterprise_id)
    if not temp_var_db_response:
        raise HTTPException(404, "User not found")

    return temp_var_db_response


@users_router.delete("/delete_user/{user_id}")
def delete_user(
    user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    require_admin(current_user)
    try:
        deleted = UserService.delete_user(db, user_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    if not deleted:
        raise HTTPException(404, "User not found")

    return {"message": "deleted"}


@users_router.get("/me", response_model=CurrentUserResponse)
def get_current_profile(current_user: User = Depends(get_current_user)):
    return current_user


@users_router.patch("/me", response_model=CurrentUserResponse)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.name = payload.name
    if "profile_photo" in payload.model_fields_set:
        current_user.profile_photo = payload.profile_photo
    db.commit()
    db.refresh(current_user)
    return current_user


@users_router.post("/me/password")
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    original_hash = current_user.hashed_password
    changed = db.execute(
        update(User)
        .where(
            User.id == current_user.id,
            User.is_active.is_(True),
            User.hashed_password == original_hash,
        )
        .values(hashed_password=hash_password(payload.password), reset_requested_at=None)
    )
    if not changed.rowcount:
        db.rollback()
        raise HTTPException(409, "Account changed. Sign in again before changing your password.")
    db.commit()
    return {"message": "Password changed. Sign in again."}


@users_router.patch("/{user_id}", response_model=UserResponse)
def edit_member(
    user_id: int,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        enterprise_id = UserService._lock_and_authorize(db, current_user)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None
    target = UserService.get_user_by_id(db, user_id, enterprise_id)
    if target is None:
        raise HTTPException(404, "Member not found")
    target.name = payload.name
    target.email = str(payload.email)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account already uses this email") from None
    db.refresh(target)
    return target
