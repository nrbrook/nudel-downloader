# Nudel PDF Downloader

A Python script to download all PDFs and thumbnails from the Nudel step-by-step guides page, and create an HTML gallery to browse them.

## Disclaimer

**Copyright Notice**: This script and its authors do not own any copyrights to the PDFs, thumbnails, or any content downloaded by this script. All downloaded content remains the property of their respective copyright holders (Nudel/Playground Ideas).

This script is provided for **personal use only** with **no guarantees**. Use at your own risk. The authors are not responsible for any misuse of this script or any content downloaded through it. Please respect the original copyright holders' terms of service and usage rights.

## Installation

Install the required dependencies using `uv`:

```bash
# Create a virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows

# Install dependencies
uv pip install -r requirements.txt

# Install development dependencies (for linting)
uv pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install
```

Alternatively, install directly without a virtual environment:

```bash
uv pip install -r requirements.txt --system
```

## Development

This project uses:
- **ruff** for linting and formatting
- **pre-commit** for git hooks

### Linting and Formatting

```bash
# Check for linting issues
ruff check download_pdfs.py

# Auto-fix linting issues
ruff check --fix download_pdfs.py

# Format code
ruff format download_pdfs.py
```

### Pre-commit Hooks

Pre-commit hooks are automatically run on `git commit`. To run them manually:

```bash
pre-commit run --all-files
```

## Usage

Run the script:

```bash
python download_pdfs.py
```

The script will:
1. Fetch the webpage from https://nudel.shop/pages/step-by-step
2. Find all PDF links and their associated thumbnails on the page
3. Download each PDF to the `pdfs/` directory
4. Download thumbnails to the `thumbnails/` directory
5. Create an HTML gallery (`gallery.html`) to browse all PDFs with thumbnails
6. Display a summary of successful and failed downloads

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
