"""
Script: scrape_aacrao_edge.py

This script crawls the AACRAO EDGE site, extracts each country's education description,
and uploads a text file per country into an S3 bucket (keyed by region/country).

Dependencies:
  - requests
  - beautifulsoup4
  - boto3
  - python-dotenv

Usage:
  poetry run python scripts/scrape_aacrao_edge.py
"""
import os
import re
import time
import random
import requests
import boto3
import logging
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urljoin

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("aacrao_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Load environment from project root .env ─────────────────────────────────
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
dotenv_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path)

# ─── Sanitize AWS_REGION ─────────────────────────────────────────────────────
raw_region = os.getenv("AWS_REGION", "us-east-1")
normalized = raw_region.replace("\u2011", "-").replace("\u2013", "-")
AWS_REGION = normalized.split("#")[0].strip()
print(f"Using AWS_REGION: {repr(AWS_REGION)}")

# ─── S3 Bucket ─────────────────────────────────────────────────────────────────
S3_BUCKET = os.getenv("S3_BUCKET")
if not S3_BUCKET:
    raise RuntimeError("Please set S3_BUCKET in your .env")

# ─── Initialize S3 client ──────────────────────────────────────────────────────
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=AWS_REGION,
)

# ─── Scraper config ────────────────────────────────────────────────────────────
BASE_URL = "https://www.aacrao.org/edge"
LISTING_URL = f"{BASE_URL}/country"

