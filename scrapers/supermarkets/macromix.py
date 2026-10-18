import urllib.parse
from typing import List, Optional
from ..base import BaseScraper, ProductItem

class MacromixScraper(BaseScraper):
    """
    Scraper para Macromix Atacado (Grupo Unidasul - RS).
    O Macromix opera como loja física com tabloides promocionais locais.
    Quando não há oferta online indexada diretamente, retorna lista vazia sem alucinação.
    """

    def __init__(self):
        super().__init__(store_name="Macromix Atacado", store_type="supermarket")

    def search(self, query: str, limit: int = 10, city: Optional[str] = None, uf: Optional[str] = "RS", **kwargs) -> List[ProductItem]:
        # Sem catálogo de e-commerce direto ativo, não gera dados fictícios.
        return []
