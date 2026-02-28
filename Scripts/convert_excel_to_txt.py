#!/usr/bin/env python3
"""
convert_excel_to_txt.py - Convert Excel file to text and update Pinecone index

This script:
1. Downloads an Excel file from S3
2. Converts it to text format
3. Uploads the text version to S3
4. Updates the Pinecone index with the new document
"""

import os
import boto3
import pandas as pd
import numpy as np
import openai
import tempfile
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Load environment variables
load_dotenv()

# Initialize clients
s3 = boto3.client(
    's3',
    region_name=os.getenv('AWS_REGION'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

openai.api_key = os.getenv('OPENAI_API_KEY')
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
index_name = os.getenv('PINECONE_INDEX')
index = pc.Index(index_name)

# Text splitter setup
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
)

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

def download_from_s3(bucket, key, local_path):
    """Download a file from S3"""
    print(f"Downloading s3://{bucket}/{key} to {local_path}")
    try:
        s3.download_file(bucket, key, local_path)
        print(f"Successfully downloaded from S3")
        return True
    except Exception as e:
        print(f"Error downloading from S3: {e}")
        return False

def upload_to_s3(content, bucket, key):
    """Upload content as a file to S3"""
    print(f"Uploading content to s3://{bucket}/{key}")
    
    try:
        s3.put_object(Body=content, Bucket=bucket, Key=key)
        print(f"Successfully uploaded to S3: s3://{bucket}/{key}")
        return True
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        return False

def excel_to_text(excel_path):
    """Convert Excel file to formatted text"""
    try:
        # Read all sheets from the Excel file
        xl = pd.ExcelFile(excel_path)
        sheet_names = xl.sheet_names
        
        text_content = []
        text_content.append(f"FCE EQUIVALENCY DOCUMENT")
        text_content.append("=" * 50)
        
        # Process each sheet
        for sheet in sheet_names:
            df = pd.read_excel(excel_path, sheet_name=sheet)
            
            text_content.append(f"\nSHEET: {sheet}")
            text_content.append("-" * 50)
            
            # Convert column names to string and handle NaN values
            columns = [str(col) for col in df.columns]
            text_content.append("COLUMNS: " + " | ".join(columns))
            text_content.append("-" * 50)
            
            # Convert each row to text
            for index, row in df.iterrows():
                row_text = []
                for col in df.columns:
                    value = row[col]
                    # Convert NaN to empty string
                    if pd.isna(value):
                        value = ""
                    row_text.append(f"{col}: {value}")
                text_content.append(" | ".join(row_text))
            
        return "\n".join(text_content)
    except Exception as e:
        print(f"Error converting Excel to text: {e}")
        return None

def process_and_index_text(text_content, s3_key):
    """Process text content and add it to Pinecone"""
    # Extract metadata
    metadata = {
        'source': s3_key,
        'document_type': 'regulation',
    }
    
    # Split the document into chunks
    chunks = text_splitter.split_text(text_content)
    print(f"Document split into {len(chunks)} chunks")
    
    # Create vectors for each chunk
    vectors_to_upsert = []
    
    for i, chunk in enumerate(chunks):
        # Generate a unique ID for this chunk
        chunk_id = f"{s3_key.replace('/', '_')}_{i}"
        
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
            
        except Exception as e:
            print(f"Error embedding chunk {i}: {e}")
    
    # Upsert vectors to Pinecone
    if vectors_to_upsert:
        try:
            index.upsert(vectors=vectors_to_upsert)
            print(f"Successfully added {len(vectors_to_upsert)} vectors to Pinecone")
            return True
        except Exception as e:
            print(f"Error upserting to Pinecone: {e}")
            return False
    else:
        print("No vectors to upsert")
        return False

def main():
    # Set your bucket and file paths
    bucket = os.getenv('S3_BUCKET')
    excel_key = "FCE Regulations/FCE Equivalency.xlsx"
    text_key = "FCE Regulations TXT/FCE Equivalency.txt"
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # Download the Excel file
        if not download_from_s3(bucket, excel_key, temp_path):
            print("Failed to download Excel file. Exiting.")
            return
        
        # Convert to text
        text_content = excel_to_text(temp_path)
        if text_content is None:
            print("Failed to convert Excel to text. Exiting.")
            return
        
        # Upload text to S3
        if not upload_to_s3(text_content, bucket, text_key):
            print("Failed to upload text file. Exiting.")
            return
        
        # Process and index the text
        process_and_index_text(text_content, text_key)
        
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)

if __name__ == "__main__":
    main()