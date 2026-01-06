# Nudel PDF Downloader

I bought a Nudel Pod for my daughter for Christmas 2025. She loves it, and I wanted to create a gallery of the step-by-step guides for easy and quick access to the guides and videos, even offline.

So I created this Python script to download all PDFs and thumbnails from the Nudel step-by-step guides page, and create an HTML gallery to browse them, along with links to the videos on YouTube and a random PDF button.

## Disclaimer

**Copyright Notice**: This script and its authors do not own any copyrights to the PDFs, thumbnails, or any content downloaded by this script. All downloaded content remains the property of their respective copyright holders (Nudel/Playground Ideas).

This script is provided for **personal use only** with **no guarantees**. Use at your own risk. The authors are not responsible for any misuse of this script or any content downloaded through it. Please respect the original copyright holders' terms of service and usage rights.

## Usage

Run the script with `uv` (recommended):

```bash
uv run download_pdfs
```

Or with `pip`:

```bash
pip install requests beautifulsoup4 lxml
python download_pdfs.py
```

## Development

This project uses:
- **ruff** for linting and formatting
- **pre-commit** for git hooks

### Linting and Formatting

```bash
# Check for linting issues
uv run ruff check download_pdfs.py

# Auto-fix linting issues
uv run ruff check --fix download_pdfs.py

# Format code
uv run ruff format download_pdfs.py
```

### Pre-commit Hooks

Set up pre-commit hooks (optional):

```bash
uv run pre-commit install
```

Pre-commit hooks are automatically run on `git commit`. To run them manually:

```bash
uv run pre-commit run --all-files
```

## What the Script Does

The script will:
1. Fetch the webpage from https://nudel.shop/pages/step-by-step
2. Find all PDF links and their associated thumbnails on the page
3. Fetch video links from tutorial pages (level 1-4)
4. Download each PDF to the `pdfs/` directory
5. Download thumbnails to the `thumbnails/` directory
6. Create an HTML gallery (`gallery.html`) with PDFs, thumbnails, and video links
7. Display a summary of successful and failed downloads

## Output

- **PDFs**: Saved to the `pdfs/` directory
- **Thumbnails**: Saved to the `thumbnails/` directory
- **Gallery**: An HTML file (`gallery.html`) with a beautiful grid layout showing all PDFs with thumbnails

Open `gallery.html` in your web browser to view all the guides in a visual gallery format.

## Notes

- This script worked as of January 2026. If the site changes, this script may not work.
- The script skips files that already exist in the output directory.
- Filenames are sanitized to remove special characters.
- If thumbnails are not found on the page, the gallery will display placeholder images.
- The HTML gallery is self-contained and can be opened directly in any web browser.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
