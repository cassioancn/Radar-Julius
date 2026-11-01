import re
import json
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any, List
import requests
from bs4 import BeautifulSoup

from .base import ProductItem, parse_price_brl

def detect_store_from_url(url: str) -> str:
    """Identifica o nome amigável da loja a partir do domínio da URL."""
    try:
        domain = urllib.parse.urlparse(url).netloc.lower()
        if "mercadolivre" in domain or "mercado-livre" in domain:
            return "Mercado Livre"
        elif "amazon" in domain:
            return "Amazon"
        elif "magazineluiza" in domain or "magalu" in domain:
            return "Magazine Luiza"
        elif "shopee" in domain:
            return "Shopee"
        elif "atacadao" in domain:
            return "Atacadão"
        elif "rissul" in domain:
            return "Super Rissul"
        elif "macromix" in domain:
            return "Macromix"
        elif "stockcenter" in domain:
            return "Stock Center"
        elif "carrefour" in domain:
            return "Carrefour"
        elif "casasbahia" in domain:
            return "Casas Bahia"
        elif "kabum" in domain:
            return "KaBuM!"
        elif "buscape" in domain:
            return "Buscapé"
        else:
            parts = domain.replace("www.", "").split(".")
            return parts[0].capitalize() if parts else "Loja Online"
    except Exception:
        return "Loja Online"

