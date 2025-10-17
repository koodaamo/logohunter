# LogoHunter 🎯

An async Python library and CLI for discovering and processing high-quality customer logos from websites.

- Library: programmatic API to find, score, and fetch the best logo for a domain
- CLI: quick, pretty terminal tool to inspect candidates and save the best logo


## Features

- Async discovery with httpx and selectolax (fast, non-blocking)
- Multi-source discovery:
  - Web App Manifest icons
  - Apple Touch icons
  - Standard favicon declarations (including SVG)
  - Open Graph / social tags
  - Heuristics for logo images in the DOM (classes/ids/alt)
  - Common fallback paths
- Rule-based scoring engine (modular bonuses/penalties under `src/logohunter/rules`)
- Image validation and basic processing with Pillow (LANCZOS resizing)
- Rich-powered CLI for inspecting candidates and scores


## Requirements

- Python 3.12+
- Dependencies (installed automatically): httpx, selectolax, Pillow, rich


## Installation

From source (recommended for now):

```bash
# clone and install in editable mode
git clone <repository-url>
cd logohunter
pip install -e .
```

After install, the CLI command `logohunt` is available. You can also run it with uv:

```bash
uv run logohunt github.com
```

Note: If this project is published on PyPI under the same name, you can install with:

```bash
pip install logohunter
```


## Quick Start (Library)

```python
import asyncio
from logohunter import LogoHunter

async def main():
    hunter = LogoHunter()

    # Get the best logo as bytes (PNG/JPEG/WebP for raster images, raw SVG bytes for SVG)
    logo_bytes = await hunter.get_customer_logo(
        "github.com",
        output_format="PNG",
        resize_to=(128, 128),
    )

    if logo_bytes:
        # Note: If the selected logo is SVG, you'll receive SVG bytes regardless of output_format
        with open("github_logo", "wb") as f:
            f.write(logo_bytes)
        print("Logo saved (extension depends on content: add .png/.svg accordingly)!")
    else:
        print("No logo found")

asyncio.run(main())
```

If you specifically need to rasterize SVG to PNG, install a converter (e.g., `cairosvg`) and perform that step yourself. The library currently returns raw SVG bytes when the best logo is an SVG.


## Quick Start (CLI)

Inspect candidates, see scores, and optionally save the best one.

```bash
# Basic usage
logohunt github.com

# Save best logo to current directory (logo.png/svg)
logohunt github.com --save

# Save to a directory and show all scoring details
logohunt github.com --save logos/ --all-scores

# Verbose mode will also show exceptions if they occur
logohunt github.com --verbose
```

Example CLI output (truncated):

```
LogoHunt • Analyzing github.com

📊 Found 5 logo candidates
#1 • Score: 1240 • SVG
https://github.com/favicon.svg
#2 • Score: 860 • PNG (180×180)
https://github.com/apple-touch-icon.png
...
✅ Successfully fetched logo
💾 Saved to: /path/to/logos/logo.svg
```


## Discovery Strategy

LogoHunter collects potential logo icons from multiple sources:

1. Web App Manifest (`<link rel="manifest" href="...">` → `icons` array)
2. Apple Touch icons (`<link rel="apple-touch-icon" ...>`, including precomposed)
3. Standard favicon declarations (`<link rel="icon" ...>`, SVG preferred when available)
4. Social/preview images (`og:image`, `twitter:image`) with penalties applied via scoring
5. Heuristics for DOM images that look like logos
   - Looks for `img` elements in containers with classes/ids like `logo`, `brand`, `header-logo`, `site-logo`, `navbar-brand`, etc.
   - Also considers `alt`, `class`, `id`, and filename keywords containing `logo`
6. Common fallback paths like `/favicon.svg`, `/logo.svg`, `/favicon.ico`, etc.

All discovered candidates are de-duplicated and then scored.


## Scoring System (Rule-based)

Scoring is modular and data-driven:

- Rules live under `src/logohunter/rules/` and are grouped by category (e.g., `html`, `dimensions`).
- Each category has `bonuses.txt` and `penalties.txt` that define weights, and Python functions that implement the checks.
- The engine loads all rules and computes a cumulative score with per-rule breakdowns.

Examples of current rules and weights (abbreviated):

- HTML bonuses (`rules/html/bonuses.txt`):
  - +100 logo_in_filename, +100 logo_in_css_classes, +100 logo_in_element_id, +40 logo_in_alt_text
  - +80 header_proximity, +80 parent_logo_context, +50 brand_keywords
- HTML penalties (`rules/html/penalties.txt`):
  - -200 social_media_context, -200 single_color_svg, -150 generic_image_names
  - -100 deep_dom_nesting, -75 advertisement_context, -60 content_area_context
- Dimension rules (`rules/dimensions/*.txt`):
  - +60 apple_touch_icon_sizes
  - -300 social_media_dimensions, -200 banner_dimensions, -150 very_small_images
  - -80 extremely_wide_aspect_ratio, -50 small_images, -20 odd_dimensions

The CLI can show a detailed rule breakdown for the top candidates (`--all-scores`).


## API Reference

Instantiate the hunter and use its async methods.

- `await hunter.get_customer_logo(domain, output_format="PNG", resize_to=None, logger=None) -> bytes | None`
  - Discovers, fetches, validates, and processes the best logo.
  - Returns image bytes. If the best logo is SVG, returns the raw SVG bytes.

- `await hunter.find_logo_urls(domain) -> list[str]`
  - Returns a list of candidate logo URLs sorted by score (best first).

- `await hunter.find_logo_candidates(domain) -> list[Icon]`
  - Returns full candidate objects with scoring details.

- `await hunter.fetch_best_logo(urls) -> PIL.Image.Image | str | None`
  - Fetches and validates the best workable logo from the provided URLs.
  - Returns a PIL Image for raster formats, or an SVG string for vector logos.

- `LogoHunter.process_image(image, output_format="PNG", resize_to=None) -> bytes`
  - Static method. For PIL images, resizes and encodes to the requested format.
  - For SVG strings, returns the SVG content as UTF‑8 bytes (no rasterization).


## Logging

- The library logs summary information at INFO and detailed steps at DEBUG.
- You can pass a custom logger to `get_customer_logo(..., logger=my_logger)` to control output.

Example:

```python
import logging
from logohunter import LogoHunter

logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)

hunter = LogoHunter()
logo_bytes = await hunter.get_customer_logo("github.com", logger=logger)
```


## Contributing

- Issues and PRs are welcome.
- The scoring system is designed to be extensible — contributions to rules are appreciated.
- Run tests with pytest (see `pyproject.toml` for dev dependencies).


## License

MIT License - see LICENSE file for details.


## Changelog

### 0.1.0
- Initial async library and CLI
- Modular rule-based scoring engine
- Rich CLI for candidate inspection and saving
