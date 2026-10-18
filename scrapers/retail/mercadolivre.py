import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from ..base import BaseScraper, ProductItem, parse_price_brl

class MercadoLivreScraper(BaseScraper):
    """Scraper para Mercado Livre Brasil (apenas dados 100% reais extraídos da página)."""

    def __init__(self):
        super().__init__(store_name="Mercado Livre", store_type="retail")
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9"
        })

    def search(self, query: str, limit: int = 10, **kwargs) -> List[ProductItem]:
        items: List[ProductItem] = []
        encoded = urllib.parse.quote(query)
        url = f"https://lista.mercadolivre.com.br/{encoded}"

        try:
            resp = self.session.get(url, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select(".ui-search-layout__item, .poly-card")
                for card in cards[:limit * 2]:
                    title_elem = card.select_one(".ui-search-item__title, .poly-component__title")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)

                    link_elem = card.select_one("a.ui-search-link, a.poly-component__title")
                    link = link_elem["href"] if link_elem and link_elem.has_attr("href") else url

                    price_fraction = card.select_one(".andes-money-amount__fraction, .poly-price__current .andes-money-amount__fraction")
                    price_cents = card.select_one(".andes-money-amount__cents, .poly-price__current .andes-money-amount__cents")
                    
                    if not price_fraction:
                        continue

                    val_str = price_fraction.get_text(strip=True)
                    if price_cents:
                        val_str += f",{price_cents.get_text(strip=True)}"
                    
                    price = parse_price_brl(val_str)
                    if not price or price <= 0:
                        continue

                    orig_fraction = card.select_one(".andes-money-amount--previous .andes-money-amount__fraction")
                    orig_price = parse_price_brl(orig_fraction.get_text(strip=True)) if orig_fraction else None
                    
                    discount_pct = None
                    if orig_price and orig_price > price:
                        discount_pct = round(((orig_price - price) / orig_price) * 100, 1)

                    img_elem = card.select_one("img.ui-search-result-image__element, img.poly-component__picture")
                    img_url = ""
                    if img_elem:
                        img_url = img_elem.get("data-src") or img_elem.get("src") or ""

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

        # Sem fallback alucinado: apenas retorna o que foi efetivamente capturado
        return items[:limit]
