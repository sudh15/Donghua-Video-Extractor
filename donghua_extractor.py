import os
import math
import socket
import time
import random
import hashlib
import base64
import requests
from flask import Flask, render_template, request, redirect, url_for
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure secret key

# === Hidden Encryption Key (Derived from System) ===
system_key = os.getenv("USER", "secure_default")
ENC_KEY = hashlib.sha256(system_key.encode()).hexdigest()[:32]

# === Encrypted Copyright Protection (Hidden Values) ===
ENC_DATA = base64.b64encode("© 2024 Geeta Tech Hub. All Rights Reserved.".encode()).decode()
ENC_URL = base64.b64encode("https://geetatechhub.blogspot.com/".encode()).decode()

def decrypt_data(enc_data, key):
    """Decrypt data only with the correct system-derived key."""
    return base64.b64decode(enc_data.encode()).decode() if key == ENC_KEY else None

COPYRIGHT_TEXT = decrypt_data(ENC_DATA, ENC_KEY)
PROTECTED_URL = decrypt_data(ENC_URL, ENC_KEY)
COPYRIGHT_HASH = hashlib.sha256(COPYRIGHT_TEXT.encode()).hexdigest()

# === Configuration ===
HEADERS = {"User-Agent": "Mozilla/5.0"}
RESULTS_PER_PAGE = 6

# === Utility: Validate Copyright ===
def validate_copyright():
    current_hash = hashlib.sha256(COPYRIGHT_TEXT.encode()).hexdigest()
    return current_hash == COPYRIGHT_HASH

# === Utility: Get Site Details ===
def get_site_details(target_url):
    parsed = urlparse(target_url)
    site_name = parsed.netloc
    try:
        site_ip = socket.gethostbyname(site_name)
    except Exception:
        site_ip = "Unknown"
    return {"target_url": target_url, "target_site_name": site_name, "target_ip": site_ip}

# === Extraction: Get All Post Links (Only donghua posts) ===
def get_all_post_links(base_url):
    """
    Extracts all valid post links from the target URL that belong to its domain.
    Only includes links that contain the word "episode" (case-insensitive).
    """
    post_links = []
    parsed_url = urlparse(base_url)
    base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    try:
        response = requests.get(base_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urljoin(base_domain, a["href"])
            # Filter: Must belong to base_domain and contain "episode"
            if link.startswith(base_domain) and "episode" in link.lower() and all(x not in link.lower() for x in ["facebook", "discord"]):
                # Use anchor text as title if available
                title = a.get_text(strip=True)
                if not title or len(title) < 5:
                    title = format_episode_title(link)
                post_links.append({"title": title, "post_link": link})
    except requests.exceptions.RequestException:
        pass
    # Deduplicate based on post_link
    unique_links = {item["post_link"]: item for item in post_links}
    return list(unique_links.values())

# === Extraction: Extract Video Info from a Post ===
def extract_video_info(post_url):
    """
    Extracts video details from the post page:
    - Title (from post header or formatted from URL)
    - Dailymotion video URL and embed code
    """
    try:
        response = requests.get(post_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title_elem = soup.find("h1", class_="post-title")
        formatted_title = title_elem.get_text(strip=True) if title_elem else format_episode_title(post_url)
        
        video_url = None
        embed_code = None
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src")
            if src and "dailymotion" in src:
                video_url = src
                embed_code = f'&lt;iframe src="{src}" width="720" height="400" allowfullscreen&gt;&lt;/iframe&gt;'
                break
        if not video_url:
            return None
        return {
            "formatted_title": formatted_title,
            "video_source": "Dailymotion",
            "video_url": video_url,
            "embed_code": embed_code
        }
    except requests.exceptions.RequestException:
        return None

def format_episode_title(url):
    """Formats an anime title from the URL."""
    try:
        # Assume the last segment (before the trailing slash) is the slug.
        slug = url.strip("/").split("/")[-1]
        # Replace dashes with spaces and capitalize each word.
        return " ".join(word.capitalize() for word in slug.split("-"))
    except Exception:
        return "Unknown Title"

# === Flask Routes ===

@app.route("/")
def index():
    note = "Note: This extractor works only on Donghua streaming sites and shows only Dailymotion video sources."
    return render_template("index.html", note=note, site_details={}, copyright_text=COPYRIGHT_TEXT)

@app.route("/scan", methods=["POST", "GET"])
def scan():
    base_url = request.args.get("url") or request.form.get("url")
    selected = request.args.get("selected")
    site_details = get_site_details(base_url)
    
    # If a specific post is selected, scrape its details.
    if selected:
        info = extract_video_info(selected)
        videos = [info] if info else []
        return render_template("results.html", videos=videos, site_details=site_details, previous_page=request.referrer or url_for("index"), base_url=base_url, page=1, total_pages=1, copyright_text=COPYRIGHT_TEXT)
    
    # Otherwise, get all valid donghua post links and show selection page.
    videos = get_all_post_links(base_url)
    if not videos:
        return "No valid donghua posts found.", 404
    # Show all found results in the selection page (no extra details).
    return render_template("select.html", videos=videos, site_details=site_details, base_url=base_url, total_results=len(videos), copyright_text=COPYRIGHT_TEXT)

@app.before_request
def protect_copyright():
    if not validate_copyright():
        return redirect(PROTECTED_URL)

if __name__ == "__main__":
    app.run(debug=True)
