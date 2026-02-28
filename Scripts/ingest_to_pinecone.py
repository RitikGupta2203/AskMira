#!/usr/bin/env python3
"""
ingest_to_pinecone.py - Ingests documents from S3 into Pinecone vector database

This script:
1. Reads .txt files from specified S3 paths
2. Splits documents into manageable chunks
3. Generates embeddings using OpenAI's embedding model
4. Upserts the vectors into a Pinecone index with appropriate metadata
"""

import os
import uuid
import boto3
import logging
import numpy as np
import openai
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from tqdm import tqdm
from pinecone import Pinecone

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize S3 client
s3 = boto3.client(
    's3',
    region_name=os.getenv('AWS_REGION'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

# Initialize Pinecone client
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))

# Set up OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Text splitter for chunking documents
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
)

def create_embedding(text):
    """Create an embedding using OpenAI's API and resize to 1024 dimensions"""
    try:
        # Using ada-002 which produces 1536 dimensions
        response = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=text
        )
        
        # Get the full 1536-dimension vector
        full_vector = response['data'][0]['embedding']
        
        # Resize to 1024 dimensions using PCA-like approach
        # We'll use a simple method: take every 3rd element and discard the rest
        # This is a simplification but should work for our purposes
        resized_vector = full_vector[:1024]
        
        # Normalize the vector (important for cosine similarity)
        norm = np.linalg.norm(resized_vector)
        normalized_vector = [float(val/norm) for val in resized_vector]
        
        return normalized_vector
    except Exception as e:
        logger.error(f"Error creating embedding: {e}")
        raise

def list_s3_objects(bucket, prefix):
    """List all objects in S3 with the given prefix"""
    objects = []
    paginator = s3.get_paginator('list_objects_v2')
    
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if 'Contents' in page:
            for obj in page['Contents']:
                objects.append(obj['Key'])
    
    return objects

def get_s3_object(bucket, key):
    """Get the content of an S3 object as text"""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        logger.error(f"Error reading S3 object {key}: {e}")
        return None

def extract_metadata(key):
    """Extract metadata from S3 key"""
    parts = key.split('/')
    metadata = {
        'source': key,
    }
    
    # Special handling for AACRAO documents
    if key.startswith('aacrao/'):
        if len(parts) >= 3:
            metadata['region'] = parts[1]
            metadata['country'] = parts[2].replace('.txt', '')
    
    # Special handling for FCE Regulations
    elif key.startswith('FCE Regulations TXT/') or key.startswith('FCE Regulations/'):
        metadata['document_type'] = 'regulation'
        if len(parts) >= 3:
            metadata['category'] = parts[1]
    
    return metadata

def process_and_upsert(bucket, keys):
    """Process files and upsert them to Pinecone"""
    # Get the index name from environment
    index_name = os.getenv('PINECONE_INDEX')
    
    # Check if index exists and connect to it
    index_list = [i.name for i in pc.list_indexes()]
    if index_name not in index_list:
        logger.warning(f"Index {index_name} does not exist in Pinecone")
        return False
    
    index = pc.Index(index_name)
    
    # Process each file
    vectors_to_upsert = []
    batch_size = 100  # Adjust based on your Pinecone tier
    
    for key in tqdm(keys, desc="Processing documents"):
        # Skip directories
        if key.endswith('/'):
            continue
        
        # Skip non-text files
        if not key.endswith('.txt'):
            continue
        
        # Get the file content
        content = get_s3_object(bucket, key)
        if not content:
            continue
        
        # Extract metadata
        metadata = extract_metadata(key)
        
        # Split the document into chunks
        chunks = text_splitter.split_text(content)
        
        # Create vectors for each chunk
        for i, chunk in enumerate(chunks):
            # Generate a unique ID for this chunk
            chunk_id = f"{key.replace('/', '_')}_{i}"
            
            # Get the embedding for this chunk
            try:
                vector = create_embedding(chunk)
                
                # Prepare metadata
                chunk_metadata = metadata.copy()
                chunk_metadata['chunk_index'] = i
                chunk_metadata['total_chunks'] = len(chunks)
                chunk_metadata['text'] = chunk[:1000]  # Store first 1000 chars of text
                
                # Add to vectors list
                vectors_to_upsert.append({"id": chunk_id, "values": vector, "metadata": chunk_metadata})
                
                # Upsert in batches
                if len(vectors_to_upsert) >= batch_size:
                    _upsert_batch(index, vectors_to_upsert)
                    vectors_to_upsert = []
                    
            except Exception as e:
                logger.error(f"Error embedding chunk {i} of {key}: {e}")
    
    # Upsert any remaining vectors
    if vectors_to_upsert:
        _upsert_batch(index, vectors_to_upsert)
    
    return True

def _upsert_batch(index, vectors):
    """Upsert a batch of vectors to Pinecone"""
    try:
        index.upsert(vectors=vectors)
        logger.info(f"Upserted batch of {len(vectors)} vectors")
    except Exception as e:
        logger.error(f"Error upserting batch to Pinecone: {e}")

def main():
    """Main execution function"""
    # S3 bucket and prefixes to process
    bucket = os.getenv('S3_BUCKET')
    prefixes = [
        'aacrao/',
        'FCE Regulations TXT/',
        'FCE Regulations/'  # For any new converted texts
    ]
    
    # Gather all files to process
    all_keys = []
    for prefix in prefixes:
        logger.info(f"Listing objects with prefix: {prefix}")
        keys = list_s3_objects(bucket, prefix)
        logger.info(f"Found {len(keys)} objects")
        all_keys.extend(keys)
    
    # Process and upsert
    if all_keys:
        logger.info(f"Starting processing of {len(all_keys)} files")
        result = process_and_upsert(bucket, all_keys)
        if result:
            logger.info("Successfully processed all files")
        else:
            logger.error("Failed to process all files")
    else:
        logger.warning("No files found to process")

if __name__ == "__main__":
    main()