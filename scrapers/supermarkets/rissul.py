import urllib.parse
from typing import List, Optional
import requests
from ..base import BaseScraper, ProductItem

class RissulScraper(BaseScraper):
    """Scraper com integração à API oficial VTEX do Super Rissul (Grupo Unidasul - RS)."""

    def __init__(self):
        super().__init__(store_name="Super Rissul", store_type="supermarket")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9"
        })

    def search(self, query: str, limit: int = 10, city: Optional[str] = None, uf: Optional[str] = "RS", **kwargs) -> List[ProductItem]:
        items: List[ProductItem] = []
        loc = f"{city} - {uf}" if city else "RS (Grande POA / Serra)"

        encoded = urllib.parse.quote(query)
        url = f"https://www.rissul.com.br/api/catalog_system/pub/products/search?ft={encoded}"

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

                        images = prod_items[0].get("images", [])
                        img_url = images[0].get("imageUrl") if images else ""

                        public_link = link or (f"https://www.rissul.com.br/{p.get('linkText')}/p" if p.get("linkText") else "")

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
                            location=loc
                        ))

                        if len(items) >= limit:
                            break
        except Exception:
            pass

        return items
