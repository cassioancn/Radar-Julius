from .vtex_base import VTEXSupermarketScraper


class ZaffariScraper(VTEXSupermarketScraper):
    """Scraper com integração à API VTEX regionalizada por CEP do Zaffari / Bourbon."""

    def __init__(self):
        super().__init__(
            store_name="Zaffari / Bourbon",
            base_url="https://www.zaffari.com.br",
            default_fallback_label="Zaffari / Bourbon (RS)",
            allow_catalog_fallback=True,
            max_sellers_to_try=3
        )
