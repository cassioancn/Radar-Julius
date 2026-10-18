from typing import List
from ..base import BaseScraper, ProductItem

class ShopeeScraper(BaseScraper):
    """
    Scraper para Shopee Brasil.
    Retorna apenas itens reais obtidos de requisições ativas.
    """

    def __init__(self):
        super().__init__(store_name="Shopee Brasil", store_type="retail")

    def search(self, query: str, limit: int = 10, **kwargs) -> List[ProductItem]:
        # Sem resposta válida ao vivo sem captcha, retorna lista vazia sem alucinação
        return []
