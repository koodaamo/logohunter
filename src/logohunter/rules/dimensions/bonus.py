"""Dimension-based bonus rules for logo scoring."""

from PIL import Image


def apple_touch_icon_sizes(
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
    """Award bonus for Apple Touch Icon and other standard large icon sizes"""
    if not width or not height:
        return 0

    # Standard Apple Touch Icon sizes and other common large icon sizes
    standard_sizes = [
        (128, 128),
        (152, 152),
        (167, 167),
        (180, 180),
        (192, 192),
        (256, 256),
        (512, 512),
    ]

    # Check if dimensions match any standard size exactly
    current_size = (width, height)
    if current_size in standard_sizes:
        return 1.0

    # Small tolerance for near-exact matches (±2 pixels)
    tolerance = 2
    for std_w, std_h in standard_sizes:
        if abs(width - std_w) <= tolerance and abs(height - std_h) <= tolerance:
            return 0.8

    return 0
