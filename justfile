build:
    uv run python scripts/build.py

serve: build
    uv run python -m http.server -d _site
