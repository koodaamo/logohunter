"""HTML-based penalty scoring rules for logo detection."""

import re
from PIL import Image
from urllib.parse import urlparse


def social_media_context(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> int:
    """Apply penalty for social media preview images"""
    social_keywords = ["og:image", "twitter:image", "social", "share", "preview"]

    # Check if this looks like a social media image
    filename = urlparse(url).path.lower()

    # Check filename for social indicators
    for keyword in social_keywords:
        if keyword in filename:
            return True

    # Check alt text
    if alt_text:
        alt_lower = alt_text.lower()
        for keyword in social_keywords:
            if keyword in alt_lower:
                return True

    # Check CSS classes
    if css_classes:
        classes_lower = css_classes.lower()
        for keyword in social_keywords:
            if keyword in classes_lower:
                return True

    return False


def generic_image_names(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> int:
    """Apply penalty for generic image filenames"""
    generic_names = [
        "pic",
        "photo",
        "picture",
        "default",
        "placeholder",
    ]

    filename = urlparse(url).path.lower()

    for generic in generic_names:
        if generic in filename:
            return True

    return False


def deep_dom_nesting(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> int:
    """Apply penalty for images deeply nested in DOM"""
    depth = len(parent_classes)

    if depth > 15:
        return 1.0  # Very deeply nested
    elif depth > 12:
        return 0.5  # Quite deep
    elif depth > 10:
        return 0.25  # Moderately deep

    return False


def content_area_context(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> int:
    """Apply penalty for images in content areas"""
    content_patterns = ["content", "article", "post", "blog", "main", "body", "text"]

    for parent_class_string in parent_classes:
        if parent_class_string:
            parent_lower = parent_class_string.lower()
            for pattern in content_patterns:
                if pattern in parent_lower:
                    return True

    return False


def advertisement_context(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> int:
    """Apply penalty for advertisement-related images"""
    ad_patterns = ["advertisement", "banner", "promo", "sponsor", "affiliate"]

    # Check filename
    filename = urlparse(url).path.lower()
    for pattern in ad_patterns:
        if pattern in filename:
            return True

    # Check alt text
    if alt_text:
        alt_lower = alt_text.lower()
        for pattern in ad_patterns:
            if pattern in alt_lower:
                return True

    # Check CSS classes
    if css_classes:
        classes_lower = css_classes.lower()
        for pattern in ad_patterns:
            if pattern in classes_lower:
                return True

    # Check parent classes
    for parent_class_string in parent_classes:
        if parent_class_string:
            parent_lower = parent_class_string.lower()
            for pattern in ad_patterns:
                if pattern in parent_lower:
                    return True

    return False


def single_color_svg(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> int:
    """Apply penalty for SVG images that only use a single color (especially white/black)"""
    # Only check if this is an SVG
    if not url.lower().endswith(".svg") and "svg" not in url.lower():
        return False

    # Get the SVG content if it's available in kwargs
    svg_content = kwargs.get("svg_content", "")
    if not svg_content:
        return False

    import re

    # Extract all color values from the SVG
    color_patterns = [
        r"fill\s*:\s*([^;}\s]+)",  # CSS fill: color
        r'fill\s*=\s*"([^"]+)"',  # attribute fill="color"
        r"stroke\s*:\s*([^;}\s]+)",  # CSS stroke: color
        r'stroke\s*=\s*"([^"]+)"',  # attribute stroke="color"
        r"color\s*:\s*([^;}\s]+)",  # CSS color: value
        r"stop-color\s*:\s*([^;}\s]+)",  # gradient stop-color
    ]

    colors = set()

    for pattern in color_patterns:
        matches = re.findall(pattern, svg_content, re.IGNORECASE)
        for match in matches:
            color = match.strip().lower()
            # Skip 'none' and 'transparent'
            if color not in ["none", "transparent", "inherit", "currentcolor"]:
                colors.add(color)

    # Convert common color names and hex values to normalized form
    normalized_colors = set()
    for color in colors:
        if color == "#fff" or color == "#ffffff" or color == "white":
            normalized_colors.add("white")
        elif color == "#000" or color == "#000000" or color == "black":
            normalized_colors.add("black")
        elif color.startswith("#"):
            normalized_colors.add(color)
        else:
            normalized_colors.add(color)

    # If only one color is used, apply penalty
    if len(normalized_colors) <= 1:
        # Extra penalty for white-only (common issue - won't show on white backgrounds)
        if "white" in normalized_colors or "#fff" in colors or "#ffffff" in colors:
            return 1.0  # Maximum penalty for white-only
        # Regular penalty for any other single color
        return 0.75

    return False
