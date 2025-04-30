#!/bin/bash

# Exit on error
set -e

# Run tests
echo "🧪 Running tests..."
python -m pytest tests/

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/
rm -rf build/
rm -rf *.egg-info/

# Build the package
echo "📦 Building package..."
python -m build

# Upload to PyPI
echo "🚀 Uploading to PyPI..."
python -m twine upload dist/*

echo "✅ Done!" 