#!/usr/bin/env python3
"""
scripts/convert_s3_docs_to_txt.py

Downloads every PDF, DOCX or XLSX under a given S3 prefix,
extracts plain-text via pdfplumber / docx2txt / pandas,
then re-uploads a .txt version under a new prefix.
"""
import os
import argparse
import boto3
import tempfile
from io import BytesIO

import pdfplumber      # pip install pdfplumber
import docx2txt       # pip install docx2txt
import pandas as pd   # pip install pandas openpyxl

def extract_text(bucket: str, key: str, s3) -> str:
    """
    Download the object from S3 and extract text based on its extension.
    Returns None for unsupported types.
    """
    ext = key.lower().rsplit('.', 1)[-1]
    resp = s3.get_object(Bucket=bucket, Key=key)
    data = resp['Body'].read()

    if ext == 'pdf':
        text_pages = []
        with pdfplumber.open(BytesIO(data)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt:
                    text_pages.append(txt)
        return "\n\n".join(text_pages)

    elif ext in ('doc', 'docx'):
        # docx2txt only works on a filesystem path
        with tempfile.NamedTemporaryFile(suffix='.'+ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            return docx2txt.process(tmp_path) or ""
        finally:
            os.unlink(tmp_path)

    elif ext in ('xls', 'xlsx'):
        df = pd.read_excel(BytesIO(data), engine='openpyxl')
        # convert to CSV-style text
        return df.to_csv(index=False)

    else:
        # skip any other filetypes
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Convert S3-stored docs (PDF, DOCX, XLSX) to TXT and re-upload."
    )
    parser.add_argument(
        "--bucket", required=True,
        help="Your S3 bucket name (e.g. askmira-fce-project)"
    )
    parser.add_argument(
        "--input_prefix", required=True,
        help="S3 key prefix where original docs live (e.g. 'FCE Regulations/')"
    )
    parser.add_argument(
        "--output_prefix", required=True,
        help="S3 key prefix for the generated .txt files (e.g. 'FCE Regulations TXT/')"
    )
    args = parser.parse_args()

    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=args.bucket, Prefix=args.input_prefix)

    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue  # skip folder markers

            print(f"→ processing {key}")
            txt = extract_text(args.bucket, key, s3)
            if txt is None:
                print(f"  ⚠️  unsupported filetype, skipping: {key}")
                continue

            # build the destination key
            basename = os.path.basename(key).rsplit('.',1)[0]
            out_key = args.output_prefix.rstrip("/") + "/" + basename + ".txt"

            s3.put_object(
                Bucket=args.bucket,
                Key=out_key,
                Body=txt.encode("utf-8"),
                ContentType="text/plain"
            )
            print(f"  ✅  uploaded {out_key}")


if __name__ == "__main__":
    main()
