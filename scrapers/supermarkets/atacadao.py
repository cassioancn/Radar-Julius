import urllib.parse
from typing import List, Optional
import requests
from ..base import BaseScraper, ProductItem

class AtacadaoScraper(BaseScraper):
    """Scraper com integração à API oficial VTEX do Atacadão (dados 100% reais em tempo real)."""

    def __init__(self):
        super().__init__(store_name="Atacadão", store_type="supermarket")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9"
        })

    def search(self, query: str, limit: int = 10, city: Optional[str] = None, uf: Optional[str] = None, **kwargs) -> List[ProductItem]:
        items: List[ProductItem] = []
        location_label = f"{city} - {uf}" if city and uf else (city or uf or "Unidade Regional")

        encoded = urllib.parse.quote(query)
        url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search?ft={encoded}"

        try:
            resp = self.session.get(url, timeout=7)
            if resp.status_code in [200, 206]:
                data = resp.json()
                if isinstance(data, list):
                    for p in data[:limit * 2]:
                        name = p.get("productName")
                        link = p.get("link")
                        prod_items = p.get("items", [])
                        
                        if not name or not prod_items:
                            continue

                        price = None
                        orig_price = None
                        sellers = prod_items[0].get("sellers", [])
                        if sellers:
                            comm = sellers[0].get("commertialOffer", {})
                            price = comm.get("Price")
                            orig_price = comm.get("ListPrice")

                        if not price or float(price) <= 0:
                            continue

                        # Imagem real do produto
                        images = prod_items[0].get("images", [])
                        img_url = images[0].get("imageUrl") if images else ""

                        # Converte link interno seguro para a URL pública real da página do produto
                        public_link = link.replace("secure.atacadao.com.br", "www.atacadao.com.br") if link else ""
                        if not public_link and p.get("linkText"):
                            public_link = f"https://www.atacadao.com.br/{p['linkText']}/p"

                        price_val = round(float(price), 2)
                        orig_val = round(float(orig_price), 2) if orig_price and float(orig_price) > price_val else None
                        disc_pct = round(((orig_val - price_val) / orig_val) * 100, 1) if orig_val else None

                        items.append(ProductItem(
                            title=name,
                            price=price_val,
                            original_price=orig_val,
                            discount_pct=disc_pct,
                            store=self.store_name,
                            store_type=self.store_type,
                            url=public_link,
                            image_url=img_url,
                            location=location_label
                        ))

                        if len(items) >= limit:
                            break
        except Exception:
            pass

        return items
