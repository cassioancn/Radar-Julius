import re
import json
import urllib.parse
from typing import Optional, Dict, Any
import requests
from bs4 import BeautifulSoup

from .base import ProductItem, parse_price_brl

def detect_store_from_url(url: str) -> str:
    """Identifica o nome amigável da loja a partir do domínio da URL."""
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
    else:
        # Fallback para o nome do domínio
        parts = domain.replace("www.", "").split(".")
        return parts[0].capitalize() if parts else "Loja Online"

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
        Usa extração rápida HTTP (OpenGraph, Schema.org e seletores comuns)
        com fallback para Playwright caso a página use renderização dinâmica (SPA) ou anti-bot.
        """
        store_name = detect_store_from_url(url)

        # 1. Tentativa Rápida via HTTP Requests
        item = self._extract_via_requests(url, store_name)
        if item and item.price > 0 and item.title:
            return item

        # 2. Fallback via Playwright para páginas com JavaScript ou bloqueio de bot
        item_playwright = self._extract_via_playwright(url, store_name)
        if item_playwright and item_playwright.price > 0 and item_playwright.title:
            return item_playwright

        return item or item_playwright

    def _extract_via_requests(self, url: str, store_name: str) -> Optional[ProductItem]:
        try:
            resp = requests.get(url, headers=self.headers, timeout=10, allow_redirects=True)
            if resp.status_code != 200:
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
                            image_url = image_url or data.get("image")
                            if isinstance(image_url, list) and image_url:
                                image_url = image_url[0]
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
                    title = og_title["content"].strip()

            if not image_url:
                og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
                if og_img and og_img.get("content"):
                    image_url = og_img["content"].strip()

            if not price:
                og_price = soup.find("meta", property="product:price:amount") or soup.find("meta", property="og:price:amount")
                if og_price and og_price.get("content"):
                    price = parse_price_brl(og_price["content"])

            # 3. Seletores específicos de lojas populares
            if not title:
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(strip=True)
                elif soup.title:
                    title = soup.title.get_text(strip=True)

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
                # Limpa título de sufixos como "| Mercado Livre" ou "- Amazon.com.br"
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

    def _extract_via_playwright(self, url: str, store_name: str) -> Optional[ProductItem]:
        """Extração com Playwright headless para páginas dinâmicas ou com proteção contra scraping."""
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
                page.goto(url, wait_until="domcontentloaded", timeout=25000)

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
            print(f"Aviso no Playwright de {url}: {e}")

        return None

# Instância singleton
url_product_scraper = URLProductScraper()