# Define headers to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# ─── Manually defined region mappings ────────────────────────────────────────
# This is based on geographical knowledge
# Note: Some countries might be in multiple regions or disputed territories
COUNTRY_TO_REGION = {
    # AFRICA
    'Algeria': 'AFRICA', 'Angola': 'AFRICA', 'Benin': 'AFRICA',
    'Botswana': 'AFRICA', 'Burkina Faso': 'AFRICA', 'Burundi': 'AFRICA',
    'Cameroon': 'AFRICA', 'Cape Verde': 'AFRICA', 'Central African Republic': 'AFRICA',
    'Chad': 'AFRICA', 'Comoros': 'AFRICA', 'Congo, Democratic Republic of': 'AFRICA',
    'Congo, Republic of': 'AFRICA', 'Côte d\'Ivoire, (Republic of)': 'AFRICA',
    'Djibouti': 'AFRICA', 'Egypt': 'AFRICA', 'Equatorial Guinea': 'AFRICA',
    'Eritrea': 'AFRICA', 'Eswatini': 'AFRICA', 'Ethiopia': 'AFRICA',
    'Gabon': 'AFRICA', 'Gambia, The': 'AFRICA', 'Ghana': 'AFRICA',
    'Guinea': 'AFRICA', 'Guinea-Bissau': 'AFRICA', 'Kenya': 'AFRICA',
    'Lesotho': 'AFRICA', 'Liberia': 'AFRICA', 'Libya': 'AFRICA',
    'Madagascar': 'AFRICA', 'Malawi': 'AFRICA', 'Mali': 'AFRICA',
    'Mauritania': 'AFRICA', 'Mauritius': 'AFRICA', 'Mayotte': 'AFRICA',
    'Morocco': 'AFRICA', 'Mozambique': 'AFRICA', 'Namibia': 'AFRICA',
    'Niger': 'AFRICA', 'Nigeria': 'AFRICA', 'Reunion': 'AFRICA',
    'Rwanda': 'AFRICA', 'Saint Helena': 'AFRICA', 'Sao Tome and Principe': 'AFRICA',
    'Senegal': 'AFRICA', 'Seychelles': 'AFRICA', 'Sierra Leone': 'AFRICA',
    'Somalia': 'AFRICA', 'South Africa': 'AFRICA', 'Sudan': 'AFRICA',
    'Tanzania': 'AFRICA', 'Togo': 'AFRICA', 'Tunisia': 'AFRICA',
    'Uganda': 'AFRICA', 'Zambia': 'AFRICA', 'Zimbabwe': 'AFRICA',
    # ASIA
    'Afghanistan': 'ASIA', 'Azerbaijan': 'ASIA', 'Bahrain': 'ASIA',
    'Bangladesh': 'ASIA', 'Bhutan': 'ASIA', 'British Indian Ocean Territory': 'ASIA',
    'Brunei': 'ASIA', 'Cambodia': 'ASIA', 'China': 'ASIA',
    'Georgia': 'ASIA', 'Hong Kong SAR, China': 'ASIA', 'India': 'ASIA',
    'Indonesia': 'ASIA', 'Iran (Islamic Republic of)': 'ASIA', 'Iraq': 'ASIA',
    'Israel': 'ASIA', 'Japan': 'ASIA', 'Jordan': 'ASIA',
    'Kazakhstan': 'ASIA', 'Korea, Republic of (South Korea)': 'ASIA', 'Kuwait': 'ASIA',
    'Kyrgyzstan': 'ASIA', 'Laos': 'ASIA', 'Lebanon': 'ASIA',
    'Macau SAR, China': 'ASIA', 'Malaysia': 'ASIA', 'Maldives': 'ASIA',
    'Mongolia': 'ASIA', 'Myanmar': 'ASIA', 'Nepal': 'ASIA',
    'Oman': 'ASIA', 'Pakistan': 'ASIA', 'Palestine': 'ASIA',
    'Philippines': 'ASIA', 'Qatar': 'ASIA', 'Russia': 'ASIA', # Russia spans both Asia and Europe
    'Saudi Arabia': 'ASIA', 'Singapore': 'ASIA', 'Sri Lanka': 'ASIA',
    'Syrian Arab Republic': 'ASIA', 'Taiwan': 'ASIA', 'Tajikistan': 'ASIA',
    'Thailand': 'ASIA', 'Türkiye': 'ASIA', 'Turkey': 'ASIA', # Turkey spans both Asia and Europe
    'Turkmenistan': 'ASIA', 'United Arab Emirates': 'ASIA', 'Uzbekistan': 'ASIA',
    'Vietnam': 'ASIA', 'Yemen, Republic of': 'ASIA',
    # EUROPE
    'Albania': 'EUROPE', 'Andorra': 'EUROPE', 'Armenia': 'EUROPE',
    'Austria': 'EUROPE', 'Bailiwick of Guernsey': 'EUROPE', 'Bailiwick of Jersey': 'EUROPE',
    'Belarus': 'EUROPE', 'Belgium': 'EUROPE', 'Bologna Process': 'EUROPE',
    'Bosnia and Herzegovina': 'EUROPE', 'Bulgaria': 'EUROPE', 'Croatia': 'EUROPE',
    'Cyprus': 'EUROPE', 'Czech Republic': 'EUROPE', 'Denmark': 'EUROPE',
    'Estonia': 'EUROPE', 'Faroe Islands': 'EUROPE', 'Finland': 'EUROPE',
    'France': 'EUROPE', 'Germany': 'EUROPE', 'Gibraltar': 'EUROPE',
    'Greece': 'EUROPE', 'Greenland': 'EUROPE', 'Hungary': 'EUROPE',
    'Iceland': 'EUROPE', 'Ireland': 'EUROPE', 'Isle of Man': 'EUROPE',
    'Italy': 'EUROPE', 'Kosovo': 'EUROPE', 'Latvia': 'EUROPE',
    'Liechtenstein': 'EUROPE', 'Lithuania': 'EUROPE', 'Luxembourg': 'EUROPE',
    'Macedonia': 'EUROPE', 'Malta': 'EUROPE', 'Moldova': 'EUROPE',
    'Monaco': 'EUROPE', 'Montenegro': 'EUROPE', 'Netherlands, The': 'EUROPE',
    'Norway': 'EUROPE', 'Poland': 'EUROPE', 'Portugal': 'EUROPE',
    'Romania': 'EUROPE', 'San Marino': 'EUROPE', 'Scotland': 'EUROPE',
    'Serbia': 'EUROPE', 'Slovakia': 'EUROPE', 'Slovenia': 'EUROPE',
    'Spain': 'EUROPE', 'Sweden': 'EUROPE', 'Switzerland': 'EUROPE',
    'Ukraine': 'EUROPE', 'United Kingdom': 'EUROPE', 'Vatican City (Holy See)': 'EUROPE',
    'Yugoslavia': 'EUROPE',
    # NORTH AMERICA
    'Anguilla': 'NORTH AMERICA', 'Antigua and Barbuda': 'NORTH AMERICA',
    'Aruba': 'NORTH AMERICA', 'Bahamas': 'NORTH AMERICA',
    'Barbados': 'NORTH AMERICA', 'Belize': 'NORTH AMERICA',
    'Bermuda': 'NORTH AMERICA', 'British Virgin Islands (BVI)': 'NORTH AMERICA',
    'Canada: Alberta': 'NORTH AMERICA', 'Canada: British Columbia': 'NORTH AMERICA',
    'Canada: Manitoba': 'NORTH AMERICA', 'Canada: New Brunswick': 'NORTH AMERICA',
    'Canada: Newfoundland and Labrador': 'NORTH AMERICA', 'Canada: Northwest Territories': 'NORTH AMERICA',
    'Canada: Nova Scotia': 'NORTH AMERICA', 'Canada: Nunavut': 'NORTH AMERICA',
    'Canada: Ontario': 'NORTH AMERICA', 'Canada: Prince Edward Island': 'NORTH AMERICA',
    'Canada: Quebec': 'NORTH AMERICA', 'Canada: Saskatchewan': 'NORTH AMERICA',
    'Canada: Yukon': 'NORTH AMERICA', 'Cayman Islands': 'NORTH AMERICA',
    'Costa Rica': 'NORTH AMERICA', 'Cuba': 'NORTH AMERICA',
    'Dominica': 'NORTH AMERICA', 'Dominican Republic': 'NORTH AMERICA',
    'El Salvador': 'NORTH AMERICA', 'Grenada': 'NORTH AMERICA',
    'Guadeloupe': 'NORTH AMERICA', 'Guatemala': 'NORTH AMERICA',
    'Haiti': 'NORTH AMERICA', 'Honduras': 'NORTH AMERICA',
    'Jamaica': 'NORTH AMERICA', 'Martinique': 'NORTH AMERICA',
    'Mexico': 'NORTH AMERICA', 'Montserrat': 'NORTH AMERICA',
    'Netherlands Antilles': 'NORTH AMERICA', 'Nicaragua': 'NORTH AMERICA',
    'Panama': 'NORTH AMERICA', 'Puerto Rico': 'NORTH AMERICA',
    'Saint Kitts and Nevis': 'NORTH AMERICA', 'Saint Lucia': 'NORTH AMERICA',
    'Saint Pierre and Miquelon': 'NORTH AMERICA', 'Saint Vincent and the Grenadines': 'NORTH AMERICA',
    'Trinidad and Tobago': 'NORTH AMERICA', 'Turks and Caicos Islands': 'NORTH AMERICA',
    'U.S. Virgin Islands': 'NORTH AMERICA', 'United States of America': 'NORTH AMERICA',
    'USA': 'NORTH AMERICA',
    # OCEANIA
    'American Samoa': 'OCEANIA', 'Australia': 'OCEANIA',
    'Cook Islands': 'OCEANIA', 'Fiji Islands': 'OCEANIA',
    'French Polynesia': 'OCEANIA', 'Guam': 'OCEANIA',
    'Kiribati': 'OCEANIA', 'Marshall Islands': 'OCEANIA',
    'Micronesia, Federated States of': 'OCEANIA', 'Nauru': 'OCEANIA',
    'New Caledonia': 'OCEANIA', 'New Zealand': 'OCEANIA',
    'Niue': 'OCEANIA', 'Norfolk Island': 'OCEANIA',
    'Northern Mariana Islands (Commonwealth of the)': 'OCEANIA', 'Palau': 'OCEANIA',
    'Papua New Guinea': 'OCEANIA', 'Pitcairn Island': 'OCEANIA',
    'Samoa': 'OCEANIA', 'Solomon Islands': 'OCEANIA',
    'Tokelau': 'OCEANIA', 'Tonga': 'OCEANIA',
    'Tuvalu': 'OCEANIA', 'U.S. Territories and Minor Outlying Islands': 'OCEANIA',
    'Vanuatu': 'OCEANIA', 'Wallis and Futuna': 'OCEANIA',
    # SOUTH AMERICA
    'Argentina': 'SOUTH AMERICA', 'Bolivia': 'SOUTH AMERICA',
    'Brazil': 'SOUTH AMERICA', 'Chile': 'SOUTH AMERICA',
    'Colombia': 'SOUTH AMERICA', 'Ecuador': 'SOUTH AMERICA',
    'Falkland Islands': 'SOUTH AMERICA', 'French Guiana': 'SOUTH AMERICA',
    'Guyana': 'SOUTH AMERICA', 'Paraguay': 'SOUTH AMERICA',
    'Peru': 'SOUTH AMERICA', 'South Georgia and the South Sandwich Islands': 'SOUTH AMERICA',
    'Suriname': 'SOUTH AMERICA', 'Uruguay': 'SOUTH AMERICA',
    'Venezuela': 'SOUTH AMERICA'
}

