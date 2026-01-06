#!/bin/bash
# Deploy script for Nudel Gallery to Cloudflare Pages
#
# Prerequisites:
#   - Node.js installed
#   - wrangler CLI: npm install -g wrangler
#   - Authenticated with Cloudflare: wrangler login
#
# Usage:
#   ./deploy.sh                  # Build and deploy
#   ./deploy.sh --build-only     # Only build, don't deploy
#   ./deploy.sh --project NAME   # Deploy to specific project name

set -e

PROJECT_NAME="nudel-gallery"
OUTPUT_DIR="dist"
BUILD_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --project)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --build-only     Only build the gallery, don't deploy"
            echo "  --project NAME   Cloudflare Pages project name (default: nudel-gallery)"
            echo "  --output DIR     Output directory (default: dist)"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🔨 Building deployable gallery..."

# Check if uv is available, otherwise use python
if command -v uv &> /dev/null; then
    uv run python download_pdfs.py --deploy -o "$OUTPUT_DIR"
else
    python download_pdfs.py --deploy -o "$OUTPUT_DIR"
fi

if [ "$BUILD_ONLY" = true ]; then
    echo ""
    echo "✅ Build complete! Files are in: $OUTPUT_DIR"
    echo "   To deploy manually: npx wrangler pages deploy $OUTPUT_DIR --project-name $PROJECT_NAME"
    exit 0
fi

echo ""
echo "🚀 Deploying to Cloudflare Pages..."

# Check if wrangler is installed
if ! command -v npx &> /dev/null; then
    echo "❌ Error: npx not found. Please install Node.js first."
    exit 1
fi

# Deploy to Cloudflare Pages
npx wrangler pages deploy "$OUTPUT_DIR" --project-name "$PROJECT_NAME"

echo ""
echo "✅ Deployment complete!"