def extract_keywords_from_url(url: str) -> str:
    """Extrai o nome ou termos do produto a partir dos slugs da URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path

        # 1. Mercado Livre
        ml_match = re.search(r"mercadolivre\.com\.br/([a-zA-Z0-9\-]+)(?:/p/|/MLB)", url, re.I)
        if ml_match:
            slug = ml_match.group(1).replace("-", " ")
            slug = re.sub(r"\bMLB\d+\b", "", slug, flags=re.I).strip()
            if len(slug) > 5:
                return slug

        # 2. Amazon
        az_match = re.search(r"amazon\.com\.br/(?:([^/]+)/)?dp/", url, re.I)
        if az_match and az_match.group(1):
            slug = az_match.group(1).replace("-", " ")
            if len(slug) > 5:
                return slug

        # 3. Slugs genéricos (/categoria/nome-do-produto-xyz/p)
        slug_parts = [p for p in path.split("/") if p and not p.isdigit() and len(p) > 5]
        if slug_parts:
            last_slug = slug_parts[-1]
            if last_slug == "p" and len(slug_parts) > 1:
                last_slug = slug_parts[-2]
            words = re.sub(r"[\-_]+", " ", last_slug)
            words = re.sub(r"\b\d{4,}\b", "", words).strip()
            if len(words) > 5:
                return words
    except Exception:
        pass
    return ""


class URLProductScraper:
    """Scraper universal para extrair título, preço atual, imagem e loja de links específicos de produtos."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }

    def scrape_url(self, url: str) -> Optional[ProductItem]:
        """
        Extrai informações de um produto a partir de sua URL web direta.
        1. Tenta extração direta via HTTP Requests (OpenGraph, Schema.org e seletores).
        2. Se bloqueado por anti-bot ou indisponível, faz fallback via busca de termos do slug.
        3. Se disponível, tenta Playwright headless.
        """
        clean_url = (url or "").strip()
        if not clean_url:
            return None

        store_name = detect_store_from_url(clean_url)

        # 1. Tentativa Rápida via HTTP Requests
        item = self._extract_via_requests(clean_url, store_name)
        if item and getattr(item, "price", 0) > 0 and getattr(item, "title", None):
            return item

        # 2. Fallback inteligente via busca com termos da URL (para Mercado Livre/Amazon com proteção anti-bot)
        item_search = self._extract_via_search_fallback(clean_url, store_name)
        if item_search and getattr(item_search, "price", 0) > 0:
            return item_search

        # 3. Fallback via Playwright para páginas com JavaScript
        item_playwright = self._extract_via_playwright(clean_url, store_name)
        if item_playwright and getattr(item_playwright, "price", 0) > 0 and getattr(item_playwright, "title", None):
            return item_playwright

        return item or item_search or item_playwright

    def _extract_via_requests(self, url: str, store_name: str) -> Optional[ProductItem]:
        try:
            resp = requests.get(url, headers=self.headers, timeout=10, allow_redirects=True)
            if resp.status_code != 200 or len(resp.text) < 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            title = None
            price = None
            original_price = None
            image_url = None

            # 1. Tenta Schema.org JSON-LD
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "{}")
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    if isinstance(data, dict):
                        if data.get("@type") in ("Product", "Offer", "IndividualProduct"):
                            title = title or data.get("name")
                            img = data.get("image")
                            if isinstance(img, list) and img:
                                image_url = image_url or (img[0] if isinstance(img[0], str) else img[0].get("url"))
                            elif isinstance(img, str):
                                image_url = image_url or img
                            elif isinstance(img, dict):
                                image_url = image_url or img.get("url")

                            offers = data.get("offers", {})
                            if isinstance(offers, dict):
                                p_val = offers.get("price") or offers.get("lowPrice")
                                if p_val:
                                    price = parse_price_brl(str(p_val))
                            elif isinstance(offers, list) and offers:
                                p_val = offers[0].get("price")
                                if p_val:
                                    price = parse_price_brl(str(p_val))
                except Exception:
                    pass

            # 2. Tenta OpenGraph Tags
            if not title:
                og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
                if og_title and og_title.get("content"):
                    title = str(og_title["content"]).strip()

            if not image_url:
                og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
                if og_img and og_img.get("content"):
                    image_url = str(og_img["content"]).strip()

            if not price:
                og_price = soup.find("meta", property="product:price:amount") or soup.find("meta", property="og:price:amount")
                if og_price and og_price.get("content"):
                    price = parse_price_brl(og_price["content"])

            # 3. Seletores específicos de lojas populares
            if not title:
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)
                elif soup.title and soup.title.string:
                    title = soup.title.string.strip()

            if not price:
                price_selectors = [
                    ".ui-pdp-price__second-line .andes-money-amount__fraction",
                    ".a-price .a-offscreen",
                    "[data-testid='price-value']",
                    ".price-tag-fraction",
                    ".preco-por",
                    ".price-current",
                    "[itemprop='price']",
                    ".product-price"
                ]
                for sel in price_selectors:
                    el = soup.select_one(sel)
                    if el:
                        p = parse_price_brl(el.get_text(strip=True))
                        if p and p > 0:
                            price = p
                            break

            # 4. Fallback de regex de preço
            if not price:
                body_text = soup.get_text()
                match = re.search(r"R\$\s*([\d\.,]+)", body_text)
                if match:
                    price = parse_price_brl(match.group(1))

            if title and price and price > 0:
                title = re.sub(r"\s*[\-|\•]\s*(Mercado Livre|Amazon|Magazine Luiza|Shopee|Atacadão).*$", "", title, flags=re.I).strip()
                return ProductItem(
                    title=title,
                    price=price,
                    original_price=original_price,
                    discount_pct=None,
                    store=store_name,
                    store_type="supermarket" if store_name in ("Atacadão", "Super Rissul", "Macromix", "Stock Center", "Carrefour") else "retail",
                    url=url,
                    image_url=image_url
                )
        except Exception as e:
            print(f"Aviso no requests de {url}: {e}")

        return None

    def _extract_via_search_fallback(self, url: str, store_name: str) -> Optional[ProductItem]:
        """Fallback que busca o produto no Buscapé usando as palavras-chave extraídas da URL."""
        try:
            keywords = extract_keywords_from_url(url)
            if not keywords or len(keywords) < 5:
                return None

            from .retail.buscape import BuscapeScraper
            bc = BuscapeScraper()
            items = bc.search(keywords, limit=2)
            if items:
                best = items[0]
                if best.price > 0:
                    return ProductItem(
                        title=best.title,
                        price=best.price,
                        original_price=best.original_price,
                        discount_pct=best.discount_pct,
                        store=store_name,
                        store_type="retail",
                        url=url,  # Mantém a URL original fornecida pelo usuário
                        image_url=best.image_url
                    )
        except Exception as e:
            print(f"Aviso no fallback de busca para {url}: {e}")
        return None

    def _extract_via_playwright(self, url: str, store_name: str) -> Optional[ProductItem]:
        """Extração com Playwright headless para páginas dinâmicas."""
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
                )
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                page.goto(url, wait_until="domcontentloaded", timeout=20000)

                title = page.title()
                h1_el = page.locator("h1").first
                if h1_el.count() > 0:
                    title = h1_el.inner_text().strip()

                price = None
                price_selectors = [
                    ".ui-pdp-price__second-line .andes-money-amount__fraction",
                    ".a-price .a-offscreen",
                    "[data-testid='price-value']",
                    ".price-tag-fraction",
                    "[itemprop='price']",
                    ".preco-por"
                ]
                for sel in price_selectors:
                    loc = page.locator(sel).first
                    if loc.count() > 0:
                        txt = loc.inner_text() or loc.get_attribute("content") or ""
                        p = parse_price_brl(txt)
                        if p and p > 0:
                            price = p
                            break

                if not price:
                    body = page.locator("body").inner_text()
                    m = re.search(r"R\$\s*([\d\.,]+)", body)
                    if m:
                        price = parse_price_brl(m.group(1))

                img_url = None
                og_img = page.locator("meta[property='og:image']").first
                if og_img.count() > 0:
                    img_url = og_img.get_attribute("content")

                browser.close()

                if title and price and price > 0:
                    title = re.sub(r"\s*[\-|\•]\s*(Mercado Livre|Amazon|Magazine Luiza|Shopee|Atacadão).*$", "", title, flags=re.I).strip()
                    return ProductItem(
                        title=title,
                        price=price,
                        original_price=None,
                        discount_pct=None,
                        store=store_name,
                        store_type="supermarket" if store_name in ("Atacadão", "Super Rissul", "Macromix", "Stock Center", "Carrefour") else "retail",
                        url=url,
                        image_url=img_url
                    )
        except Exception as e:
            pass

        return None


