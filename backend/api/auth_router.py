from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.config import settings
from database.session import get_db
from schemas.auth import (
    DirectResetPasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from services.auth_service import AuthService
from services.password_reset_service import PasswordResetService

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    return {
        "message": PasswordResetService.request(db, str(payload.email), background_tasks.add_task)
    }


@auth_router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        PasswordResetService.reset(db, payload.token, payload.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return {"message": "Your password has been updated. Sign in with your new password."}


@auth_router.get("/config")
def authentication_config():
    return {
        "registration_enabled": settings.PUBLIC_REGISTRATION_ENABLED,
        "direct_password_reset_enabled": PasswordResetService.direct_enabled(),
    }


@auth_router.post("/reset-password/direct")
def reset_password_direct(payload: DirectResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        PasswordResetService.reset_direct(db, str(payload.email), payload.password)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    return {"message": "Your password has been updated. Sign in with your new password."}


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if not settings.PUBLIC_REGISTRATION_ENABLED:
        raise HTTPException(
            403, "Workspace registration is disabled. Contact your administrator for an account."
        )
    try:
        result = AuthService.register_user(
            db=db,
            enterprise_name=payload.enterprise_name,
            email=payload.email,
            password=payload.password,
            name=payload.name,
        )

        return {
            "message": "User registered successfully",
            "user_id": result["user"].id,
            "email": result["user"].email,
            "access_token": result["access_token"],
            "token_type": result["token_type"],
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@auth_router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        token_details = AuthService.login_user(
            db=db,
            email=payload.email,
            password=payload.password,
        )

        return TokenResponse(**token_details)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
