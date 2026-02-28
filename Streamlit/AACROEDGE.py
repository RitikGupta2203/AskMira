# AACROEDGE.py
import os
import streamlit as st
import boto3
from dotenv import load_dotenv
from io import BytesIO

load_dotenv()

S3_BUCKET  = os.getenv("S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION")

if not S3_BUCKET:
    st.error("Please set S3_BUCKET in your .env")
    st.stop()

@st.cache_resource
def s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id     = os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name           = AWS_REGION,
    )

@st.cache_data
def list_regions():
    """
    List all first‐level 'folders' under aacrao/ → these are our regions.
    """
    client = s3_client()
    resp = client.list_objects_v2(
        Bucket    = S3_BUCKET,
        Prefix    = "aacrao/",
        Delimiter = "/"
    )
    prefixes = resp.get("CommonPrefixes", [])
    # each prefix is like "aacrao/AFRICA/"
    return [p["Prefix"].split("/")[1] for p in prefixes]

@st.cache_data
def list_countries(region: str):
    """
    List all .txt files under aacrao/{region}/ and return the country names.
    """
    client = s3_client()
    prefix = f"aacrao/{region}/"
    resp = client.list_objects_v2(
        Bucket = S3_BUCKET,
        Prefix = prefix
    )
    contents = resp.get("Contents", [])
    countries = []
    for obj in contents:
        key = obj["Key"]  # e.g. "aacrao/AFRICA/Algeria.txt"
        name = os.path.basename(key).rsplit(".", 1)[0]
        if name: 
            countries.append(name)
    return sorted(set(countries))

@st.cache_data
def fetch_country_text(region: str, country: str) -> str:
    """
    Download the .txt for region/country from S3.
    """
    client = s3_client()
    key = f"aacrao/{region}/{country}.txt"
    obj = client.get_object(Bucket=S3_BUCKET, Key=key)
    return obj["Body"].read().decode("utf-8")

def show_edge():
    st.markdown(
        """
        <div style="text-align:center;">
          <div style="
            font-family:'Cinzel Decorative', serif;
            font-size:3rem;
            color:#2E86AB;
          ">
            AACRAO EDGE
          </div>
        </div>
        """, unsafe_allow_html=True
    )

    # 1) pick a region
    regions = list_regions()
    if not regions:
        st.warning("No regions found in your S3 bucket.")
        return

    region = st.selectbox("Select Region", regions)

    # 2) pick a country
    countries = list_countries(region)
    if not countries:
        st.warning(f"No countries found under region “{region}”.")
        return

    country = st.selectbox("Select Country", countries)

    # 3) fetch & display
    if country:
        try:
            content = fetch_country_text(region, country)
            st.markdown(content)
        except Exception as e:
            st.error(f"Could not load “{country}”: {e}")