# Instância global singleton
url_product_scraper = URLProductScraper()


def track_specific_url(
    url: Optional[str] = None,
    target_drop_pct: float = 10.0,
    user_city: Optional[str] = None,
    user_state: Optional[str] = None,
    user_cep: Optional[str] = None,
    custom_name: Optional[str] = None,
    target_url: Optional[str] = None
) -> Dict[str, Any]:
    """Extrai as informações de um link de produto e cadastra no monitoramento específico."""
    target_link = (url or target_url or "").strip()
    if not target_link:
        return {"success": False, "error": "URL não fornecida.", "message": "URL não fornecida."}

    item = url_product_scraper.scrape_url(target_link)
    if not item or not getattr(item, "price", None) or item.price <= 0:
        err_msg = "Não foi possível extrair o preço e dados do produto automaticamente deste link. Verifique se o link está acessível."
        return {
            "success": False,
            "error": err_msg,
            "message": err_msg
        }

    from database.db import get_db
    from database.models import TrackedProduct, PriceCapture, HistoricalTopPrice

    product_name = custom_name or getattr(item, "title", None) or "Produto Monitorado"
    store = getattr(item, "store", None) or "Loja Online"

    with get_db() as db:
        existing = db.query(TrackedProduct).filter(
            (TrackedProduct.target_url == target_link) |
            ((TrackedProduct.name == product_name) & (TrackedProduct.is_url_specific == True))
        ).first()

        now = datetime.utcnow()
        if existing:
            existing.active = True
            existing.target_drop_pct = target_drop_pct
            existing.current_price = item.price
            existing.last_best_price = min(existing.last_best_price or item.price, item.price)
            existing.last_checked_at = now
            if getattr(item, "image_url", None):
                existing.image_url = item.image_url
            prod_id = existing.id
        else:
            new_prod = TrackedProduct(
                name=product_name,
                niche=store,
                target_drop_pct=target_drop_pct,
                last_best_price=item.price,
                current_price=item.price,
                user_cep=user_cep,
                user_city=user_city,
                user_state=user_state,
                active=True,
                created_at=now,
                last_checked_at=now,
                target_url=target_link,
                is_url_specific=True,
                image_url=getattr(item, "image_url", None),
                store_name=store
            )
            db.add(new_prod)
            db.flush()
            prod_id = new_prod.id

        db.add(PriceCapture(
            product_id=prod_id,
            store_name=store,
            store_type=getattr(item, "store_type", "retail"),
            product_title=getattr(item, "title", None) or product_name,
            price=item.price,
            original_price=getattr(item, "original_price", None),
            discount_pct=getattr(item, "discount_pct", None),
            url=target_link,
            image_url=getattr(item, "image_url", None),
            location_city=user_city,
            captured_at=now
        ))

        top_h = db.query(HistoricalTopPrice).filter(HistoricalTopPrice.product_id == prod_id).first()
        if not top_h:
            db.add(HistoricalTopPrice(
                product_id=prod_id,
                rank=1,
                store_name=store,
                product_title=getattr(item, "title", None) or product_name,
                price=item.price,
                url=target_link,
                captured_at=now
            ))

    return {
        "success": True,
        "product_id": prod_id,
        "item": item,
        "store": store,
        "price": item.price,
        "title": product_name,
        "message": "Produto monitorado com sucesso!"
    }


