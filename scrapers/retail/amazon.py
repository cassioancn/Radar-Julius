import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from ..base import BaseScraper, ProductItem, parse_price_brl

class AmazonScraper(BaseScraper):
    """Scraper para Amazon Brasil (apenas dados 100% reais extraídos da página)."""

    def __init__(self):
        super().__init__(store_name="Amazon Brasil", store_type="retail")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9"
        })

    def search(self, query: str, limit: int = 10, **kwargs) -> List[ProductItem]:
        items: List[ProductItem] = []
        encoded = urllib.parse.quote(query)
        url = f"https://www.amazon.com.br/s?k={encoded}"

        try:
            resp = self.session.get(url, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                results = soup.select("[data-component-type='s-search-result']")
                
                for item in results:
                    title_el = item.select_one("h2 span, h2 a span")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)

                    link_el = item.select_one("h2 a")
                    link = f"https://www.amazon.com.br{link_el['href']}" if link_el and link_el.has_attr("href") else url

                    whole = item.select_one(".a-price-whole")
                    fraction = item.select_one(".a-price-fraction")
                    if not whole:
                        continue
                    val_str = whole.get_text(strip=True).replace(".", "")
                    if fraction:
                        val_str += f",{fraction.get_text(strip=True)}"
                    
                    price = parse_price_brl(val_str)
                    if not price or price <= 0:
                        continue

                    strike = item.select_one(".a-text-price .a-offscreen")
                    orig_price = parse_price_brl(strike.get_text(strip=True)) if strike else None
                    
                    discount_pct = None
                    if orig_price and orig_price > price:
                        discount_pct = round(((orig_price - price) / orig_price) * 100, 1)

                    img_el = item.select_one("img.s-image")
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

        # Sem dados inventados
        return items[:limit]
