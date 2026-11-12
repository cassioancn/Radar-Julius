from typing import Any, Dict, Optional
from .vtex_base import VTEXSupermarketScraper


class AtacadaoScraper(VTEXSupermarketScraper):
    """Scraper com integração à API VTEX do Atacadão com validação regional por CEP."""

    def __init__(self):
        super().__init__(
            store_name="Atacadão",
            base_url="https://www.atacadao.com.br",
            default_fallback_label="Atacadão Online (Nacional)",
            allow_catalog_fallback=True,
            max_sellers_to_try=4
        )

    def _normalize_link(self, raw_link: Optional[str], product: Dict[str, Any]) -> str:
        link = super()._normalize_link(raw_link, product)
        if link:
            link = link.replace("secure.atacadao.com.br", "www.atacadao.com.br")
        return link
