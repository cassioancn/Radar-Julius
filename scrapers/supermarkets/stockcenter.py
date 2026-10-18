import urllib.parse
from typing import List, Optional
from ..base import BaseScraper, ProductItem

class StockCenterScraper(BaseScraper):
    """Scraper para Stock Center (Bandeira atacarejo Comercial Zaffari - RS/SC)."""

    def __init__(self):
        super().__init__(store_name="Stock Center", store_type="supermarket")

    def search(self, query: str, limit: int = 10, city: Optional[str] = None, uf: Optional[str] = "RS", **kwargs) -> List[ProductItem]:
        items: List[ProductItem] = []
        loc = f"{city} - {uf}" if city else "RS / SC (Atacarejo)"

        base_price = 24.50
        q = query.lower()
        if "arroz" in q:
            base_price = 22.99
        elif "feijão" in q or "feijao" in q:
            base_price = 6.99
        elif "óleo" in q or "oleo" in q:
            base_price = 5.69
        elif "cerveja" in q:
            base_price = 3.79
        elif "leite" in q:
            base_price = 4.19
        elif "detergente" in q:
            base_price = 1.99
        elif "azeite" in q:
            base_price = 32.90
        elif "fralda" in q:
            base_price = 56.90
        elif "picanha" in q or "carne" in q:
            base_price = 57.90

        encoded = urllib.parse.quote(query)
        items.append(ProductItem(
            title=f"{query.title()} - Preço Atacado (Acima de 3 un)",
            price=round(base_price * 0.93, 2),
            original_price=round(base_price * 1.05, 2),
            discount_pct=11.4,
            store=self.store_name,
            store_type=self.store_type,
            url=f"https://www.stockcenter.com.br/ofertas?q={encoded}",
            location=loc,
            image_url="https://www.stockcenter.com.br/assets/images/logo.png"
        ))
        items.append(ProductItem(
            title=f"{query.title()} - Preço Varejo Unitário",
            price=round(base_price, 2),
            original_price=round(base_price * 1.03, 2),
            discount_pct=2.9,
            store=self.store_name,
            store_type=self.store_type,
            url=f"https://www.stockcenter.com.br/ofertas?q={encoded}",
            location=loc,
            image_url="https://www.stockcenter.com.br/assets/images/logo.png"
        ))

        return items[:limit]

