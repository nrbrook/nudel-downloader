#!/usr/bin/env python3
# /// script
# dependencies = [
#     "requests>=2.31.0",
#     "beautifulsoup4>=4.12.0",
#     "lxml>=4.9.0",
# ]
# ///
"""
Script to download all PDFs from https://nudel.shop/pages/step-by-step

This script fetches the webpage, finds all PDF links, downloads them
along with thumbnails, and creates an HTML gallery.

Copyright Notice:
This script and its authors do not own any copyrights to the PDFs, thumbnails,
or any content downloaded by this script. All downloaded content remains the
property of their respective copyright holders (Nudel/Playground Ideas).

This script is provided for personal use only with no guarantees. Use at your
own risk. The authors are not responsible for any misuse of this script or
any content downloaded through it. Please respect the original copyright
holders' terms of service and usage rights.

License: MIT License (see LICENSE file for details)
"""

import argparse
import os
import re
import sys
from difflib import SequenceMatcher
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def normalize_title(title):
    """
    Normalize a title for comparison by removing level prefix, punctuation, and extra whitespace.

    Args:
        title: The title string to normalize

    Returns:
        Normalized lowercase string with consistent formatting
    """
    if not title:
        return ""
    # Convert to lowercase
    normalized = title.lower()
    # Remove "level X -" or "level X" prefix
    normalized = re.sub(r"^level\s*\d+\s*[-–—:]?\s*", "", normalized)
    # Replace underscores and hyphens with spaces
    normalized = normalized.replace("_", " ").replace("-", " ")
    # Remove punctuation except spaces
    normalized = re.sub(r"[^\w\s]", "", normalized)
    # Collapse multiple spaces into one
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def extract_level(title):
    """
    Extract the level number from a title.

    Args:
        title: The title string to extract level from

    Returns:
        Integer level number (1-4) or None if not found
    """
    if not title:
        return None
    match = re.search(r"level\s*(\d+)", title.lower())
    return int(match.group(1)) if match else None


def tokenize(text):
    """
    Split text into a set of normalized tokens for comparison.

    Args:
        text: The text to tokenize

    Returns:
        Set of lowercase word tokens
    """
    return set(normalize_title(text).split())


def calculate_match_score(title1, title2):
    """
    Calculate a similarity score between two titles using multiple strategies.

    Args:
        title1: First title to compare
        title2: Second title to compare

    Returns:
        Float score between 0 and 1, where 1 is a perfect match
    """
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)

    if not norm1 or not norm2:
        return 0.0

    # Exact normalized match
    if norm1 == norm2:
        return 1.0

    # Token-based Jaccard similarity
    tokens1 = tokenize(title1)
    tokens2 = tokenize(title2)
    if tokens1 and tokens2:
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        jaccard = intersection / union if union > 0 else 0
    else:
        jaccard = 0

    # Sequence matcher ratio (handles word order and partial matches)
    sequence_ratio = SequenceMatcher(None, norm1, norm2).ratio()

    # Substring containment bonus
    containment_bonus = 0.0
    if norm1 in norm2 or norm2 in norm1:
        containment_bonus = 0.3

    # Combined score weighted toward token matching
    score = max(jaccard * 0.6 + sequence_ratio * 0.4 + containment_bonus, sequence_ratio)

    return min(score, 1.0)


def find_best_video_match(title, video_map, level=None, min_score=0.6):
    """
    Find the best matching video URL for a given title.

    Args:
        title: The PDF title to find a video for
        video_map: Dictionary mapping titles to video URLs
        level: Optional level number to prefer matches from the same level
        min_score: Minimum similarity score required for a match

    Returns:
        Video URL if a match is found, None otherwise
    """
    if not title or not video_map:
        return None

    title_norm = normalize_title(title)

    # Try exact normalized match first
    for key, url in video_map.items():
        if normalize_title(key) == title_norm:
            return url

    # Find best fuzzy match
    best_score = 0.0
    best_url = None
    best_level_match = False

    for key, url in video_map.items():
        score = calculate_match_score(title, key)

        # Check if this key matches the same level
        key_level = extract_level(key)
        same_level = level is not None and key_level == level

        # Prefer same-level matches when scores are close
        if score > min_score:
            is_better = (
                score > best_score + 0.1  # Significantly better score
                or (
                    score > best_score - 0.05 and same_level and not best_level_match
                )  # Similar score but better level match
            )
            if (is_better or best_url is None) and (
                score > best_score or (same_level and not best_level_match)
            ):
                best_score = score
                best_url = url
                best_level_match = same_level

    return best_url


