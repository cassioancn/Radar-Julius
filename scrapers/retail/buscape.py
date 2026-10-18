import re
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from ..base import BaseScraper, ProductItem, parse_price_brl

class BuscapeScraper(BaseScraper):
    """
    Scraper do Buscapé: captura em tempo real preços e ofertas reais dos maiores
    varejistas do Brasil (Amazon, Mercado Livre, Shopee, Magalu, Fast Shop, Casas Bahia, etc.).
    """

    def __init__(self):
        super().__init__(store_name="Buscapé Varejo", store_type="retail")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9"
        })

    def search(self, query: str, limit: int = 15, **kwargs) -> List[ProductItem]:
        items: List[ProductItem] = []
        encoded = urllib.parse.quote(query)
        url = f"https://www.buscape.com.br/search?q={encoded}"

        try:
            resp = self.session.get(url, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select("[data-testid='product-card']")
                for card in cards[:limit * 2]:
                    title_el = card.select_one("[data-testid='product-card::name']")
                    price_el = card.select_one("[data-testid='product-card::price']")
                    merchant_el = card.select_one("[class*='BestOfferMerchant']")
                    link_el = card.select_one("a")
                    img_el = card.select_one("img")

                    if not title_el or not price_el or not link_el:
                        continue

                    title = title_el.get_text(strip=True)
                    price = parse_price_brl(price_el.get_text(strip=True))
                    if not price or price <= 0:
                        continue

                    raw_merchant = merchant_el.get_text(strip=True) if merchant_el else ""
                    store_display = raw_merchant.replace("Via ", "").strip() if raw_merchant else "Varejo Online"

                    href = link_el.get("href", "")
                    link_url = f"https://www.buscape.com.br{href}" if href.startswith("/") else href

                    img_url = img_el.get("src") if img_el else ""

                    items.append(ProductItem(
                        title=title,
                        price=price,
                        original_price=None,
                        discount_pct=None,
                        store=store_display,
                        store_type=self.store_type,
                        url=link_url,
                        image_url=img_url
                    ))

                    if len(items) >= limit:
                        break
        except Exception:
            pass

        return items

