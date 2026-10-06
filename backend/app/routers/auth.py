from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas
from ..config import settings
from ..db import get_db
from ..models import User
from ..security import create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": create_token(user), "user": user}


@router.post("/register", response_model=schemas.TokenOut)
def register(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email already registered")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password), role="user")
    db.add(user)
    db.commit()
    return {"access_token": create_token(user), "user": user}


@router.post("/google", response_model=schemas.TokenOut)
def google(body: schemas.GoogleIn, db: Session = Depends(get_db)):
    if not settings.google_client_id:
        raise HTTPException(501, "Google SSO is not configured (set GOOGLE_CLIENT_ID)")
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    try:
        info = id_token.verify_oauth2_token(body.id_token, g_requests.Request(), settings.google_client_id)
    except ValueError:
        raise HTTPException(401, "Invalid Google token")
    if not info.get("email_verified"):
        raise HTTPException(401, "Google email not verified")
    email = info["email"].lower()
    user = db.query(User).filter((User.google_sub == info["sub"]) | (User.email == email)).first()
    if not user:
        user = User(email=email, name=info.get("name", email), google_sub=info["sub"], role="user")
        db.add(user)
    elif not user.google_sub:
        user.google_sub = info["sub"]  # link existing password account
    db.commit()
    return {"access_token": create_token(user), "user": user}


@router.get("/config")
def auth_config():
    return {"google_client_id": settings.google_client_id}


@router.get("/me", response_model=schemas.UserOut)
def me(user: User = Depends(current_user)):
    return user