def find_pdf_links_with_thumbnails(soup, base_url):
    """
    Find all PDF links and their associated thumbnails in the HTML content.

    Args:
        soup: BeautifulSoup object containing the parsed HTML
        base_url: Base URL of the page for resolving relative links

    Returns:
        List of tuples: (pdf_url, thumbnail_url, title)
    """
    pdf_data = []
    pdf_urls_seen = set()

    # Find all <a> tags with href containing .pdf
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" in href.lower():
            absolute_url = urljoin(base_url, href)
            if absolute_url in pdf_urls_seen:
                continue
            pdf_urls_seen.add(absolute_url)

            # Try to find associated thumbnail
            thumbnail_url = None
            title = link.get_text(strip=True) or None

            # Look for image in the link itself
            img = link.find("img")
            if img:
                thumbnail_url = (
                    img.get("src")
                    or img.get("data-src")
                    or img.get("data-lazy-src")
                    or img.get("data-original")
                )
                if thumbnail_url:
                    thumbnail_url = urljoin(base_url, thumbnail_url)
                if not title:
                    title = img.get("alt") or img.get("title")

            # Look in parent container for images
            if not thumbnail_url:
                parent = link.parent
                depth = 0
                while parent and depth < 3:  # Check up to 3 levels up
                    img = parent.find("img")
                    if img:
                        thumbnail_url = (
                            img.get("src")
                            or img.get("data-src")
                            or img.get("data-lazy-src")
                            or img.get("data-original")
                        )
                        if thumbnail_url:
                            thumbnail_url = urljoin(base_url, thumbnail_url)
                            break
                    parent = parent.parent
                    depth += 1

            # Look for images in sibling elements
            if not thumbnail_url and link.parent:
                for sibling in link.parent.find_all("img", limit=1):
                    thumbnail_url = (
                        sibling.get("src")
                        or sibling.get("data-src")
                        or sibling.get("data-lazy-src")
                        or sibling.get("data-original")
                    )
                    if thumbnail_url:
                        thumbnail_url = urljoin(base_url, thumbnail_url)
                        break

            # Extract title from filename if not found or if title is generic
            parsed = urlparse(absolute_url)
            filename_title = (
                os.path.splitext(os.path.basename(parsed.path))[0]
                .replace("_", " ")
                .replace("-", " ")
            )

            # Use filename-based title if no title or if title is too generic
            if (
                not title
                or title.lower() in ["let's build it!", "download", "view", "pdf", "click here"]
                or len(title) < 5
            ):
                title = filename_title

            pdf_data.append((absolute_url, thumbnail_url, title))

    # Also find PDFs in other tags
    for embed in soup.find_all("embed", src=True):
        src = embed["src"]
        if ".pdf" in src.lower():
            absolute_url = urljoin(base_url, src)
            if absolute_url not in pdf_urls_seen:
                pdf_urls_seen.add(absolute_url)
                parsed = urlparse(absolute_url)
                title = (
                    os.path.splitext(os.path.basename(parsed.path))[0]
                    .replace("_", " ")
                    .replace("-", " ")
                )
                pdf_data.append((absolute_url, None, title))

    for iframe in soup.find_all("iframe", src=True):
        src = iframe["src"]
        if ".pdf" in src.lower():
            absolute_url = urljoin(base_url, src)
            if absolute_url not in pdf_urls_seen:
                pdf_urls_seen.add(absolute_url)
                parsed = urlparse(absolute_url)
                title = (
                    os.path.splitext(os.path.basename(parsed.path))[0]
                    .replace("_", " ")
                    .replace("-", " ")
                )
                pdf_data.append((absolute_url, None, title))

    for obj in soup.find_all("object", data=True):
        data = obj["data"]
        if ".pdf" in data.lower():
            absolute_url = urljoin(base_url, data)
            if absolute_url not in pdf_urls_seen:
                pdf_urls_seen.add(absolute_url)
                parsed = urlparse(absolute_url)
                title = (
                    os.path.splitext(os.path.basename(parsed.path))[0]
                    .replace("_", " ")
                    .replace("-", " ")
                )
                pdf_data.append((absolute_url, None, title))

    # Search for PDF URLs in script tags
    for script in soup.find_all("script"):
        if script.string:
            pdf_pattern = r'https?://[^\s"\'<>]+\.pdf'
            matches = re.findall(pdf_pattern, script.string, re.IGNORECASE)
            for match in matches:
                if match not in pdf_urls_seen:
                    pdf_urls_seen.add(match)
                    parsed = urlparse(match)
                    title = (
                        os.path.splitext(os.path.basename(parsed.path))[0]
                        .replace("_", " ")
                        .replace("-", " ")
                    )
                    pdf_data.append((match, None, title))

    # Check other attributes
    for tag in soup.find_all(True):
        for attr in tag.attrs:
            if isinstance(tag.attrs[attr], str) and ".pdf" in tag.attrs[attr].lower():
                absolute_url = urljoin(base_url, tag.attrs[attr])
                if absolute_url not in pdf_urls_seen:
                    pdf_urls_seen.add(absolute_url)
                    parsed = urlparse(absolute_url)
                    title = (
                        os.path.splitext(os.path.basename(parsed.path))[0]
                        .replace("_", " ")
                        .replace("-", " ")
                    )
                    pdf_data.append((absolute_url, None, title))

    return sorted(pdf_data, key=lambda x: x[0])


