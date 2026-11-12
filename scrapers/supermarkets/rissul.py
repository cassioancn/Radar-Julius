from .vtex_base import VTEXSupermarketScraper


class RissulScraper(VTEXSupermarketScraper):
    """Scraper com integração à API VTEX regionalizada por CEP do Super Rissul (Grupo Unidasul - RS)."""

    def __init__(self):
        super().__init__(
            store_name="Super Rissul",
            base_url="https://www.rissul.com.br",
            default_fallback_label="RS (Grande POA / Serra)",
            allow_catalog_fallback=True,
            max_sellers_to_try=3
        )
