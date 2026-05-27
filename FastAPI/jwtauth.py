# src/jwtauth.py
import os
import jwt
import hmac
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials   # For reading JWT token from request headers
from pydantic import BaseModel
from dotenv import load_dotenv

# PostgreSQL connection
import psycopg2
from psycopg2.extras import RealDictCursor



# load vars if this file is run stand‑alone
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
JWT_EXPIRY_MINUTES = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))


router = APIRouter()
security = HTTPBearer() # Extracts token from "Authorization: Bearer <token>"


# Connects to PostgreSQL database
def get_db_conn():
    '''
    Creates a new PostgreSQL database connection.
    Each request opens and closes its own connection (simple approach).
    
    '''
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        dbname=os.getenv("POSTGRES_DB"),
    )

 # PASSWORD HASHING
def hash_password(password: str) -> str:
    '''
    Hashes plain-text password using HMAC-SHA256.
    '''

    return hmac.new(SECRET_KEY.encode(), msg=password.encode(), digestmod=hashlib.sha256).hexdigest()

# JWT CREATION
def create_jwt_token(data: dict) -> str:
    '''
    Creates a JWT token with expiration time.
    Used after successful login.
    
    '''
    exp = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES)
    payload = {"exp": exp, **data}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


# JWT VALIDATION
def decode_jwt_token(token: str) -> dict:
    '''
    Decodes and verifies JWT token.

    Handles:
    - expired tokens
    - invalid tokens
    
    '''
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_user_from_db(username: str):
    '''
    Fetches a user record from PostgreSQL by username.
    Returns None if user does not exist.
    '''
    conn = get_db_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT username, email, hashed_password FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

# AUTH DEPENDENCY (JWT CHECK)
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    '''
     Extracts and validates user from JWT token.

    Flow:
    1. Extract token from request header
    2. Decode JWT
    3. Fetch user from database
    
    '''
    payload = decode_jwt_token(credentials.credentials)
    username = payload.get("username")
    user = get_user_from_db(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# PYDANTIC MODELS
class UserRegister(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


# REGISTER ENDPOINT
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserRegister):
    '''
    Creates a new user account.

    Steps:
    - Ensure users table exists
    - Check if username already exists
    - Hash password
    - Store user in database

    '''
    conn = get_db_conn()
    cur = conn.cursor()
    # ensure table exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username VARCHAR(255) PRIMARY KEY,
            email VARCHAR(255),
            hashed_password VARCHAR(255)
        )
    """)
    # check duplicate
    cur.execute("SELECT 1 FROM users WHERE username = %s", (user.username,))
    if cur.fetchone():
        cur.close(); conn.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")

    pw_hash = hash_password(user.password)
    cur.execute(
        "INSERT INTO users (username, email, hashed_password) VALUES (%s, %s, %s)",
        (user.username, user.email, pw_hash)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"message": "User registered successfully"}



# LOGIN ENDPOINT
@router.post("/login")
def login(user: UserLogin):
    '''
    Authenticates user and returns JWT token.

    Steps:
    - Fetch user from DB
    - Verify password hash
    - Generate JWT token
    
    '''

    db_user = get_user_from_db(user.username)
    if not db_user or db_user["hashed_password"] != hash_password(user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_jwt_token({"username": user.username})
    return {"access_token": token, "token_type": "bearer"}


# PROTECTED ENDPOINT
@router.get("/protected")
def protected_route(current_user=Depends(get_current_user)):
    '''
    Only accessible if valid JWT token is provided. 
    '''
    
    return {"message": f"Hello, {current_user['username']}!"}
