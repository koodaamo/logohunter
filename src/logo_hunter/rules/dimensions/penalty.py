"""Dimensions-based penalty scoring rules for logo detection."""

from PIL import Image


def very_small_images(
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
    """Apply penalty for very small images (likely not useful logos)"""
    if not width or not height:
        return 0

    max_dimension = max(width, height)

    if max_dimension < 16:
        return 1.0  # Extremely small
    elif max_dimension < 24:
        return 0.67  # Very small
    elif max_dimension < 32:
        return 0.33  # Small but might be acceptable

    return False


def extremely_wide_aspect_ratio(
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
    """Apply penalty for extremely wide or tall images (unlikely to be logos)"""
    if not width or not height:
        return 0

    aspect_ratio = max(width, height) / min(width, height)

    if aspect_ratio > 8.0:
        return 1.0  # Extremely wide/tall
    elif aspect_ratio > 6.0:
        return 0.75  # Very wide/tall
    elif aspect_ratio > 5.0:
        return 0.5  # Quite wide/tall

    return False


def social_media_dimensions(
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
    """Apply penalty for typical social media preview image dimensions"""
    if not width or not height:
        return 0

    # Common social media image dimensions that are NOT logos
    social_dimensions = [
        (1200, 630),  # Facebook Open Graph
        (1200, 628),  # Twitter summary card with large image
        (1024, 512),  # Twitter summary card
        (1200, 675),  # LinkedIn
        (1080, 1080),  # Instagram square (but could be logo)
        (1080, 1920),  # Instagram story
        (1200, 1200),  # Facebook square
    ]

    for social_w, social_h in social_dimensions:
        # Check if dimensions match social media standards (with tolerance)
        w_tolerance = social_w * 0.05
        h_tolerance = social_h * 0.05

        if (
            abs(width - social_w) <= w_tolerance
            and abs(height - social_h) <= h_tolerance
        ):
            # Extra penalty if aspect ratio is very wide (typical for social previews)
            aspect_ratio = max(width, height) / min(width, height)
            if aspect_ratio > 1.5:
                return 1.0
            else:
                return 0.33  # Square social images might still be logos

    return False


def banner_dimensions(
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
    """Apply penalty for typical banner/advertisement dimensions"""
    if not width or not height:
        return 0

    # Common banner dimensions
    banner_dimensions = [
        (728, 90),  # Leaderboard
        (300, 250),  # Medium Rectangle
        (336, 280),  # Large Rectangle
        (320, 50),  # Mobile Banner
        (468, 60),  # Banner
        (234, 60),  # Half Banner
        (120, 600),  # Skyscraper
        (160, 600),  # Wide Skyscraper
        (300, 600),  # Half Page Ad
    ]

    for banner_w, banner_h in banner_dimensions:
        # Check if dimensions match banner standards (with tolerance)
        w_tolerance = max(5, banner_w * 0.1)
        h_tolerance = max(5, banner_h * 0.1)

        if (
            abs(width - banner_w) <= w_tolerance
            and abs(height - banner_h) <= h_tolerance
        ):
            return True

    return False


def odd_dimensions(
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
    """Apply small penalty for unusual/odd dimensions"""
    if not width or not height:
        return 0

    # Check for prime numbers or other unusual dimensions
    def is_odd_dimension(n):
        # Penalize dimensions that are prime numbers > 100
        # or very specific numbers that suggest generated content
        if n > 100:
            for i in range(2, int(n**0.5) + 1):
                if n % i == 0:
                    return False
            return True  # It's prime
        return False

    penalty = 0

    if is_odd_dimension(width) or is_odd_dimension(height):
        penalty += 0.5

    # Penalize very specific dimensions that suggest auto-generated thumbnails
    if width == 150 and height == 150:
        penalty += 1.0
    elif (width, height) in [(120, 120), (240, 240), (360, 360)]:
        penalty += 0.75

    return penalty if penalty > 0 else False
