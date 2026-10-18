import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from ..base import BaseScraper, ProductItem, parse_price_brl

class MagaluScraper(BaseScraper):
    """Scraper para Magazine Luiza (apenas dados 100% reais)."""

    def __init__(self):
        super().__init__(store_name="Magalu", store_type="retail")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9"
        })

    def search(self, query: str, limit: int = 10, **kwargs) -> List[ProductItem]:
        items: List[ProductItem] = []
        encoded = urllib.parse.quote(query)
        url = f"https://www.magazineluiza.com.br/busca/{encoded}/"

        try:
            resp = self.session.get(url, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select("[data-testid='product-card-container'], li[id^='product-']")
                for card in cards[:limit * 2]:
                    title_el = card.select_one("[data-testid='product-title'], h2")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)

                    link_el = card.select_one("a[data-testid='product-card-container'], a")
                    link = f"https://www.magazineluiza.com.br{link_el['href']}" if link_el and link_el.has_attr("href") and link_el['href'].startswith("/") else (link_el['href'] if link_el and link_el.has_attr("href") else url)

                    price_el = card.select_one("[data-testid='price-value'], [data-testid='price-original']")
                    if not price_el:
                        continue
                    price = parse_price_brl(price_el.get_text(strip=True))
                    if not price or price <= 0:
                        continue

                    orig_el = card.select_one("[data-testid='price-original']")
                    orig_price = parse_price_brl(orig_el.get_text(strip=True)) if orig_el and orig_el != price_el else None
                    discount_pct = round(((orig_price - price) / orig_price) * 100, 1) if orig_price and orig_price > price else None

                    img_el = card.select_one("img")
                    img_url = img_el.get("src") if img_el else ""

                    items.append(ProductItem(
                        title=title,
                        price=price,
                        original_price=orig_price,
                        discount_pct=discount_pct,
                        store=self.store_name,
                        store_type=self.store_type,
                        url=link,
                        image_url=img_url
                    ))
                    if len(items) >= limit:
                        break
        except Exception:
            pass

        return items[:limit]
