# Scrapers package
from .base import ProductItem, BaseScraper, parse_price_brl
from .manager import ScraperManager

__all__ = ["ProductItem", "BaseScraper", "parse_price_brl", "ScraperManager"]