def fetch_soup(url: str, retries=3) -> BeautifulSoup:
    """Fetch and parse a webpage with retries and random delays."""
    for attempt in range(retries):
        try:
            # Add a small random delay to avoid overwhelming the server
            time.sleep(random.uniform(1, 3))
            
            logger.info(f"Fetching: {url}")
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt+1}/{retries} failed: {e}")
            if attempt == retries - 1:
                logger.error(f"Failed to fetch {url} after {retries} attempts")
                raise
            time.sleep(random.uniform(5, 10))  # Longer delay between retries

def parse_country_listing():
    """Fetch the main country listing page and extract all country links with their regions."""
    soup = fetch_soup(LISTING_URL)
    
    # Find all country links
    country_entries = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/edge/country/' in href and not href.endswith('/edge/country/'):
            name = link.get_text(strip=True)
            if name:  # Ensure we have a valid country name
                full_url = urljoin(BASE_URL, href)
                
                # Determine region from our mapping
                region = COUNTRY_TO_REGION.get(name, 'UNKNOWN')
                
                country_entries.append((region, name, full_url))
    
    # Count countries by region for logging
    regions_count = {}
    for region, _, _ in country_entries:
        regions_count[region] = regions_count.get(region, 0) + 1
    
    for region, count in regions_count.items():
        logger.info(f"Region {region}: {count} countries")
    
    logger.info(f"Found {len(country_entries)} country entries in total")
    
    return country_entries

