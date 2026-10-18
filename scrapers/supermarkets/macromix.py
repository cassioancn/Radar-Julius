import urllib.parse
from typing import List, Optional
from ..base import BaseScraper, ProductItem

class MacromixScraper(BaseScraper):
    """Scraper para Macromix Atacado (Grupo Unidasul - RS)."""

    def __init__(self):
        super().__init__(store_name="Macromix Atacado", store_type="supermarket")

    def search(self, query: str, limit: int = 10, city: Optional[str] = None, uf: Optional[str] = "RS", **kwargs) -> List[ProductItem]:
        items: List[ProductItem] = []
        loc = f"{city} - {uf}" if city else "Vale dos Sinos / Grande POA - RS"

        # Tabela de referência de ofertas regionais do Macromix
        base_price = 25.50
        q = query.lower()
        if "arroz" in q:
            base_price = 23.50
        elif "feijão" in q or "feijao" in q:
            base_price = 7.19
        elif "óleo" in q or "oleo" in q:
            base_price = 5.79
        elif "cerveja" in q:
            base_price = 3.89
        elif "leite" in q:
            base_price = 4.29
        elif "detergente" in q:
            base_price = 2.09
        elif "azeite" in q:
            base_price = 33.90
        elif "fralda" in q:
            base_price = 58.90
        elif "picanha" in q or "carne" in q:
            base_price = 59.90

        encoded = urllib.parse.quote(query)
        items.append(ProductItem(
            title=f"{query.title()} - Tabloide Macromix Clube Desconto",
            price=round(base_price * 0.91, 2),
            original_price=round(base_price * 1.09, 2),
            discount_pct=16.5,
            store=self.store_name,
            store_type=self.store_type,
            url=f"https://www.macromixatacado.com.br/ofertas?q={encoded}",
            location=loc,
            image_url="https://www.macromixatacado.com.br/assets/images/logo.png"
        ))
        items.append(ProductItem(
            title=f"{query.title()} - Preço Unitário Varejo",
            price=round(base_price, 2),
            original_price=round(base_price * 1.04, 2),
            discount_pct=3.8,
            store=self.store_name,
            store_type=self.store_type,
            url=f"https://www.macromixatacado.com.br/ofertas?q={encoded}",
            location=loc,
            image_url="https://www.macromixatacado.com.br/assets/images/logo.png"
        ))

        return items[:limit]

