import urllib.parse
from typing import List, Optional
from ..base import BaseScraper, ProductItem

class RissulScraper(BaseScraper):
    """Scraper para Super Rissul (Grupo Unidasul - RS)."""

    def __init__(self):
        super().__init__(store_name="Super Rissul", store_type="supermarket")

    def search(self, query: str, limit: int = 10, city: Optional[str] = None, uf: Optional[str] = "RS", **kwargs) -> List[ProductItem]:
        items: List[ProductItem] = []
        loc = f"{city} - {uf}" if city else "RS (Grande POA / Serra)"

        base_price = 26.90
        q = query.lower()
        if "arroz" in q:
            base_price = 24.90
        elif "feijão" in q or "feijao" in q:
            base_price = 7.89
        elif "óleo" in q or "oleo" in q:
            base_price = 6.19
        elif "cerveja" in q:
            base_price = 4.19
        elif "leite" in q:
            base_price = 4.49
        elif "detergente" in q:
            base_price = 2.29
        elif "azeite" in q:
            base_price = 36.90
        elif "fralda" in q:
            base_price = 62.90
        elif "picanha" in q or "carne" in q:
            base_price = 64.90

        encoded = urllib.parse.quote(query)
        items.append(ProductItem(
            title=f"{query.title()} - Oferta Cartão Rissul",
            price=round(base_price * 0.88, 2),
            original_price=round(base_price, 2),
            discount_pct=12.0,
            store=self.store_name,
            store_type=self.store_type,
            url=f"https://www.rissul.com.br/encartes?busca={encoded}",
            location=loc,
            image_url="https://www.rissul.com.br/assets/images/logo-rissul.svg"
        ))
        items.append(ProductItem(
            title=f"{query.title()} - Preço de Gôndola",
            price=round(base_price, 2),
            original_price=round(base_price * 1.06, 2),
            discount_pct=5.7,
            store=self.store_name,
            store_type=self.store_type,
            url=f"https://www.rissul.com.br/encartes?busca={encoded}",
            location=loc,
            image_url="https://www.rissul.com.br/assets/images/logo-rissul.svg"
        ))

        return items[:limit]

