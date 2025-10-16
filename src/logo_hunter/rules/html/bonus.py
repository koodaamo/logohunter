"""HTML-based bonus scoring rules for logo detection."""

from PIL import Image
from urllib.parse import urlparse


def logo_in_filename(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> bool:
    """Award bonus for 'logo' keyword in filename"""
    filename = urlparse(url).path.lower()
    return "logo" in filename


def logo_in_alt_text(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> bool:
    """Award bonus for 'logo' keyword in alt text"""
    return alt_text and "logo" in alt_text.lower()


def logo_in_css_classes(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> bool:
    """Award bonus for 'logo' keyword in CSS classes"""
    return css_classes and "logo" in css_classes.lower()


def logo_in_element_id(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> bool:
    """Award bonus for 'logo' keyword in element ID"""
    return element_id and "logo" in element_id.lower()


def brand_keywords(
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
    """Award bonus for brand-related keywords in attributes"""
    keywords = ["brand", "icon", "header-logo", "site-logo", "company-logo"]
    matches = 0

    # Check filename
    filename = urlparse(url).path.lower()
    for keyword in keywords:
        if keyword in filename:
            matches += 1
            break

    # Check alt text
    if alt_text:
        alt_lower = alt_text.lower()
        for keyword in keywords:
            if keyword in alt_lower:
                matches += 1
                break

    # Check CSS classes
    if css_classes:
        classes_lower = css_classes.lower()
        for keyword in keywords:
            if keyword in classes_lower:
                matches += 1
                break

    # Check element ID
    if element_id:
        id_lower = element_id.lower()
        for keyword in keywords:
            if keyword in id_lower:
                matches += 1
                break

    return matches


def parent_logo_context(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> bool:
    """Award bonus for logo-related classes in parent elements"""
    logo_patterns = ["logo", "brand", "header", "navbar", "nav", "masthead", "banner"]

    for parent_class_string in parent_classes:
        if parent_class_string:
            parent_lower = parent_class_string.lower()
            for pattern in logo_patterns:
                if pattern in parent_lower:
                    return True

    return False


def header_proximity(
    img: Image.Image,
    width: int,
    height: int,
    url: str,
    alt_text: str,
    css_classes: str,
    element_id: str,
    parent_classes: list[str],
    **kwargs,
) -> float:
    """Award bonus for images near top of DOM hierarchy"""
    # Award bonus based on DOM depth (fewer parents = higher in DOM)
    depth = len(parent_classes)

    if depth <= 3:
        return 1.0  # Very close to top
    elif depth <= 5:
        return 0.67  # Reasonably close to top
    elif depth <= 8:
        return 0.33  # Moderate depth
    else:
        return 0  # Too deep in DOM
