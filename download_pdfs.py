#!/usr/bin/env python3
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

import os
import re
import sys
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


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


def create_html_gallery(pdf_data, pdf_dir, thumb_dir, output_file):
    """
    Create an HTML gallery file displaying all PDFs with thumbnails.

    Args:
        pdf_data: List of tuples (pdf_url, thumbnail_filename, title, pdf_filename)
        pdf_dir: Directory containing PDFs
        thumb_dir: Directory containing thumbnails
        output_file: Path to output HTML file
    """
    # Use double curly braces to escape them in format strings
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nudel Step-by-Step Guides</title>
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
        <h1>📚 Nudel Step-by-Step Guides</h1>
        <div class="stats">
            <div>
                <strong>Total Guides:</strong> {len(pdf_data)}
            </div>
            <button class="random-button" onclick="openRandomPDF()">🎲 Random PDF</button>
        </div>
        <div class="gallery">
"""

    for _pdf_url, thumb_filename, title, pdf_filename in pdf_data:
        thumb_path = f"{thumb_dir}/{thumb_filename}" if thumb_filename else None
        pdf_path = f"{pdf_dir}/{pdf_filename}"

        if thumb_filename and os.path.exists(thumb_path):
            thumbnail_html = (
                f'<img src="{escape(thumb_path)}" alt="{escape(title)}" class="thumbnail">'
            )
        else:
            thumbnail_html = '<div class="thumbnail no-thumbnail">📄 PDF</div>'

        html_content += f"""
            <div class="card">
                {thumbnail_html}
                <div class="card-content">
                    <div class="card-title">{escape(title)}</div>
                    <a href="{escape(pdf_path)}" class="card-link" target="_blank">View PDF →</a>
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

        function openRandomPDF() {{
            if (pdfLinks.length === 0) {{
                alert('No PDFs available');
                return;
            }}
            // Select a random PDF
            const randomIndex = Math.floor(Math.random() * pdfLinks.length);
            const randomPDF = pdfLinks[randomIndex];
            // Open in new tab
            window.open(randomPDF, '_blank');
        }}
    </script>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"  ✅ Created HTML gallery: {output_file}")


def main():
    """Main function to download all PDFs and thumbnails from the page."""
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

    # Create HTML gallery
    print("\n🎨 Creating HTML gallery...")
    html_file = "gallery.html"
    create_html_gallery(processed_data, pdf_dir, thumb_dir, html_file)

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