def scrape_country(name: str, url: str) -> str:
    """Extract main descriptive text and educational information for a country."""
    try:
        soup = fetch_soup(url)

        content_selectors = [
            'div.entry-content',
            'div.page-content',
            'div.main-content',
            'article',
            'main'
        ]

        container = None
        for selector in content_selectors:
            container = soup.select_one(selector)
            if container and len(container.get_text(strip=True)) > 100:
                break

        if not container:
            logger.warning(f"No content container found for {name}, falling back to <p> tags")
            paras = soup.find_all('p')
        else:
            paras = container.find_all(['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

        # Combine all content
        text = f"# {name} Education System\n\n"
        text += f"Source: {url}\n"
        text += f"Scraped: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        # Set of country names to detect repeated listings
        known_countries = set(COUNTRY_TO_REGION.keys())

        for elem in paras:
            tag = elem.name
            content = elem.get_text(strip=True)

            if not content:
                continue

            # Heuristic: Skip content that has many known countries in it (likely navigation menus)
            matches = [country for country in known_countries if country in content]
            if len(matches) > 5:
                continue  # skip this paragraph/list

            if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                level = int(tag[1])
                text += f"{'#' * level} {content}\n\n"
            elif tag == 'li':
                text += f"- {content}\n"
            else:
                text += f"{content}\n\n"

        if len(text.split('\n')) < 5:
            logger.warning(f"Very little content found for {name}")

        return text

    except Exception as e:
        logger.error(f"Error scraping country {name}: {e}")
        return ""


def upload_to_s3(region: str, country: str, content: str):
    """Upload content to S3 with appropriate error handling."""
    try:
        safe_region = re.sub(r"[^a-zA-Z0-9_-]", "_", region)
        safe_country = re.sub(r"[^a-zA-Z0-9_-]", "_", country)
        key = f"aacrao/{safe_region}/{safe_country}.txt"
        
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=content.encode('utf-8'),
            ContentType='text/plain'
        )
        logger.info(f"Uploaded {safe_country}.txt to s3://{S3_BUCKET}/{key}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload {country} to S3: {e}")
        return False

def main():
    try:
        logger.info("Starting AACRAO EDGE scraper")
        
        # Get all countries grouped by region
        listings = parse_country_listing()
        
        # Track successes and failures
        success_count = 0
        error_count = 0
        
        for region, name, url in listings:
            try:
                logger.info(f"Scraping {region} - {name}")
                content = scrape_country(name, url)
                
                if not content:
                    logger.warning(f"⚠️ No content for {name}")
                    error_count += 1
                    continue
                
                success = upload_to_s3(region, name, content)
                if success:
                    success_count += 1
                else:
                    error_count += 1
                
                # Be nice to the server
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"Error processing {name}: {e}")
                error_count += 1
                
            # Optional: Add a checkpoint to save progress
            if (success_count + error_count) % 10 == 0:
                logger.info(f"Progress: {success_count + error_count}/{len(listings)} countries processed")
                logger.info(f"Current stats - Successful: {success_count}, Failed: {error_count}")
        
        logger.info(f"Scraping complete. Successful: {success_count}, Failed: {error_count}")
        
    except Exception as e:
        logger.critical(f"Critical error in main process: {e}")
        raise

if __name__ == '__main__':
    main()