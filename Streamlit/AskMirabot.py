import streamlit as st
import requests
import os
from dotenv import load_dotenv
import openai
from pinecone import Pinecone
import numpy as np

# Load environment variables
# Load environment variables
load_dotenv()
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://fastapi:8000")
CHAT_URL = f"{FASTAPI_URL}/chat"

# Initialize OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX")
index = pc.Index(index_name)

def create_embedding(text):
    """Create an embedding using OpenAI's API and resize to 1024 dimensions"""
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=text
    )
    
    # Get the full 1536-dimension vector
    full_vector = response['data'][0]['embedding']
    
    # Resize to 1024 dimensions by taking the first 1024 values
    resized_vector = full_vector[:1024]
    
    # Normalize the vector
    norm = np.linalg.norm(resized_vector)
    normalized_vector = [float(val/norm) for val in resized_vector]
    
    return normalized_vector

def query_pinecone(query, top_k=5):
    """Query Pinecone index and return top matches"""
    # Create query embedding
    query_vector = create_embedding(query)
    
    # Query Pinecone
    results = index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True
    )
    
    return results

def format_context(results):
    """Format retrieved context into a prompt-friendly format"""
    context = []
    
    for match in results.matches:
        # Extract relevant metadata
        metadata = match.metadata
        source = metadata.get('source', 'Unknown source')
        text = metadata.get('text', '')
        
        # Format this piece of context
        formatted = f"[Source: {source}]\n{text}\n"
        context.append(formatted)
    
    # Join all pieces into one string
    return "\n".join(context)

def get_rag_response(query):
    """Get a response using RAG (Retrieval Augmented Generation)"""
    try:
        # Step 1: Retrieve relevant context from Pinecone
        st.write("🔍 Searching knowledge base...")
        results = query_pinecone(query)
        
        # Step 2: Format context
        context = format_context(results)
        
        # Step 3: Create prompt with context
        system_prompt = """You are AskMira, an expert in global education and credit evaluation. 
Your purpose is to provide accurate information about international education systems, credentials, 
and credit evaluation practices.

Use only the provided context to answer the user's question. If the answer is not in the context,
say that you don't know and suggest what information might be needed.

Always cite your sources when answering."""
        
        # Step 4: Call OpenAI for completion - using gpt-4o
        st.write("🤔 Thinking...")
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # Updated to the latest model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Here is the context to use for answering the question:\n\n{context}\n\nQuestion: {query}"}
            ],
            max_tokens=8000,
            temperature=0.5,
        )
        
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return f"⚠️ Error generating response: {e}"

def legacy_get_bot_response(prompt: str) -> str:
    """Legacy API-based response method"""
    try:
        r = requests.post(CHAT_URL, json={"prompt": prompt}, timeout=15)
        r.raise_for_status()
        return r.json().get("response", "")
    except Exception as e:
        return f"⚠️ Error: {e}"

def show_bot():
    # Decorative header
    st.markdown(
        """
        <div style="text-align:center;">
          <div style="
            font-family:'Cinzel Decorative', serif;
            font-size:3rem;
            color:#2E86AB;
          ">
            AskMira Bot
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Add a toggle for RAG mode
    rag_mode = st.sidebar.checkbox("Use RAG Mode (Knowledge Base)", value=True)
    
    # Display chat history
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])
    
    # Prompt
    user_input = st.chat_input("Type your question here…")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.chat_message("user").write(user_input)
        
        with st.chat_message("assistant"):
            if rag_mode:
                # Use the RAG system
                resp = get_rag_response(user_input)
            else:
                # Use the legacy API-based system
                resp = legacy_get_bot_response(user_input)
            
            st.write(resp)
            st.session_state.messages.append({"role": "assistant", "content": resp})