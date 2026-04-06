"""
Tests for crawler registry module
"""

import os
import sys
import pytest
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from crawler.registry import list_crawlers, is_valid_crawler, get_crawler_module


class TestCrawlerRegistry:
    """Test crawler registry functionality"""

    def test_list_crawlers_returns_list(self):
        """Test that list_crawlers returns a list"""
        crawlers = list_crawlers()
        assert isinstance(crawlers, list)

    def test_list_crawlers_has_valid_structure(self):
        """Test that list_crawlers returns properly structured data"""
        crawlers = list_crawlers()
        for crawler in crawlers:
            assert "name" in crawler
            assert "module" in crawler
            assert "description" in crawler
            assert crawler["name"].endswith(".py")
            assert crawler["module"].startswith("crawler.")

    def test_list_crawlers_finds_job51(self):
        """Test that job51_crawler.py is found"""
        crawlers = list_crawlers()
        names = [c["name"] for c in crawlers]
        assert "job51_crawler.py" in names

    def test_list_crawlers_finds_boss(self):
        """Test that boss_crawler.py is found"""
        crawlers = list_crawlers()
        names = [c["name"] for c in crawlers]
        assert "boss_crawler.py" in names

    def test_list_crawlers_excludes_non_crawlers(self):
        """Test that non-crawler files are excluded"""
        crawlers = list_crawlers()
        names = [c["name"] for c in crawlers]
        assert "checkpoint_manager.py" not in names
        assert "__init__.py" not in names
        assert "registry.py" not in names

    def test_is_valid_crawler_accepts_job51(self):
        """Test that job51_crawler.py is recognized as valid"""
        assert is_valid_crawler("job51_crawler.py") is True

    def test_is_valid_crawler_accepts_boss(self):
        """Test that boss_crawler.py is recognized as valid"""
        assert is_valid_crawler("boss_crawler.py") is True

    def test_is_valid_crawler_rejects_invalid(self):
        """Test that invalid scripts are rejected"""
        assert is_valid_crawler("checkpoint_manager.py") is False
        assert is_valid_crawler("__init__.py") is False
        assert is_valid_crawler("nonexistent.py") is False
        assert is_valid_crawler("") is False

    def test_is_valid_crawler_rejects_directory(self):
        """Test that directories are rejected"""
        assert is_valid_crawler("tests") is False

    def test_is_valid_crawler_rejects_no_run_crawler(self):
        """Test that files without run_crawler function are rejected"""
        assert is_valid_crawler("registry.py") is False


class TestGetCrawlerModule:
    """Test get_crawler_module function"""

    def test_get_crawler_module_returns_module(self):
        """Test that get_crawler_module returns a module object"""
        # This may fail if dependencies are not installed
        try:
            module = get_crawler_module("job51_crawler.py")
            assert module is not None
            assert hasattr(module, "__name__")
        except ImportError:
            # Dependencies not installed, skip this test
            pytest.skip("Dependencies not installed")

    def test_get_crawler_module_raises_on_invalid(self):
        """Test that get_crawler_module raises error for invalid scripts"""
        with pytest.raises(ValueError):
            get_crawler_module("nonexistent.py")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
