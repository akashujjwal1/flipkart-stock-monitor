import unittest
from unittest.mock import Mock, patch

import monitor


class CheckStockTests(unittest.TestCase):
    @patch("monitor.time.sleep")
    @patch("monitor.cloudscraper.create_scraper")
    def test_returns_unknown_after_all_request_attempts_fail(self, create_scraper, sleep):
        scraper = Mock()
        scraper.get.side_effect = TimeoutError("timed out")
        create_scraper.return_value = scraper

        result = monitor.check_stock("https://example.test/product", {})

        self.assertIsNone(result)
        self.assertEqual(scraper.get.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("monitor.cloudscraper.create_scraper")
    def test_detects_in_stock_when_request_succeeds(self, create_scraper):
        response = Mock(text="Add to Cart")
        scraper = Mock()
        scraper.get.return_value = response
        create_scraper.return_value = scraper

        result = monitor.check_stock("https://example.test/product", {})

        self.assertTrue(result)
        response.raise_for_status.assert_called_once_with()
