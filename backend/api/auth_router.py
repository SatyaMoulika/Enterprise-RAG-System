from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.session import get_db
from schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from services.auth_service import AuthService

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        result = AuthService.register_user(
            db=db,
            enterprise_name=payload.enterprise_name,
            email=payload.email,
            password=payload.password,
        )

        return {
            "message": "User registered successfully",
            "user_id": result["user"].id,
            "email": result["user"].email,
            "access_token": result["access_token"],
            "token_type": result["token_type"],
        }

    except ValueError as e:
        print("REGISTER ERROR:", str(e))
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