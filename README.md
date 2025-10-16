# LogoHunter 🎯

A modern, async-only Python library for discovering and processing high-quality customer logos from websites.

## Features

- **Comprehensive Logo Discovery Strategy** - Implements industry-standard discovery with intelligent prioritization
- **Web App Manifest Support** - Parses `/manifest.json` files for optimal logo selection
- **Advanced Scoring System** - Prioritizes SVG > PNG > WebP > ICO with size, context, and quality scoring
- **Multi-Source Discovery** - Apple Touch icons, Open Graph images, standard favicons, and fallback locations
- **Quality Validation** - Aspect ratio checking, size validation, and quality assessment
- **Async-Only Design** - Built with `httpx` and `asyncio` for high-performance non-blocking I/O
- **Fast HTML Parsing** - Uses `selectolax` for optimal performance
- **Modern Image Processing** - PIL with LANCZOS resampling and format conversion

## Installation

```bash
pip install logo-hunter
```

Or install from source:

```bash
git clone <repository-url>
cd logohunter
pip install -e .
```

## Quick Start

```python
import asyncio
from logo_hunter import LogoHunter

async def main():
    # Get a logo as PNG bytes with comprehensive discovery
    logo_bytes = await LogoHunter.get_customer_logo(
        "github.com", 
        output_format="PNG", 
        resize_to=(128, 128)
    )
    
    if logo_bytes:
        with open("github_logo.png", "wb") as f:
            f.write(logo_bytes)
        print("Logo saved!")
    else:
        print("No logo found")

asyncio.run(main())
```

## Discovery Strategy

LogoHunter implements a comprehensive logo discovery strategy prioritizing:

### 1. Web App Manifest (`/manifest.json`)
- Checks `icons` array for largest/SVG icons
- Prioritizes `"purpose": "any"` or `"maskable"`
- SVG format preferred for infinite scaling

### 2. Apple Touch Icons
- `<link rel="apple-touch-icon">` with sizes parsing
- Default 180x180 if no size specified
- Checks precomposed variants

### 3. Open Graph / Social Media Tags
- `<meta property="og:image">` (Facebook)
- `<meta name="twitter:image">` (Twitter/X)
- Often larger branded images (1200x630 typical)

### 4. Standard Favicon Declarations
- `<link rel="icon" type="image/svg+xml">` (preferred - vector)
- `<link rel="icon" sizes="...">` (all sizes, largest selected)
- Supports 512x512, 256x256, 192x192, 96x96, 48x48, 32x32, 16x16

### 5. Logo Class/ID Detection
- Searches for `<img>` tags within elements containing logo-related class or ID names
- Patterns: "logo", "icon", "brand", "header-logo", "site-logo", "company-logo", "navbar-brand"
- Example: `<div class="header-logo"><img src="/logo.png"></div>`
- High priority scoring for explicit logo identification

### 6. Logo Keyword Detection
- Searches all `<img>` elements for "logo" keyword in multiple attributes:
  - **Filename**: `/company-logo.png`, `/brand-logo.svg`
  - **Class attribute**: `<img class="site-logo-img">`
  - **ID attribute**: `<img id="main-logo">`
  - **Alt text**: `<img alt="Company logo">`
- Upgrades context from logo-class if same image found via both methods
- Very high priority scoring for explicit logo identification

### 7. Common File Location Fallbacks
- `/favicon.svg`, `/logo.svg`, `/icon.svg`
- `/favicon-512x512.png`
- `/favicon.ico` (last resort, often multi-resolution)

## Advanced Usage

### Step-by-step Processing

```python
import asyncio
from logo_hunter import LogoHunter

async def detailed_example():
    domain = "python.org"
    
    # Step 1: Find all logo URLs (scored and prioritized)
    logo_urls = await LogoHunter.find_logo_urls(domain)
    print(f"Found {len(logo_urls)} logo URLs")
    
    # Step 2: Fetch and validate the best quality logo
    best_logo = await LogoHunter.fetch_best_logo(logo_urls)
    
    if best_logo:
        # Step 3: Process the image with modern resampling
        processed_bytes = LogoHunter.process_image(
            best_logo,
            output_format="PNG",
            resize_to=(256, 256)
        )
        
        with open(f"{domain}_logo.png", "wb") as f:
            f.write(processed_bytes)

asyncio.run(detailed_example())
```

### Concurrent Batch Processing

```python
import asyncio
from logo_hunter import LogoHunter

async def batch_process():
    domains = ["github.com", "stackoverflow.com", "python.org", "microsoft.com"]
    
    # Process all domains concurrently with comprehensive discovery
    tasks = [
        LogoHunter.get_customer_logo(domain, resize_to=(128, 128))
        for domain in domains
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for domain, result in zip(domains, results):
        if isinstance(result, Exception):
            print(f"Error processing {domain}: {result}")
        elif result:
            with open(f"{domain.replace('.', '_')}_logo.png", "wb") as f:
                f.write(result)
            print(f"Saved high-quality logo for {domain}")

asyncio.run(batch_process())
```

