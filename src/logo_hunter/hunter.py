import asyncio
import json
import logging
import re
from io import BytesIO
from typing import NamedTuple
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image
from selectolax.parser import HTMLParser, Node

from .scoring import get_scoring_engine


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Icon(NamedTuple):
    """Represents a favicon/icon with its properties."""

    url: str
    width: int
    height: int
    format: str
    alt_text: str = ""
    css_classes: str = ""
    element_id: str = ""
    parent_classes: list[str] = []
    score: int = 0
    rule_details: list = []


class LogoHunter:
    """Async logo hunting class using httpx and selectolax."""

    # Discovery selectors in priority order with context
    LOGO_SELECTORS: list[tuple[str, str, str, int]] = [
        # (selector, attribute, context, base_score)
        ('link[rel="manifest"]', "href", "manifest", 200),
        ('link[rel="apple-touch-icon"]', "href", "apple-touch", 150),
        ('link[rel="apple-touch-icon-precomposed"]', "href", "apple-touch", 150),
        ('link[rel="icon"][type="image/svg+xml"]', "href", "favicon", 100),
        ('link[rel="icon"]', "href", "favicon", 100),
        ('link[rel="shortcut icon"]', "href", "favicon", 100),
        ('meta[property="og:image"]', "content", "social", 50),
        ('meta[name="og:image"]', "content", "social", 50),
        ('meta[name="twitter:image"]', "content", "social", 50),
        ('meta[name="msapplication-TileImage"]', "content", "favicon", 100),
    ]

    # Common fallback locations
    FALLBACK_LOCATIONS: list[str] = [
        "/favicon.svg",
        "/logo.svg",
        "/icon.svg",
        "/favicon-512x512.png",
        "/apple-touch-icon.png",
        "/apple-touch-icon-precomposed.png",
        "/favicon.ico",
    ]

    # Regex for extracting dimensions from filenames
    SIZE_REGEX: re.Pattern[str] = re.compile(
        r"(?P<width>\d{2,4})x(?P<height>\d{2,4})", flags=re.IGNORECASE
    )

    # Default headers to avoid bot detection
    DEFAULT_HEADERS: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    async def _calculate_score_with_rules(
        self, icon: Icon, client: httpx.AsyncClient
    ) -> tuple[int, list]:
        """Calculate score using rule-based scoring system."""
        try:
            # Load the image to get actual dimensions
            response = await client.get(icon.url, headers=self.DEFAULT_HEADERS)
            img_data = response.content

            # Handle SVG content specially
            svg_content = ""
            img = None
            actual_width = icon.width
            actual_height = icon.height

            content_type = response.headers.get("Content-Type", "")
            if "svg" in content_type:
                # For SVG, store content and use default dimensions
                svg_content = img_data.decode("utf-8")
                actual_width = icon.width or 100
                actual_height = icon.height or 100
            else:
                # For raster images, load with PIL
                img = Image.open(BytesIO(img_data))
                actual_width, actual_height = img.size

            # Use actual dimensions from image, fallback to HTML attributes
            width = actual_width if actual_width else icon.width
            height = actual_height if actual_height else icon.height

            scoring_engine = get_scoring_engine()
            score, rule_details = scoring_engine.calculate_score(
                img=img,
                width=width,
                height=height,
                url=icon.url,
                alt_text=icon.alt_text,
                css_classes=icon.css_classes,
                element_id=icon.element_id,
                parent_classes=icon.parent_classes,
                svg_content=svg_content,
            )

            logger.debug(
                f"Scored icon {icon.url}: {score} points from {len(rule_details)} rules"
            )
            return score, rule_details

        except Exception as e:
            logger.debug(f"Error scoring icon {icon.url}: {e}")
            # Fallback to basic scoring without image loading
            scoring_engine = get_scoring_engine()
            score, rule_details = scoring_engine.calculate_score(
                img=None,
                width=icon.width,
                height=icon.height,
                url=icon.url,
                alt_text=icon.alt_text,
                css_classes=icon.css_classes,
                element_id=icon.element_id,
                parent_classes=icon.parent_classes,
                svg_content="",
            )
            return score, rule_details

    @staticmethod
    def _get_parent_classes(element: Node) -> list[str]:
        """Extract class names from all parent elements up to document root."""
        parent_classes = []
        current = element.parent

        while current is not None:
            if hasattr(current, "attributes") and current.attributes:
                class_attr = current.attributes.get("class", "")
                if class_attr:
                    parent_classes.append(class_attr)
            current = current.parent

        return parent_classes

    @staticmethod
    async def _check_manifest(
        domain: str, client: httpx.AsyncClient, manifest_url: str
    ) -> list[Icon]:
        """Parse Web App Manifest for icons."""
        icons = []

        try:
            response = await client.get(manifest_url)
            response.raise_for_status()
            manifest = json.loads(response.text)

            manifest_icons = manifest.get("icons", [])
            for icon_info in manifest_icons:
                src = icon_info.get("src", "")
                if not src:
                    continue

                # Convert relative URLs to absolute
                if src.startswith("//"):
                    src = f"https:{src}"
                elif not src.startswith("http"):
                    src = urljoin(f"https://{domain}", src)

                # Get dimensions
                sizes = icon_info.get("sizes", "")
                width = height = 0

                if sizes and sizes.lower() != "any":
                    size_parts = sizes.split("x")
                    if len(size_parts) == 2:
                        try:
                            width = int(size_parts[0])
                            height = int(size_parts[1])
                        except ValueError:
                            pass

                # Get format from src
                parsed_url = urlparse(src)
                format_ext = (
                    parsed_url.path.split(".")[-1].lower()
                    if "." in parsed_url.path
                    else ""
                )

                # Check purpose (prioritize "any" or "maskable")
                purpose = icon_info.get("purpose", "any")
                # context_bonus = 250 if purpose in ["any", "maskable"] else 200

                icon = Icon(src, width, height, format_ext)
                icons.append(icon)

        except Exception as e:
            logger.debug(f"Failed to parse manifest {manifest_url}: {e}")

        return icons

    @staticmethod
    async def _get_fallback_icons(domain: str, client: httpx.AsyncClient) -> list[Icon]:
        """Check common fallback locations for icons."""
        icons = []
        base_url = f"https://{domain}"

        for path in LogoHunter.FALLBACK_LOCATIONS:
            try:
                url = urljoin(base_url, path)
                response = await client.head(url, follow_redirects=True)

                if response.status_code == 200:
                    # Extract format from path
                    format_ext = path.split(".")[-1].lower() if "." in path else ""

                    # Try to extract dimensions from filename
                    width = height = 0
                    match = LogoHunter.SIZE_REGEX.search(path)
                    if match:
                        try:
                            width = int(match.group("width"))
                            height = int(match.group("height"))
                        except ValueError:
                            pass

                    # Default sizes for known patterns
                    if "apple-touch-icon" in path and width == 0:
                        width = height = 180

                    icon = Icon(str(response.url), width, height, format_ext)
                    icons.append(icon)

            except Exception as e:
                url = urljoin(base_url, path)
                logger.debug(f"Fallback check failed for {url}: {e}")

        return icons

    @staticmethod
    def _extract_dimensions(element: Node) -> tuple[int, int]:
        """Extract width and height from element attributes or filename."""
        # Try to get dimensions from sizes attribute
        sizes = element.attributes.get("sizes", "")
        if sizes and sizes.lower() != "any":
            size_list = sizes.split(" ")

            # Sort by area (width * height) to get largest first
            def size_key(size_str):
                match = re.split(r"[x×]", size_str)
                if len(match) == 2:
                    try:
                        w = int("".join(c for c in match[0] if c.isdigit()))
                        h = int("".join(c for c in match[1] if c.isdigit()))
                        return w * h
                    except ValueError:
                        return 0
                return 0

            size_list.sort(key=size_key, reverse=True)
            if size_list:
                match = re.split(r"[x×]", size_list[0])
                if len(match) == 2:
                    try:
                        width = int("".join(c for c in match[0] if c.isdigit()))
                        height = int("".join(c for c in match[1] if c.isdigit()))
                        return width, height
                    except ValueError:
                        pass

        # Try to extract from href/content filename
        href = element.attributes.get("href", "") or element.attributes.get(
            "content", ""
        )
        if href:
            match = LogoHunter.SIZE_REGEX.search(href)
            if match:
                try:
                    width = int(match.group("width"))
                    height = int(match.group("height"))
                    return width, height
                except ValueError:
                    pass

        return 0, 0

    @staticmethod
    async def _find_icons_from_html(
        domain: str, html_content: str, client: httpx.AsyncClient
    ) -> list[Icon]:
        """Parse HTML and extract icon/logo URLs."""
        icons = []
        base_url = f"https://{domain}"

        try:
            tree = HTMLParser(html_content)

            # Check for manifest first
            manifest_links = tree.css('link[rel="manifest"]')
            for manifest_link in manifest_links:
                href = manifest_link.attributes.get("href", "")
                if href:
                    if href.startswith("//"):
                        manifest_url = f"https:{href}"
                    elif not href.startswith("http"):
                        manifest_url = urljoin(base_url, href)
                    else:
                        manifest_url = href

                    manifest_icons = await LogoHunter._check_manifest(
                        domain, client, manifest_url
                    )
                    icons.extend(manifest_icons)

            # Process other selectors
            for selector, attr, context, base_score in LogoHunter.LOGO_SELECTORS:
                if context == "manifest":  # Already handled above
                    continue

                elements = tree.css(selector)
                for element in elements:
                    href_value = element.attributes.get(attr, "")
                    if href_value is None:
                        continue
                    href = href_value.strip()

                    if not href or href.startswith("data:"):
                        continue

                    # Convert relative URLs to absolute
                    if href.startswith("//"):
                        href = f"https:{href}"
                    elif not href.startswith("http"):
                        href = urljoin(base_url, href)

                    # Extract dimensions
                    width, height = LogoHunter._extract_dimensions(element)

                    # Extract format from URL
                    parsed_url = urlparse(href)
                    format_ext = (
                        parsed_url.path.split(".")[-1].lower()
                        if "." in parsed_url.path
                        else ""
                    )

                    icon = Icon(href, width, height, format_ext)
                    icons.append(icon)
                    logger.debug(f"Found {context} icon: {href} ({width}x{height})")

            # Search for logo/icon images by class and ID patterns
            logo_icons = LogoHunter._find_logo_images_by_class_id(tree, base_url)
            icons.extend(logo_icons)

        except Exception as e:
            logger.error(f"HTML parsing failed for {domain}: {e}")

        return icons

    @staticmethod
    def _find_logo_images_by_class_id(tree: HTMLParser, base_url: str) -> list[Icon]:
        """Find logo images by searching for elements with logo/icon class/ID patterns."""
        icons = []
        found_data = {}  # Track URLs with their context to allow better context assignment

        # Logo/icon class and ID patterns for img element detection
        logo_patterns = [
            "logo",
            "icon",
            "brand",
            "header-logo",
            "site-logo",
            "company-logo",
            "navbar-brand",
            "logo-img",
            "brand-img",
            "site-icon",
        ]

        try:
            # Search for elements with logo-related class or ID attributes
            for pattern in logo_patterns:
                # Search by class
                elements_by_class = tree.css(f'[class*="{pattern}"]')
                # Search by ID
                elements_by_id = tree.css(f'[id*="{pattern}"]')

                all_elements = elements_by_class + elements_by_id

                for element in all_elements:
                    # Look for img tags within this element (including itself)
                    img_elements = []

                    # Check if the element itself is an img
                    if element.tag == "img":
                        img_elements.append(element)
                    else:
                        # Search for img tags within this element
                        img_elements.extend(element.css("img"))

                    for img in img_elements:
                        src = img.attributes.get("src", "")
                        if not src or src.startswith("data:"):
                            continue

                        # Convert relative URLs to absolute
                        if src.startswith("//"):
                            src = f"https:{src}"
                        elif not src.startswith("http"):
                            src = urljoin(base_url, src)

                        # Extract HTML attributes
                        alt_text = img.attributes.get("alt", "")
                        css_classes = img.attributes.get("class", "")
                        element_id = img.attributes.get("id", "")
                        parent_classes = LogoHunter._get_parent_classes(img)

                        # Extract dimensions from img attributes
                        width = height = 0
                        try:
                            if img.attributes.get("width"):
                                width = int(img.attributes.get("width", "0"))
                            if img.attributes.get("height"):
                                height = int(img.attributes.get("height", "0"))
                        except (ValueError, TypeError):
                            pass

                        # Extract format from URL
                        parsed_url = urlparse(src)
                        path_parts = parsed_url.path.split(".")
                        format_ext = ""
                        if len(path_parts) > 1:
                            format_ext = path_parts[-1].lower()
                        elif "svg" in src.lower():
                            format_ext = "svg"
                        elif any(
                            fmt in src.lower()
                            for fmt in ["png", "jpg", "jpeg", "webp", "gif"]
                        ):
                            for fmt in ["png", "jpg", "jpeg", "webp", "gif"]:
                                if fmt in src.lower():
                                    format_ext = fmt
                                    break

                        # Create icon with full HTML context
                        icon = Icon(
                            src,
                            width,
                            height,
                            format_ext,
                            alt_text,
                            css_classes,
                            element_id,
                            parent_classes,
                        )
                        icons.append(icon)

            # Also search for all img elements that have "logo" in their attributes
            logo_keyword_icons = LogoHunter._find_logo_images_by_keyword(
                tree, base_url, found_data
            )
            icons.extend(logo_keyword_icons)

        except Exception as e:
            logger.debug(f"Error in logo class/ID search: {e}")

        return icons

    @staticmethod
    def _find_logo_images_by_keyword(
        tree: HTMLParser, base_url: str, found_data: dict
    ) -> list[Icon]:
        """Find img elements that have 'logo' keyword in filename, class, id, or alt attributes."""
        icons = []

        try:
            # Find all img elements
            all_imgs = tree.css("img")

            for img in all_imgs:
                src = img.attributes.get("src", "")
                if not src or src.startswith("data:"):
                    continue

                # Convert relative URLs to absolute
                if src.startswith("//"):
                    src = f"https:{src}"
                elif not src.startswith("http"):
                    src = urljoin(base_url, src)

                # Extract HTML attributes
                alt_text = img.attributes.get("alt", "")
                css_classes = img.attributes.get("class", "")
                element_id = img.attributes.get("id", "")
                parent_classes = LogoHunter._get_parent_classes(img)

                # Check if 'logo' appears in various attributes
                has_logo_keyword = False
                logo_sources = []

                # Check filename
                if "logo" in src.lower():
                    has_logo_keyword = True
                    logo_sources.append("filename")

                # Check class attribute
                if css_classes and "logo" in css_classes.lower():
                    has_logo_keyword = True
                    logo_sources.append("class")

                # Check id attribute
                if element_id and "logo" in element_id.lower():
                    has_logo_keyword = True
                    logo_sources.append("id")

                # Check alt attribute
                if alt_text and "logo" in alt_text.lower():
                    has_logo_keyword = True
                    logo_sources.append("alt")

                if has_logo_keyword:
                    # Extract dimensions from img attributes
                    width = height = 0
                    try:
                        if img.attributes.get("width"):
                            width = int(img.attributes.get("width", "0"))
                        if img.attributes.get("height"):
                            height = int(img.attributes.get("height", "0"))
                    except (ValueError, TypeError):
                        pass

                    # Extract format from URL
                    parsed_url = urlparse(src)
                    path_parts = parsed_url.path.split(".")
                    format_ext = ""
                    if len(path_parts) > 1:
                        format_ext = path_parts[-1].lower()
                    elif "svg" in src.lower():
                        format_ext = "svg"
                    elif any(
                        fmt in src.lower()
                        for fmt in ["png", "jpg", "jpeg", "webp", "gif"]
                    ):
                        for fmt in ["png", "jpg", "jpeg", "webp", "gif"]:
                            if fmt in src.lower():
                                format_ext = fmt
                                break

                    # Create icon with full HTML context
                    icon = Icon(
                        src,
                        width,
                        height,
                        format_ext,
                        alt_text,
                        css_classes,
                        element_id,
                        parent_classes,
                    )
                    icons.append(icon)
                    logger.debug(
                        f"Found logo-keyword icon: {src} ({width}x{height}) via {', '.join(logo_sources)}"
                    )

        except Exception as e:
            logger.debug(f"Error in logo keyword search: {e}")

        return icons

    def _validate_icon(self, icon: Icon, image: Image.Image) -> bool:
        """Validate if the icon is suitable as a logo."""
        try:
            width, height = image.size
            logger.debug(f"Validating {icon.url}: {width}x{height}")

            # Check aspect ratio (logos should be roughly square)
            if width > 0 and height > 0:
                aspect_ratio = max(width, height) / min(width, height)
                if aspect_ratio > 2.0:  # Too wide/tall
                    logger.debug(
                        f"Rejecting {icon.url} - bad aspect ratio: {aspect_ratio} (>{2.0})"
                    )
                    return False

            # Check minimum size
            if max(width, height) < 16:
                logger.debug(f"Rejecting {icon.url} - too small: {width}x{height}")
                return False

            # Check file size for different formats
            if icon.format.lower() == "svg":
                # SVG files should be reasonable size
                logger.debug(f"Accepting SVG {icon.url}: {width}x{height}")
                return True  # We can't check size without downloading

            # For raster images, check reasonable size limits
            if width * height > 2048 * 2048:  # Very large images
                logger.debug(f"Rejecting {icon.url} - too large: {width}x{height}")
                return False

            logger.debug(f"Accepting {icon.url}: {width}x{height}")
            return True

        except Exception as e:
            logger.debug(f"Validation failed for {icon.url}: {e}")
            return False

    async def find_logo_urls(self, domain: str) -> list[str]:
        """Fetch known logo URLs using async HTTP requests and HTML parsing."""
        all_icons = []

        async with httpx.AsyncClient(
            headers=LogoHunter.DEFAULT_HEADERS, timeout=30.0, follow_redirects=True
        ) as client:
            # Fetch and parse HTML
            url = f"https://{domain}"
            try:
                response = await client.get(url)
                response.raise_for_status()

                html_icons = await self._find_icons_from_html(
                    domain, response.text, client
                )
                all_icons.extend(html_icons)

            except Exception as e:
                logger.error(f"Failed to fetch URL: {url}. Error: {e}")

            # Check fallback locations
            fallback_icons = await self._get_fallback_icons(domain, client)
            all_icons.extend(fallback_icons)

            # Remove duplicates based on URL
            unique_icons = list({icon.url: icon for icon in all_icons}.values())

            # Calculate scores using rule-based system
            scored_icons = []
            for icon in unique_icons:
                (
                    score,
                    rule_details,
                ) = await self._calculate_score_with_rules(icon, client)
                scored_icon = Icon(
                    icon.url,
                    icon.width,
                    icon.height,
                    icon.format,
                    icon.alt_text,
                    icon.css_classes,
                    icon.element_id,
                    icon.parent_classes,
                    score,
                    rule_details,
                )
                scored_icons.append(scored_icon)

        # Sort by score (highest first)
        sorted_icons = sorted(scored_icons, key=lambda i: i.score, reverse=True)

        logger.info(f"Found {len(sorted_icons)} potential logos for {domain}:")
        for i, icon in enumerate(sorted_icons, 1):
            logger.info(f"  {i}. {icon.url} (score: {icon.score})")

        return [icon.url for icon in sorted_icons]

    async def find_logo_candidates(self, domain: str) -> list[Icon]:
        """Fetch logo candidates with full Icon objects including scoring details."""
        all_icons = []

        async with httpx.AsyncClient(
            headers=LogoHunter.DEFAULT_HEADERS, timeout=30.0, follow_redirects=True
        ) as client:
            # Fetch and parse HTML
            url = f"https://{domain}"
            try:
                response = await client.get(url)
                response.raise_for_status()

                html_icons = await self._find_icons_from_html(
                    domain, response.text, client
                )
                all_icons.extend(html_icons)

            except Exception as e:
                logger.error(f"Failed to fetch URL: {url}. Error: {e}")

            # Check fallback locations
            fallback_icons = await self._get_fallback_icons(domain, client)
            all_icons.extend(fallback_icons)

            # Remove duplicates based on URL
            unique_icons = list({icon.url: icon for icon in all_icons}.values())

            # Calculate scores using rule-based system
            scored_icons = []
            for icon in unique_icons:
                (
                    score,
                    rule_details,
                ) = await self._calculate_score_with_rules(icon, client)
                scored_icon = Icon(
                    icon.url,
                    icon.width,
                    icon.height,
                    icon.format,
                    icon.alt_text,
                    icon.css_classes,
                    icon.element_id,
                    icon.parent_classes,
                    score,
                    rule_details,
                )
                scored_icons.append(scored_icon)

        # Sort by score (highest first)
        sorted_icons = sorted(scored_icons, key=lambda i: i.score, reverse=True)

        logger.info(f"Found {len(sorted_icons)} potential logos for {domain}:")
        for i, icon in enumerate(sorted_icons, 1):
            logger.info(f"  {i}. {icon.url} (score: {icon.score})")

        return sorted_icons

    async def fetch_best_logo(self, logo_urls: list[str]) -> Image.Image | str | None:
        """Fetch the best quality logo image with validation. Returns PIL Image for raster formats or string for SVG."""
        if not logo_urls:
            return None

        async with httpx.AsyncClient(
            headers=LogoHunter.DEFAULT_HEADERS, timeout=30.0, follow_redirects=True
        ) as client:
            # Process URLs in order (they're already sorted by score)
            semaphore = asyncio.Semaphore(3)  # Limit concurrent requests

            async def fetch_and_validate(
                logo_url: str,
            ) -> tuple[Image.Image | str, int] | None:
                async with semaphore:
                    try:
                        logger.debug(f"Fetching logo from {logo_url}")
                        response = await client.get(logo_url)
                        response.raise_for_status()

                        content_type = response.headers.get("Content-Type", "")
                        valid_types = [
                            "image/png",
                            "image/svg+xml",
                            "image/webp",
                            "image/x-icon",
                            "image/jpeg",
                            "image/jpg",
                            "image/gif",
                        ]

                        if any(t in content_type for t in valid_types):
                            try:
                                # Handle SVGs by returning the string content
                                if "svg" in content_type:
                                    logger.debug(f"Found SVG logo: {logo_url}")
                                    svg_content = response.content.decode("utf-8")
                                    # Return SVG string with high priority score
                                    return svg_content, 100000

                                image = Image.open(BytesIO(response.content))
                                size = image.size[0] * image.size[1]
                                logger.debug(
                                    f"Successfully loaded image: {logo_url} ({image.size})"
                                )
                                return image, size

                            except Exception as e:
                                logger.error(
                                    f"Failed to process image from {logo_url}: {e}"
                                )
                                return None
                        else:
                            logger.debug(
                                f"Skipping {logo_url} - unsupported content type: {content_type}"
                            )
                            return None

                    except Exception as e:
                        logger.error(f"Failed to fetch logo from {logo_url}: {e}")
                        return None

            # Try URLs in order until we find a good one (since they're pre-sorted)
            for i, url in enumerate(logo_urls):
                logger.debug(f"Trying candidate #{i + 1}: {url}")
                result = await fetch_and_validate(url)
                if result is not None:
                    image, _ = result
                    logger.info(f"Selected logo: {url} (candidate #{i + 1})")
                    return image
                else:
                    logger.debug(f"Candidate #{i + 1} failed validation")

            logger.warning("No suitable logo found after validation")
            return None

    @staticmethod
    def process_image(
        image: Image.Image | str,
        output_format: str = "PNG",
        resize_to: tuple[int, int] | None = None,
    ) -> bytes:
        """Process and optionally resize image, return as bytes in specified format.
        For SVG strings, returns the SVG content as bytes."""
        # Handle SVG string content
        if isinstance(image, str):
            # For SVG, just return the string as UTF-8 bytes
            return image.encode("utf-8")

        # Handle PIL Image objects
        # Resize if requested
        if resize_to:
            image = image.resize(resize_to, Image.Resampling.LANCZOS)

        # Save to byte buffer
        byte_arr = BytesIO()

        # Handle different output formats
        save_format = output_format.upper()
        if save_format == "JPG":
            save_format = "JPEG"

        # Convert RGBA to RGB for JPEG format
        if save_format == "JPEG" and image.mode in ("RGBA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(
                image, mask=image.split()[-1] if image.mode == "RGBA" else None
            )
            image = background

        image.save(byte_arr, format=save_format)
        return byte_arr.getvalue()

    async def get_customer_logo(
        self,
        customer_name_or_domain: str,
        output_format: str = "PNG",
        resize_to: tuple[int, int] | None = None,
        logger: logging.Logger | None = None,
    ) -> bytes | None:
        """Main async function to retrieve and process the customer's logo."""
        # Use provided logger or fall back to module logger
        log = logger or globals()["logger"]

        # Temporarily store the original logger for internal methods
        original_logger = globals()["logger"]
        globals()["logger"] = log

        try:
            logo_urls = await self.find_logo_urls(customer_name_or_domain)

            if not logo_urls:
                log.debug("No logo URLs found")
                return None

            best_logo = await self.fetch_best_logo(logo_urls)

            if not best_logo:
                log.debug("No suitable logo found")
                return None

            return LogoHunter.process_image(
                best_logo, output_format=output_format, resize_to=resize_to
            )
        finally:
            # Restore original logger
            globals()["logger"] = original_logger
