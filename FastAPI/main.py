# src/main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv

from jwtauth import router as auth_router

# load .env at project root
load_dotenv()

app = FastAPI(title="AskMira Auth Service")

# CORS – allow your Streamlit front end
origins = [
    os.getenv("FRONTEND_URL", "http://localhost:8501"),
    os.getenv("FRONTEND_URL", "http://127.0.0.1:8501"),
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount the auth router under /auth
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# for FastAPI’s OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@app.get("/", tags=["root"])
async def read_root():
    return {"message": "Welcome to AskMira Auth Service"}