## API Reference

### LogoHunter

#### `await LogoHunter.get_customer_logo(domain, output_format="PNG", resize_to=None, logger=None)`

Main async method to discover and process a logo with comprehensive strategy.

- **domain**: Domain name (e.g., "github.com")
- **output_format**: "PNG", "JPEG", "WEBP", etc.
- **resize_to**: Tuple (width, height) for resizing
- **logger**: Optional custom logger for controlling output (defaults to module logger)
- **Returns**: Logo bytes or None

#### `await LogoHunter.find_logo_urls(domain)`

Discover all available logo URLs using comprehensive strategy with scoring.

- **domain**: Domain name to search
- **Returns**: List of scored and prioritized logo URLs

#### `await LogoHunter.fetch_best_logo(logo_urls)`

Fetch and validate the highest quality logo from URL list.

- **logo_urls**: List of URLs to fetch (pre-sorted by score)
- **Returns**: PIL Image object or None after validation

#### `LogoHunter.process_image(image, output_format="PNG", resize_to=None)`

Process a PIL Image with modern resampling (static method).

- **image**: PIL Image object
- **output_format**: Target format ("PNG", "JPEG", etc.)
- **resize_to**: Tuple (width, height) for thumbnail resizing
- **Returns**: Processed image bytes

## Logging Control

The library provides detailed logging at INFO level for discovery results and DEBUG level for detailed processing steps:

### Default Logging Behavior
- **INFO**: Number of logos found, list of all discovered URLs with scores, selected logo
- **DEBUG**: Individual discovery steps, validation details, error details

### Custom Logger Usage
```python
import logging
from logo_hunter import LogoHunter

# Create custom logger
logger = logging.getLogger("my_app")
logger.setLevel(logging.INFO)

# Use with custom logger
logo_bytes = await LogoHunter.get_customer_logo(
    "github.com", 
    logger=logger
)
```

### Example Log Output
```
INFO: Found 5 potential logos for github.com:
INFO:   1. https://github.com/apple-touch-icon.png (score: 1650, apple-touch)
INFO:   2. https://github.com/favicon.svg (score: 11000, favicon)  
INFO:   3. https://github.com/logo.png (score: 2560, favicon)
INFO: Selected logo: https://github.com/favicon.svg
```

## Scoring System

The library uses a comprehensive scoring system:

### Format Priority
- **SVG**: 1000 points (infinite scaling)
- **PNG**: 500 points (lossless)
- **WebP**: 400 points (modern, efficient)
- **ICO**: 100 points (legacy)
- **JPEG**: 50 points (lossy, rarely used for logos)

### Context Bonuses
- **Manifest icon**: +200 (explicit declaration)
- **Apple touch icon**: +150 (designed for visibility)  
- **Logo keyword**: +130 (explicit "logo" in img attributes)
- **Logo class/ID**: +125 (explicit logo element identification)
- **Standard favicon**: +100 (rel="icon")
- **Social media image**: +50 (might be promotional)
- **Fallback locations**: +25 (common file paths)

### Quality Penalties
- **Bad aspect ratio** (not square): -1000
- **Very small** (<32px): -100
- **Generic filenames**: -50
- **Wide social images**: -300

## Performance Features

- **Async-only design** for optimal I/O performance
- **Comprehensive validation** with fallback cascade
- **Connection pooling** via httpx AsyncClient
- **Concurrent discovery** with semaphore limits
- **Modern image processing** with LANCZOS resampling
- **Fast HTML parsing** with selectolax
- **Smart caching** and deduplication
- **Timeout handling** for reliable operation

## Error Handling

The library is designed to be resilient:

- Network errors are logged but don't crash the application
- Invalid images are skipped automatically
- Missing logos return `None` rather than raising exceptions
- Malformed HTML is handled gracefully

## Migration from v1.x

If you're upgrading from the previous version, the API has been modernized:

### New Code (v2.x)
```python
# Async (recommended)
logo_bytes = await LogoHunter.get_customer_logo("example.com")

# Or sync (for backward compatibility)
logo_bytes = SyncLogoHunter.get_customer_logo("example.com")
```

## Requirements

- Python 3.8+
- httpx >= 0.24.1
- selectolax >= 0.3.29
- Pillow >= 9.5.0

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.

## Changelog

### v2.0.0
- **Breaking**: Async-first API design
- **New**: httpx replaces requests for better async support
- **New**: selectolax for fast HTML parsing
- **New**: Concurrent logo fetching
- **New**: Better error handling and logging
- **New**: Type hints throughout
- **Added**: Backward compatibility via SyncLogoHunter