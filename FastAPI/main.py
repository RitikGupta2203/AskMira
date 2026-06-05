# src/main.py
import os
import openai
import numpy as np
from pinecone import Pinecone
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from dotenv import load_dotenv

from FastAPI.jwtauth import router as auth_router, get_current_user

# load .env at project root
load_dotenv()

# creating the server
app = FastAPI(title="AskMira Auth Service")

# CORS – allow your Streamlit front end
origins = [
    os.getenv("FRONTEND_URL", "http://localhost:8501"),
    os.getenv("FRONTEND_URL", "http://127.0.0.1:8501"),
]

# Allow frontend to communicate with backend (CORS setup)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # allow login cookies / tokens
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount the auth router under /auth
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# for FastAPI’s OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")



# test route to check backend is running
@app.get("/", tags=["root"])
async def read_root():
    return {"message": "Welcome to AskMira Auth Service"}


# ─── RAG configuration (env-driven, defaults preserve current behavior) ──────
EMBEDDING_MODEL      = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
EMBEDDING_DIM        = int(os.getenv("EMBEDDING_DIM", "1024"))
CHAT_MODEL           = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
RAG_TOP_K            = int(os.getenv("RAG_TOP_K", "5"))
CHAT_MAX_TOKENS      = int(os.getenv("CHAT_MAX_TOKENS", "8000"))
CHAT_TEMPERATURE     = float(os.getenv("CHAT_TEMPERATURE", "0.5"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))

# ─── RAG client initialization ───────────────────────────────────────────────
openai.api_key = os.getenv("OPENAI_API_KEY")
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX"))


class ChatRequest(BaseModel):
    query: str


def _create_embedding(text: str):
    resp = openai.Embedding.create(model=EMBEDDING_MODEL, input=text)
    full = resp["data"][0]["embedding"]
    resized = full[:EMBEDDING_DIM]
    norm = float(np.linalg.norm(resized))
    return [float(v / norm) for v in resized]


@app.post("/rag/chat", tags=["rag"])
def rag_chat(req: ChatRequest, current_user=Depends(get_current_user)):
    """JWT-gated RAG endpoint: embeds the query, searches Pinecone, calls GPT-4o."""
    try:
        qvec = _create_embedding(req.query)
        results = index.query(vector=qvec, top_k=RAG_TOP_K, include_metadata=True)

        # Drop any match whose cosine score is below the threshold
        results.matches = [m for m in results.matches if m.score >= SIMILARITY_THRESHOLD]

        # No chunks passed the relevance bar → refuse without calling the LLM
        if not results.matches:
            return {
                "response": (
                    "I can only answer questions about international academic credentials "
                    "and Northeastern's FCE policies. Your question doesn't appear to match "
                    "anything in my knowledge base."
                ),
                "sources": [],
                "user": current_user["username"],
            }

        sources = [m.metadata.get("source", "Unknown") for m in results.matches]
        context = "\n".join(
            f"[Source: {m.metadata.get('source', 'Unknown')}]\n{m.metadata.get('text', '')}\n"
            for m in results.matches
        )
        system_prompt = (
            "You are AskMira, an expert in global education and credit evaluation. "
            "Use only the provided context to answer the user's question. "
            "If the answer is not in the context, say you don't know. "
            "Always cite your sources."
        )
        completion = openai.ChatCompletion.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {req.query}"},
            ],
            max_tokens=CHAT_MAX_TOKENS,
            temperature=CHAT_TEMPERATURE,
        )
        return {
            "response": completion.choices[0].message["content"].strip(),
            "sources": sources,
            "user": current_user["username"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG error: {e}")