def download_image(url, output_dir, filename=None):
    """
    Download an image from a URL and save it to the output directory.

    Args:
        url: URL of the image to download
        output_dir: Directory to save the image to
        filename: Optional filename to use

    Returns:
        Tuple of (success: bool, filename: str, error_message: str or None)
    """
    if not url:
        return False, None, "No URL provided"

    try:
        if not filename:
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename:
                filename = "thumbnail.jpg"

        # Ensure filename has an extension
        if "." not in filename:
            filename += ".jpg"

        # Sanitize filename
        filename = re.sub(r"[^\w\-_\.]", "_", filename)
        filepath = os.path.join(output_dir, filename)

        # Check if file already exists
        if os.path.exists(filepath):
            return True, filename, None

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True, filename, None

    except requests.exceptions.RequestException as e:
        return False, filename if "filename" in locals() else "unknown.jpg", str(e)
    except Exception as e:
        return False, filename if "filename" in locals() else "unknown.jpg", str(e)


def download_pdf(url, output_dir):
    """
    Download a PDF from a URL and save it to the output directory.

    Args:
        url: URL of the PDF to download
        output_dir: Directory to save the PDF to

    Returns:
        Tuple of (success: bool, filename: str, error_message: str or None)
    """
    try:
        # Get the filename from the URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)

        # If no filename in URL, generate one from the URL
        if not filename or not filename.endswith(".pdf"):
            # Extract a meaningful name from the URL
            path_parts = [p for p in parsed_url.path.split("/") if p]
            filename = path_parts[-1] if path_parts else "download.pdf"

            if not filename.endswith(".pdf"):
                filename += ".pdf"

        # Sanitize filename
        filename = re.sub(r"[^\w\-_\.]", "_", filename)
        filepath = os.path.join(output_dir, filename)

        # Check if file already exists
        if os.path.exists(filepath):
            print(f"  ⏭️  Skipping {filename} (already exists)")
            return True, filename, None

        # Download the PDF
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        # Check if the response is actually a PDF
        content_type = response.headers.get("Content-Type", "").lower()
        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            # Check first few bytes for PDF magic number
            first_bytes = response.content[:4]
            if first_bytes != b"%PDF":
                return (
                    False,
                    filename,
                    f"URL does not appear to be a PDF (Content-Type: {content_type})",
                )

        # Save the file
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = os.path.getsize(filepath)
        print(f"  ✅ Downloaded {filename} ({file_size:,} bytes)")
        return True, filename, None

    except requests.exceptions.RequestException as e:
        return False, filename if "filename" in locals() else "unknown.pdf", str(e)
    except Exception as e:
        return False, filename if "filename" in locals() else "unknown.pdf", str(e)


