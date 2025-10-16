import unittest
import asyncio
import json
import logging
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from logo_hunter.hunter import LogoHunter, Icon
from logo_hunter.scoring import get_scoring_engine
from io import BytesIO
from PIL import Image
import httpx


class TestAsyncLogoHunter(unittest.IsolatedAsyncioTestCase):
    """Test the async LogoHunter class."""

    def test_scoring_engine_loads_rules(self):
        """Test that the scoring engine loads rules correctly."""
        engine = get_scoring_engine()
        self.assertGreater(
            len(engine.rules), 0, "Should load at least some scoring rules"
        )

        # Check that rules have proper format
        for rule_func, rule_label in engine.rules:
            self.assertTrue(callable(rule_func), "Rule should be callable")
            self.assertIsInstance(rule_label, str, "Rule label should be string")
            self.assertTrue(len(rule_label) > 0, "Rule label should not be empty")

    def test_rule_based_scoring(self):
        """Test the new rule-based scoring system."""
        # Create a mock image for testing
        mock_image = Image.new("RGB", (100, 100), color="red")

        engine = get_scoring_engine()

        # Test with logo-friendly attributes
        score_good, details_good = engine.calculate_score(
            img=mock_image,
            width=100,
            height=100,
            url="https://example.com/logo.png",
            alt_text="Company logo",
            css_classes="logo site-logo",
            element_id="main-logo",
            parent_classes=["header", "navbar"],
        )

        # Test with non-logo attributes
        score_bad, details_bad = engine.calculate_score(
            img=mock_image,
            width=100,
            height=100,
            url="https://example.com/image123.jpg",
            alt_text="Random image",
            css_classes="content-image",
            element_id="img-123",
            parent_classes=["article", "content", "main", "body"],
        )

        # Logo-friendly attributes should score higher
        self.assertGreater(score_good, score_bad)
        self.assertGreater(len(details_good), 0, "Should have scoring details")
        self.assertGreater(len(details_bad), 0, "Should have scoring details")

    def test_aspect_ratio_scoring(self):
        """Test aspect ratio scoring rules."""
        engine = get_scoring_engine()

        # Square image (should get bonus)
        square_img = Image.new("RGB", (200, 200), color="red")
        square_score, _ = engine.calculate_score(
            img=square_img,
            width=200,
            height=200,
            url="https://example.com/square.png",
            alt_text="",
            css_classes="",
            element_id="",
            parent_classes=[],
        )

        # Very wide image (should get penalty)
        wide_img = Image.new("RGB", (800, 100), color="red")
        wide_score, _ = engine.calculate_score(
            img=wide_img,
            width=800,
            height=100,
            url="https://example.com/wide.png",
            alt_text="",
            css_classes="",
            element_id="",
            parent_classes=[],
        )

        # Square should score higher due to aspect ratio rules
        self.assertGreater(square_score, wide_score)

    @pytest.mark.asyncio
    async def test_check_manifest(self):
        """Test parsing Web App Manifest for icons."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock manifest response
            manifest_data = {
                "icons": [
                    {
                        "src": "/icon-192.png",
                        "sizes": "192x192",
                        "type": "image/png",
                        "purpose": "any",
                    },
                    {
                        "src": "/icon-512.png",
                        "sizes": "512x512",
                        "type": "image/png",
                        "purpose": "maskable",
                    },
                ]
            }

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = json.dumps(manifest_data)
            mock_response.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_response

            result = await LogoHunter._check_manifest(
                "example.com", mock_client, "https://example.com/manifest.json"
            )

            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 2)
            self.assertIsInstance(result[0], Icon)
            self.assertEqual(result[0].width, 192)
            self.assertEqual(result[0].height, 192)

    @pytest.mark.asyncio
    async def test_check_manifest_error(self):
        """Test manifest parsing with network error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock network error
            mock_client.get.side_effect = httpx.RequestError("Network error")

            result = await LogoHunter._check_manifest(
                "example.com", mock_client, "https://example.com/manifest.json"
            )

            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 0)

    @pytest.mark.asyncio
    async def test_get_fallback_icons(self):
        """Test getting fallback icons from common locations."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock successful responses for some fallbacks
            def mock_head(url, **kwargs):
                response = MagicMock()
                if "favicon.svg" in url:
                    response.status_code = 200
                    response.url = url
                elif "favicon.ico" in url:
                    response.status_code = 200
                    response.url = url
                else:
                    response.status_code = 404
                return response

            mock_client.head.side_effect = mock_head

            result = await LogoHunter._get_fallback_icons("example.com", mock_client)

            self.assertIsInstance(result, list)
            self.assertGreater(len(result), 0)

            # Should find favicon.svg and favicon.ico
            urls = [icon.url for icon in result]
            self.assertTrue(any("favicon.svg" in url for url in urls))
            self.assertTrue(any("favicon.ico" in url for url in urls))

    def test_extract_dimensions_from_sizes(self):
        """Test dimension extraction from sizes attribute."""
        element = MagicMock()
        element.attributes = {"sizes": "192x192 96x96 48x48"}

        width, height = LogoHunter._extract_dimensions(element)

        # Should return the largest size (192x192)
        self.assertEqual(width, 192)
        self.assertEqual(height, 192)

    def test_extract_dimensions_from_filename(self):
        """Test dimension extraction from filename."""
        element = MagicMock()
        element.attributes = {"href": "/favicon-256x256.png", "sizes": ""}

        width, height = LogoHunter._extract_dimensions(element)

        self.assertEqual(width, 256)
        self.assertEqual(height, 256)

    def test_extract_dimensions_no_info(self):
        """Test dimension extraction when no size info available."""
        element = MagicMock()
        element.attributes = {"href": "/favicon.png"}

        width, height = LogoHunter._extract_dimensions(element)

        self.assertEqual(width, 0)
        self.assertEqual(height, 0)

    async def test_find_icons_from_html(self):
        """Test HTML parsing for icons."""
        html_content = """
        <html>
            <head>
                <link rel="manifest" href="/manifest.json">
                <link rel="icon" type="image/svg+xml" href="/favicon.svg">
                <link rel="icon" href="/favicon.png" sizes="32x32">
                <link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180">
                <meta property="og:image" content="https://example.com/og-image.png">
                <meta name="twitter:image" content="https://example.com/twitter-image.png">
            </head>
        </html>
        """

        with patch.object(LogoHunter, "_check_manifest", return_value=[]):
            mock_client = AsyncMock()

            icons = await LogoHunter._find_icons_from_html(
                "example.com", html_content, mock_client
            )

            self.assertGreater(len(icons), 0)

            # Check URLs were converted to absolute
            urls = [icon.url for icon in icons]
            self.assertIn("https://example.com/favicon.svg", urls)
            self.assertIn("https://example.com/favicon.png", urls)
            self.assertIn("https://example.com/apple-touch-icon.png", urls)

    def test_validate_icon(self):
        """Test icon validation logic."""
        # Create LogoHunter instance for validation
        hunter = LogoHunter()

        # Valid square logo
        valid_icon = Icon("https://example.com/logo.png", 200, 200, "png")
        test_image = Image.new("RGB", (200, 200), color="red")

        self.assertTrue(hunter._validate_icon(valid_icon, test_image))

        # Too small
        small_icon = Icon("https://example.com/tiny.png", 10, 10, "png")
        small_image = Image.new("RGB", (10, 10), color="red")

        self.assertFalse(hunter._validate_icon(small_icon, small_image))

        # Bad aspect ratio
        wide_icon = Icon("https://example.com/banner.png", 600, 100, "png")
        wide_image = Image.new("RGB", (600, 100), color="red")

        self.assertFalse(hunter._validate_icon(wide_icon, wide_image))

    @pytest.mark.asyncio
    async def test_find_logo_urls_integration(self):
        """Test the complete find_logo_urls method."""
        html_content = """
        <html>
            <head>
                <link rel="icon" href="/favicon.ico" sizes="16x16">
                <meta property="og:image" content="/logo-large.png">
                <link rel="apple-touch-icon" href="/apple-touch-icon.png">
            </head>
        </html>
        """

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock HTML GET request
            html_response = MagicMock()
            html_response.status_code = 200
            html_response.text = html_content
            html_response.raise_for_status = MagicMock()
            mock_client.get.return_value = html_response

            # Mock fallback HEAD requests (some succeed, some fail)
            def mock_head(url, **kwargs):
                response = MagicMock()
                if "favicon.ico" in url:
                    response.status_code = 200
                    response.url = url
                else:
                    response.status_code = 404
                return response

            mock_client.head.side_effect = mock_head

            # Mock the scoring method to return simple scores
            hunter = LogoHunter()
            with patch.object(hunter, "_calculate_score_with_rules") as mock_score:
                mock_score.return_value = (100, [])

                urls = await hunter.find_logo_urls("example.com")

                self.assertIsInstance(urls, list)
                self.assertGreater(len(urls), 0)

                # Should return absolute URLs
                for url in urls:
                    self.assertTrue(url.startswith("http"))

    @pytest.mark.asyncio
    async def test_fetch_best_logo(self):
        """Test fetching and validating the best logo."""
        logo_urls = ["https://example.com/small.png", "https://example.com/large.png"]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock responses for different URLs
            def mock_get(url, **kwargs):
                response = MagicMock()
                response.status_code = 200
                response.headers = {"Content-Type": "image/png"}
                response.raise_for_status = MagicMock()

                if "large.png" in url:
                    # Create larger test image
                    img = Image.new("RGB", (256, 256), color="blue")
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    response.content = buf.getvalue()
                else:
                    # Create smaller test image
                    img = Image.new("RGB", (64, 64), color="red")
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    response.content = buf.getvalue()

                return response

            mock_client.get.side_effect = mock_get

            hunter = LogoHunter()
            best_logo = await hunter.fetch_best_logo(logo_urls)

            self.assertIsNotNone(best_logo)
            self.assertIsInstance(best_logo, Image.Image)

    @pytest.mark.asyncio
    async def test_fetch_best_logo_svg_skip(self):
        """Test that SVG images are skipped in current implementation."""
        logo_urls = ["https://example.com/logo.svg"]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock SVG response
            response = MagicMock()
            response.status_code = 200
            response.headers = {"Content-Type": "image/svg+xml"}
            response.raise_for_status = MagicMock()
            mock_client.get.return_value = response

            hunter = LogoHunter()
            best_logo = await hunter.fetch_best_logo(logo_urls)

            # Should be None since SVG processing is not implemented
            self.assertIsNone(best_logo)

    def test_process_image(self):
        """Test image processing."""
        # Create a test image
        test_image = Image.new("RGB", (100, 100), color="green")

        # Test PNG output
        hunter = LogoHunter()
        png_bytes = hunter.process_image(test_image, "PNG")
        self.assertIsInstance(png_bytes, bytes)
        self.assertGreater(len(png_bytes), 0)

        # Test JPEG output (should convert RGBA to RGB)
        rgba_image = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        jpeg_bytes = hunter.process_image(rgba_image, "JPEG")
        self.assertIsInstance(jpeg_bytes, bytes)
        self.assertGreater(len(jpeg_bytes), 0)

    def test_process_image_resize(self):
        """Test image resizing."""
        test_image = Image.new("RGB", (200, 200), color="blue")

        hunter = LogoHunter()
        resized_bytes = hunter.process_image(test_image, "PNG", resize_to=(50, 50))

        # Verify the resized image
        resized_image = Image.open(BytesIO(resized_bytes))
        self.assertEqual(resized_image.size, (50, 50))

    @pytest.mark.asyncio
    async def test_get_customer_logo_integration(self):
        """Test the main get_customer_logo method."""
        hunter = LogoHunter()
        with patch.object(hunter, "find_logo_urls") as mock_find:
            with patch.object(hunter, "fetch_best_logo") as mock_fetch:
                # Mock finding URLs
                mock_find.return_value = ["https://example.com/logo.png"]

                # Mock fetching logo
                test_image = Image.new("RGB", (100, 100), color="red")
                mock_fetch.return_value = test_image

                result = await hunter.get_customer_logo("example.com")

                self.assertIsNotNone(result)
                self.assertIsInstance(result, bytes)
                self.assertGreater(len(result), 0)

    @pytest.mark.asyncio
    async def test_get_customer_logo_with_custom_logger(self):
        """Test get_customer_logo with custom logger."""
        custom_logger = logging.getLogger("test_logger")
        hunter = LogoHunter()

        with patch.object(hunter, "find_logo_urls") as mock_find:
            with patch.object(hunter, "fetch_best_logo") as mock_fetch:
                # Mock finding URLs
                mock_find.return_value = ["https://example.com/logo.png"]

                # Mock fetching logo
                test_image = Image.new("RGB", (100, 100), color="red")
                mock_fetch.return_value = test_image

                result = await hunter.get_customer_logo(
                    "example.com", logger=custom_logger
                )

                self.assertIsNotNone(result)
                self.assertIsInstance(result, bytes)
                self.assertGreater(len(result), 0)

    @pytest.mark.asyncio
    async def test_get_customer_logo_no_urls(self):
        """Test get_customer_logo when no URLs are found."""
        hunter = LogoHunter()
        with patch.object(hunter, "find_logo_urls") as mock_find:
            mock_find.return_value = []

            result = await hunter.get_customer_logo("example.com")

            self.assertIsNone(result)

    @pytest.mark.asyncio
    async def test_find_logo_images_by_class_id(self):
        """Test finding logo images by class and ID patterns."""
        html_content = """
        <html>
            <head>
                <title>Test</title>
            </head>
            <body>
                <div class="header-logo">
                    <a href="/">
                        <img src="/company-logo.png" alt="Company logo" width="200" height="100">
                    </a>
                </div>
                <div id="site-logo">
                    <img src="/site-brand.svg" alt="Site brand" width="150" height="75">
                </div>
                <div class="navbar-brand">
                    <img src="/navbar-logo.jpg" alt="Nav logo">
                </div>
                <div class="content">
                    <img src="/random-image.png" alt="Random content">
                </div>
            </body>
        </html>
        """

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            hunter = LogoHunter()
            icons = await hunter._find_icons_from_html(
                "example.com", html_content, mock_client
            )

            # Should have found some logo-related icons
            self.assertGreater(len(icons), 0)

            # Check that logo-related images were found
            logo_urls = [icon.url for icon in icons]
            self.assertTrue(any("logo" in url for url in logo_urls))

            # Check that specific logo images were found
            self.assertIn("https://example.com/company-logo.png", logo_urls)
            self.assertIn("https://example.com/navbar-logo.jpg", logo_urls)
            self.assertIn("https://example.com/site-brand.svg", logo_urls)

            # Verify that non-logo images are not included
            self.assertNotIn("https://example.com/random-image.png", logo_urls)

    def test_new_scoring_system(self):
        """Test that the new rule-based scoring system works correctly."""
        engine = get_scoring_engine()

        # Create test image
        test_image = Image.new("RGB", (200, 200), color="red")

        # Logo-friendly attributes should score higher than generic ones
        logo_score, _ = engine.calculate_score(
            img=test_image,
            width=200,
            height=200,
            url="https://example.com/logo.png",
            alt_text="Company logo",
            css_classes="header-logo",
            element_id="site-logo",
            parent_classes=["header", "navbar"],
        )

        generic_score, _ = engine.calculate_score(
            img=test_image,
            width=200,
            height=200,
            url="https://example.com/image.png",
            alt_text="Some image",
            css_classes="content-image",
            element_id="img-1",
            parent_classes=["article", "content", "main", "body", "html"],
        )

        self.assertGreater(logo_score, generic_score)


if __name__ == "__main__":
    unittest.main()