def check_and_persist_tracked_url(
    product_id: int,
    phone: Optional[str] = None,
    apikey: Optional[str] = None,
    provider: Optional[str] = None,
    custom_url: Optional[str] = None
) -> Dict[str, Any]:
    """Varre um link específico já cadastrado, verifica quedas e dispara alerta WhatsApp se houver queda >= X%."""
    from database.db import get_db
    from database.models import TrackedProduct, PriceCapture, HistoricalTopPrice
    from notifications.whatsapp_dispatcher import dispatch_price_drop_alert

    with get_db() as db:
        product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
        if not product or not product.target_url:
            return {"status": "error", "message": "Produto ou URL não encontrada"}

        item = url_product_scraper.scrape_url(product.target_url)
        if not item or item.price <= 0:
            return {"status": "error", "message": "Falha ao extrair preço do link"}

        now = datetime.utcnow()
        product.last_checked_at = now
        product.current_price = item.price
        if getattr(item, "image_url", None):
            product.image_url = item.image_url

        db.add(PriceCapture(
            product_id=product.id,
            store_name=getattr(item, "store", None) or product.store_name or "Loja Online",
            store_type=getattr(item, "store_type", "retail"),
            product_title=getattr(item, "title", None) or product.name,
            price=item.price,
            original_price=getattr(item, "original_price", None),
            discount_pct=getattr(item, "discount_pct", None),
            url=product.target_url,
            image_url=getattr(item, "image_url", None),
            location_city=product.user_city,
            captured_at=now
        ))

        old_price = product.last_best_price
        alert_dispatched = False
        alert_details = None

        if old_price and old_price > 0 and item.price < old_price:
            drop_pct = ((old_price - item.price) / old_price) * 100.0
            if drop_pct >= (product.target_drop_pct or 10.0):
                alert_details = dispatch_price_drop_alert(
                    product_id=product.id,
                    product_name=product.name,
                    niche=product.niche,
                    store_name=getattr(item, "store", None) or product.store_name or "Loja Online",
                    current_price=item.price,
                    previous_price=old_price,
                    drop_pct=drop_pct,
                    url=product.target_url,
                    location_city=product.user_city,
                    image_url=getattr(item, "image_url", None),
                    phone=phone,
                    apikey=apikey,
                    provider=provider,
                    custom_url=custom_url
                )
                alert_dispatched = True

        if not product.last_best_price or item.price < product.last_best_price:
            product.last_best_price = item.price

        existing_history = db.query(HistoricalTopPrice).filter(
            HistoricalTopPrice.product_id == product.id
        ).all()

        candidates = [{
            "store_name": h.store_name,
            "product_title": h.product_title,
            "price": h.price,
            "url": h.url,
            "captured_at": h.captured_at
        } for h in existing_history]

        candidates.append({
            "store_name": getattr(item, "store", None) or product.store_name or "Loja Online",
            "product_title": getattr(item, "title", None) or product.name,
            "price": item.price,
            "url": product.target_url,
            "captured_at": now
        })

        seen = set()
        unique_candidates = []
        for c in sorted(candidates, key=lambda x: x["price"]):
            key = round(c["price"], 2)
            if key not in seen:
                seen.add(key)
                unique_candidates.append(c)

        top_3 = unique_candidates[:3]
        db.query(HistoricalTopPrice).filter(HistoricalTopPrice.product_id == product.id).delete()
        for idx, c in enumerate(top_3, start=1):
            db.add(HistoricalTopPrice(
                product_id=product.id,
                rank=idx,
                store_name=c["store_name"],
                product_title=c["product_title"],
                price=c["price"],
                url=c["url"],
                captured_at=c["captured_at"]
            ))

        return {
            "status": "success",
            "price": item.price,
            "store": getattr(item, "store", "Loja Online"),
            "alert_dispatched": alert_dispatched,
            "alert_details": alert_details
        }