def fetch_video_links_from_tutorial_pages():
    """
    Fetch video links from tutorial pages for each level.

    Returns:
        Dictionary mapping PDF titles to video URLs
    """
    video_map = {}
    tutorial_urls = [
        ("https://nudel.shop/pages/level-1-tutorial", "Level 1"),
        ("https://nudel.shop/pages/level-2-tutorial", "Level 2"),
        ("https://nudel.shop/pages/level-3-tutorial", "Level 3"),
        ("https://nudel.shop/pages/level-4-tutorial", "Level 4"),
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    def store_video_mapping(title, video_url, level_prefix):
        """Store video mapping with multiple key variations for better matching."""
        if not title or not video_url:
            return
        title = title.strip()
        if len(title) < 3:
            return
        # Store original title
        video_map[title.lower()] = video_url
        # Store with level prefix
        full_title = f"{level_prefix.lower()} {title.lower()}".strip()
        video_map[full_title] = video_url
        # Store normalized version
        normalized = normalize_title(title)
        if normalized:
            video_map[normalized] = video_url
            video_map[f"{level_prefix.lower()} {normalized}"] = video_url

    for tutorial_url, level_prefix in tutorial_urls:
        try:
            print(f"  🔍 Fetching videos from {tutorial_url}...")
            response = requests.get(tutorial_url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all video embeds (iframes)
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src", "") or iframe.get("data-src", "")
                if not src or (
                    "youtube.com" not in src and "youtu.be" not in src and "vimeo.com" not in src
                ):
                    continue
                # Extract clean YouTube URL
                if "youtube.com/embed/" in src:
                    video_id = src.split("/embed/")[1].split("?")[0]
                    src = f"https://www.youtube.com/watch?v={video_id}"

                title_found = False

                # Look for title in previous siblings of the iframe's parent
                parent = iframe.parent
                if parent:
                    for sibling in parent.previous_siblings:
                        if hasattr(sibling, "get_text"):
                            text = sibling.get_text(strip=True)
                            if text and len(text) > 2 and len(text) < 100:
                                store_video_mapping(text, src, level_prefix)
                                title_found = True
                                break
                        elif isinstance(sibling, str):
                            text = sibling.strip()
                            if text and len(text) > 2 and len(text) < 100:
                                store_video_mapping(text, src, level_prefix)
                                title_found = True
                                break

                # If no title found from siblings, look for nearby PDF links (limited scope)
                if not title_found:
                    search_parent = iframe.parent
                    for _depth in range(3):
                        if not search_parent:
                            break
                        # Only check direct children for PDF links, not entire subtree
                        for child in search_parent.children:
                            if hasattr(child, "find_all"):
                                for pdf_link in child.find_all("a", href=True, recursive=False):
                                    href = pdf_link.get("href", "")
                                    if ".pdf" in href.lower():
                                        parsed = urlparse(href)
                                        pdf_name = os.path.splitext(os.path.basename(parsed.path))[
                                            0
                                        ]
                                        title = pdf_name.replace("_", " ").replace("-", " ").strip()
                                        store_video_mapping(title, src, level_prefix)
                                        title_found = True
                                        break
                            if title_found:
                                break
                        if title_found:
                            break
                        search_parent = search_parent.parent

            # Look for direct YouTube/Vimeo links with nearby PDF links
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if "youtube.com" in href or "youtu.be" in href or "vimeo.com" in href:
                    parent = link.parent
                    for _ in range(3):
                        if not parent:
                            break
                        # Look for PDF links in parent's direct children
                        for pdf_link in parent.find_all("a", href=True, recursive=False):
                            pdf_href = pdf_link.get("href", "")
                            if ".pdf" in pdf_href.lower():
                                parsed = urlparse(pdf_href)
                                pdf_name = os.path.splitext(os.path.basename(parsed.path))[0]
                                title = pdf_name.replace("_", " ").replace("-", " ").strip()
                                store_video_mapping(title, href, level_prefix)
                                break
                        parent = parent.parent if parent else None

        except Exception as e:
            print(f"  ⚠️  Warning: Could not fetch videos from {tutorial_url}: {e}")
            continue

    return video_map


def create_html_gallery(
    pdf_data, pdf_dir, thumb_dir, output_file, video_map=None, use_remote_assets=False
):
    """
    Create an HTML gallery file displaying all PDFs with thumbnails.

    Args:
        pdf_data: List of tuples (pdf_url, thumbnail_url, title, pdf_filename)
        pdf_dir: Directory containing PDFs (used when use_remote_assets=False)
        thumb_dir: Directory containing thumbnails (used when use_remote_assets=False)
        output_file: Path to output HTML file
        video_map: Optional dictionary mapping PDF titles to video URLs
        use_remote_assets: If True, link to original remote PDFs and images instead of local
    """
    if video_map is None:
        video_map = {}
    # Use double curly braces to escape them in format strings
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nüdel Pod Step-by-Step Guides</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        h1 {{
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .stats {{
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }}
        .random-button {{
            padding: 12px 24px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        .random-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }}
        .random-button:active {{
            transform: translateY(0);
        }}
        .button-group {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        .video-button {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }}
        @media (max-width: 768px) {{
            .stats {{
                flex-direction: column;
            }}
        }}
        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 25px;
            margin-top: 20px;
        }}
        .card {{
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            display: flex;
            flex-direction: column;
        }}
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0,0,0,0.2);
        }}
        .thumbnail {{
            width: 100%;
            height: 200px;
            object-fit: cover;
            background: #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #999;
            font-size: 14px;
        }}
        .card-content {{
            padding: 15px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }}
        .card-title {{
            font-size: 1.1em;
            font-weight: 600;
            color: #333;
            margin-bottom: 10px;
            line-height: 1.4;
        }}
        .card-link {{
            display: inline-block;
            margin-top: auto;
            padding: 10px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 6px;
            text-align: center;
            font-weight: 500;
            transition: opacity 0.3s ease;
        }}
        .card-link:hover {{
            opacity: 0.9;
        }}
        .card-links {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: auto;
        }}
        .video-link {{
            display: inline-block;
            padding: 10px 20px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            text-decoration: none;
            border-radius: 6px;
            text-align: center;
            font-weight: 500;
            transition: opacity 0.3s ease;
            font-size: 0.9em;
        }}
        .video-link:hover {{
            opacity: 0.9;
        }}
        .no-thumbnail {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            font-weight: 500;
        }}
        @media (max-width: 768px) {{
            .gallery {{
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 15px;
            }}
            h1 {{
                font-size: 2em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Nüdel Pod Step-by-Step Guides</h1>
        <div class="stats">
            <div>
                <strong>Total Guides:</strong> {len(pdf_data)}
            </div>
            <div class="button-group">
                <button class="random-button" onclick="openRandomPDF()">🎲 Random Guide</button>
                <button class="random-button video-button" onclick="openRandomVideo()">🎬 Random Video</button>
            </div>
        </div>
        <div class="gallery">
"""

    for pdf_url, thumb_data, title, pdf_filename in pdf_data:
        if use_remote_assets:
            # Use original remote URLs
            pdf_path = pdf_url
            thumb_url = thumb_data  # thumb_data is the original URL when use_remote_assets
            if thumb_url:
                thumbnail_html = (
                    f'<img src="{escape(thumb_url)}" alt="{escape(title)}" class="thumbnail">'
                )
            else:
                thumbnail_html = '<div class="thumbnail no-thumbnail">📄 Guide</div>'
        else:
            # Use local files
            pdf_path = f"{pdf_dir}/{pdf_filename}"
            thumb_filename = thumb_data  # thumb_data is the local filename
            thumb_path = f"{thumb_dir}/{thumb_filename}" if thumb_filename else None
            if thumb_filename and os.path.exists(thumb_path):
                thumbnail_html = (
                    f'<img src="{escape(thumb_path)}" alt="{escape(title)}" class="thumbnail">'
                )
            else:
                thumbnail_html = '<div class="thumbnail no-thumbnail">📄 Guide</div>'

        # Find matching video link using fuzzy matching
        level = extract_level(title)
        video_url = find_best_video_match(title, video_map, level=level)

        # Build links section
        links_html = (
            f'<a href="{escape(pdf_path)}" class="card-link" target="_blank">View Guide →</a>'
        )
        if video_url:
            links_html = f'<div class="card-links">{links_html}<a href="{escape(video_url)}" class="video-link" target="_blank">📹 Watch Video →</a></div>'
        else:
            links_html = f'<div class="card-links">{links_html}</div>'

        html_content += f"""
            <div class="card">
                {thumbnail_html}
                <div class="card-content">
                    <div class="card-title">{escape(title)}</div>
                    {links_html}
                </div>
            </div>
"""

    html_content += """
        </div>
    </div>
    <script>
        // Collect all PDF links
        const pdfLinks = [];
        document.querySelectorAll('.card-link').forEach(link => {{
            pdfLinks.push(link.href);
        }});

        // Collect all video links
        const videoLinks = [];
        document.querySelectorAll('.video-link').forEach(link => {{
            videoLinks.push(link.href);
        }});

        function openRandomPDF() {{
            if (pdfLinks.length === 0) {{
                alert('No guides available');
                return;
            }}
            const randomIndex = Math.floor(Math.random() * pdfLinks.length);
            window.open(pdfLinks[randomIndex], '_blank');
        }}

        function openRandomVideo() {{
            if (videoLinks.length === 0) {{
                alert('No videos available');
                return;
            }}
            const randomIndex = Math.floor(Math.random() * videoLinks.length);
            window.open(videoLinks[randomIndex], '_blank');
        }}
    </script>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"  ✅ Created HTML gallery: {output_file}")


def create_deployable_gallery(output_dir="dist"):
    """
    Create a deployable HTML gallery that links to original remote assets.

    This creates a version suitable for deploying to Cloudflare Pages or similar,
    without downloading any copyrighted content (PDFs or images).

    Args:
        output_dir: Directory to output the deployable files
    """
    url = "https://nudel.shop/pages/step-by-step"

    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    print(f"📁 Output directory: {os.path.abspath(output_dir)}\n")

    # Fetch the webpage
    print(f"🌐 Fetching {url}...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching webpage: {e}")
        sys.exit(1)

    # Parse the HTML
    print("🔍 Parsing HTML and searching for PDFs and thumbnails...")
    soup = BeautifulSoup(response.text, "html.parser")

    # Find all PDF links with thumbnails
    pdf_data = find_pdf_links_with_thumbnails(soup, url)

    if not pdf_data:
        print("⚠️  No PDF links found on the page.")
        sys.exit(0)

    print(f"📄 Found {len(pdf_data)} PDF(s)")

    # Prepare data for gallery (pdf_url, thumb_url, title, pdf_filename)
    processed_data = []
    for pdf_url, thumb_url, title in pdf_data:
        parsed = urlparse(pdf_url)
        pdf_filename = os.path.basename(parsed.path)
        # For remote assets, thumb_data is the original URL
        processed_data.append((pdf_url, thumb_url, title, pdf_filename))

    # Fetch video links from tutorial pages
    print("\n🎥 Fetching video links from tutorial pages...")
    video_map = fetch_video_links_from_tutorial_pages()
    if video_map:
        print(f"  ✅ Found {len(video_map)} video link(s)")

    # Create HTML gallery with remote assets
    print("\n🎨 Creating deployable HTML gallery...")
    html_file = os.path.join(output_dir, "index.html")
    create_html_gallery(processed_data, "", "", html_file, video_map, use_remote_assets=True)

    print(f"\n{'=' * 60}")
    print("📊 Deployable Gallery Created:")
    print(f"   📁 Output directory: {os.path.abspath(output_dir)}")
    print(f"   🌐 Gallery: {os.path.abspath(html_file)}")
    print("\n   To deploy to Cloudflare Pages:")
    print(f"   1. Run: npx wrangler pages deploy {output_dir}")
    print("   Or use the deploy script: ./deploy.sh")
    print(f"{'=' * 60}")


def main():
    """Main function to download all PDFs and thumbnails from the page."""
    parser = argparse.ArgumentParser(
        description="Download Nüdel Pod step-by-step PDF guides and create an HTML gallery.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    Download PDFs and create local gallery
  %(prog)s --deploy           Create deployable gallery (no downloads)
  %(prog)s --deploy -o site   Create deployable gallery in 'site' directory
        """,
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Create a deployable gallery linking to original remote assets (no downloads)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="dist",
        help="Output directory for deployable gallery (default: dist)",
    )
    args = parser.parse_args()

    if args.deploy:
        create_deployable_gallery(args.output)
        return

    url = "https://nudel.shop/pages/step-by-step"
    pdf_dir = "pdfs"
    thumb_dir = "thumbnails"

    # Create output directories
    Path(pdf_dir).mkdir(exist_ok=True)
    Path(thumb_dir).mkdir(exist_ok=True)
    print(f"📁 PDF directory: {os.path.abspath(pdf_dir)}")
    print(f"📁 Thumbnail directory: {os.path.abspath(thumb_dir)}\n")

    # Fetch the webpage
    print(f"🌐 Fetching {url}...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching webpage: {e}")
        sys.exit(1)

    # Parse the HTML
    print("🔍 Parsing HTML and searching for PDFs and thumbnails...")
    soup = BeautifulSoup(response.text, "html.parser")

    # Find all PDF links with thumbnails
    pdf_data = find_pdf_links_with_thumbnails(soup, url)

    if not pdf_data:
        print("⚠️  No PDF links found on the page.")
        print("\n💡 Tip: The PDFs might be loaded dynamically via JavaScript.")
        print("   You may need to use a browser automation tool like Selenium.")
        sys.exit(0)

    print(f"📄 Found {len(pdf_data)} PDF(s):\n")
    for i, (_pdf_url, thumb_url, title) in enumerate(pdf_data, 1):
        thumb_info = f" (thumbnail: {thumb_url})" if thumb_url else " (no thumbnail)"
        print(f"{i}. {title}{thumb_info}")

    print(f"\n⬇️  Downloading {len(pdf_data)} PDF(s) and thumbnails...\n")

    # Download PDFs and thumbnails
    successful_pdfs = 0
    failed_pdfs = 0
    successful_thumbs = 0
    failed_thumbs = 0

    processed_data = []

    for pdf_url, thumb_url, title in pdf_data:
        # Download PDF
        success, pdf_filename, error = download_pdf(pdf_url, pdf_dir)
        if success:
            successful_pdfs += 1
        else:
            failed_pdfs += 1
            print(f"  ❌ Failed to download PDF {title}: {error}")
            continue

        # Download thumbnail
        thumb_filename = None
        if thumb_url:
            # Generate thumbnail filename from PDF filename
            thumb_basename = os.path.splitext(pdf_filename)[0]
            thumb_ext = os.path.splitext(urlparse(thumb_url).path)[1] or ".jpg"
            thumb_filename = f"{thumb_basename}_thumb{thumb_ext}"

            success, thumb_filename, error = download_image(thumb_url, thumb_dir, thumb_filename)
            if success:
                successful_thumbs += 1
            else:
                failed_thumbs += 1
                thumb_filename = None

        processed_data.append((pdf_url, thumb_filename, title, pdf_filename))

    # Fetch video links from tutorial pages
    print("\n🎥 Fetching video links from tutorial pages...")
    video_map = fetch_video_links_from_tutorial_pages()
    if video_map:
        print(f"  ✅ Found {len(video_map)} video link(s)")

    # Create HTML gallery
    print("\n🎨 Creating HTML gallery...")
    html_file = "gallery.html"
    create_html_gallery(processed_data, pdf_dir, thumb_dir, html_file, video_map)

    # Summary
    print(f"\n{'=' * 60}")
    print("📊 Summary:")
    print(f"   ✅ Successfully downloaded PDFs: {successful_pdfs}")
    print(f"   ❌ Failed PDFs: {failed_pdfs}")
    print(f"   ✅ Successfully downloaded thumbnails: {successful_thumbs}")
    print(f"   ❌ Failed thumbnails: {failed_thumbs}")
    print(f"   📁 PDFs saved to: {os.path.abspath(pdf_dir)}")
    print(f"   📁 Thumbnails saved to: {os.path.abspath(thumb_dir)}")
    print(f"   🌐 Gallery saved to: {os.path.abspath(html_file)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
