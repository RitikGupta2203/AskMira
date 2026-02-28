# src/jwtauth.py
import os
import hmac
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
import snowflake.connector
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from dotenv import load_dotenv

# load vars if this file is run stand‑alone
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

router = APIRouter()
security = HTTPBearer()


def get_snowflake_conn():
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )


def hash_password(password: str) -> str:
    return hmac.new(SECRET_KEY.encode(), msg=password.encode(), digestmod=hashlib.sha256).hexdigest()


def create_jwt_token(data: dict) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=60)
    payload = {"exp": exp, **data}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_jwt_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_user_from_db(username: str):
    conn = get_snowflake_conn()
    cur = conn.cursor(snowflake.connector.DictCursor)
    cur.execute("SELECT USERNAME, EMAIL, HASHED_PASSWORD FROM USERS WHERE USERNAME = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_jwt_token(credentials.credentials)
    username = payload.get("username")
    user = get_user_from_db(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# Pydantic models
class UserRegister(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserRegister):
    conn = get_snowflake_conn()
    cur = conn.cursor()
    # ensure table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS USERS (
            USERNAME STRING PRIMARY KEY,
            EMAIL STRING,
            HASHED_PASSWORD STRING
        )
    """)
    # check duplicate
    cur.execute("SELECT 1 FROM USERS WHERE USERNAME = %s", (user.username,))
    if cur.fetchone():
        cur.close(); conn.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    pw_hash = hash_password(user.password)
    cur.execute(
        "INSERT INTO USERS (USERNAME, EMAIL, HASHED_PASSWORD) VALUES (%s, %s, %s)",
        (user.username, user.email, pw_hash)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "User registered successfully"}


@router.post("/login")
def login(user: UserLogin):
    db_user = get_user_from_db(user.username)
    if not db_user or db_user["HASHED_PASSWORD"] != hash_password(user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_jwt_token({"username": user.username})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/protected")
def protected_route(current_user=Depends(get_current_user)):
    return {"message": f"Hello, {current_user['USERNAME']}!"}
