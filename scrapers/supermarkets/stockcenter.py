import urllib.parse
from typing import List, Optional
from ..base import BaseScraper, ProductItem

class StockCenterScraper(BaseScraper):
    """
    Scraper para Stock Center (Comercial Zaffari - RS/SC).
    O Stock Center não possui e-commerce aberto com carrinho.
    Retorna lista vazia sem inventar preços ou links fictícios.
    """

    def __init__(self):
        super().__init__(store_name="Stock Center", store_type="supermarket")

    def search(self, query: str, limit: int = 10, city: Optional[str] = None, uf: Optional[str] = "RS", **kwargs) -> List[ProductItem]:
        # Sem e-commerce de venda direta online, não alucina preços
        return []
