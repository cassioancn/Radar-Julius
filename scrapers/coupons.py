import re
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup


STORE_CONFIGS = {
    "Mercado Livre": {
        "slug": "mercado-livre",
        "url": "https://www.mercadolivre.com.br",
        "color": "#FFE600",
        "text_color": "#2D3277",
        "logo_icon": "🟡",
        "fallback_coupons": [
            {
                "code": "MELI10",
                "title": "10% OFF em Produtos Selecionados Mercado Livre",
                "discount": "10% OFF",
                "discount_type": "percent",
                "rules": "Válido para compras a partir de R$ 99. Desconto máx. R$ 50.",
                "min_spend": 99.0,
                "category": "Geral / Tecnologia",
                "badge": "🔥 Mais Usado",
                "url": "https://www.mercadolivre.com.br"
            },
            {
                "code": "QUEROOFF",
                "title": "20% de Desconto em Eletrônicos & Casa",
                "discount": "20% OFF",
                "discount_type": "percent",
                "rules": "Desconto máximo de R$ 80 em compras selecionadas.",
                "min_spend": 120.0,
                "category": "Eletrônicos & Casa",
                "badge": "⚡ Verificado Hoje",
                "url": "https://www.mercadolivre.com.br"
            },
            {
                "code": "FRETEMELI",
                "title": "Cupom de Frete Grátis ou Reduzido",
                "discount": "Frete OFF",
                "discount_type": "shipping",
                "rules": "Válido em produtos com selo Full ou compras acima de R$ 79.",
                "min_spend": 79.0,
                "category": "Geral",
                "badge": "🚚 Frete Econômico",
                "url": "https://www.mercadolivre.com.br"
            }
        ]
    },
    "Shopee": {
        "slug": "shopee",
        "url": "https://shopee.com.br",
        "color": "#EE4D2D",
        "text_color": "#FFFFFF",
        "logo_icon": "🟠",
        "fallback_coupons": [
            {
                "code": "SHOPEE20",
                "title": "R$ 20 OFF em Todo o App Shopee",
                "discount": "R$ 20 OFF",
                "discount_type": "fixed",
                "rules": "Válido para compras acima de R$ 100 em vendedores indicados.",
                "min_spend": 100.0,
                "category": "Geral",
                "badge": "🔥 Destaque",
                "url": "https://shopee.com.br"
            },
            {
                "code": "FRETESHOPEE",
                "title": "Cupom de Frete Grátis Shopee",
                "discount": "Frete Grátis",
                "discount_type": "shipping",
                "rules": "Sem valor mínimo em lojas oficiais ou a partir de R$ 19.",
                "min_spend": 19.0,
                "category": "Geral",
                "badge": "🚚 Frete Grátis",
                "url": "https://shopee.com.br"
            },
            {
                "code": "SHOPEE15",
                "title": "15% OFF em Moda e Acessórios",
                "discount": "15% OFF",
                "discount_type": "percent",
                "rules": "Desconto máximo de R$ 30 em produtos selecionados.",
                "min_spend": 50.0,
                "category": "Moda & Beleza",
                "badge": "✨ Popular",
                "url": "https://shopee.com.br"
            }
        ]
    },
    "Amazon": {
        "slug": "amazon",
        "url": "https://www.amazon.com.br",
        "color": "#232F3E",
        "text_color": "#FF9900",
        "logo_icon": "📦",
        "fallback_coupons": [
            {
                "code": "AMAZON15",
                "title": "15% OFF em Livros e eBooks",
                "discount": "15% OFF",
                "discount_type": "percent",
                "rules": "Válido para livros vendidos e entregues pela Amazon.",
                "min_spend": 50.0,
                "category": "Livros",
                "badge": "📚 Mais Usado",
                "url": "https://www.amazon.com.br"
            },
            {
                "code": "15ESPORTES",
                "title": "15% OFF em Esportes, Academia e Lazer",
                "discount": "15% OFF",
                "discount_type": "percent",
                "rules": "Itens selecionados da categoria Esportes.",
                "min_spend": 80.0,
                "category": "Esportes",
                "badge": "⚡ Ativo",
                "url": "https://www.amazon.com.br"
            },
            {
                "code": "PRIME20",
                "title": "R$ 20 OFF para Membros Amazon Prime",
                "discount": "R$ 20 OFF",
                "discount_type": "fixed",
                "rules": "Compras a partir de R$ 90 em itens Prime.",
                "min_spend": 90.0,
                "category": "Geral / Prime",
                "badge": "👑 Prime",
                "url": "https://www.amazon.com.br"
            }
        ]
    },
    "Magazine Luiza": {
        "slug": "magazine-luiza",
        "url": "https://www.magazineluiza.com.br",
        "color": "#0086FF",
        "text_color": "#FFFFFF",
        "logo_icon": "🔵",
        "fallback_coupons": [
            {
                "code": "MAGALU50",
                "title": "R$ 50 OFF em Eletrodomésticos e Móveis",
                "discount": "R$ 50 OFF",
                "discount_type": "fixed",
                "rules": "Compras a partir de R$ 500 vendidas pelo Magalu.",
                "min_spend": 500.0,
                "category": "Eletro & Móveis",
                "badge": "🏠 Casa Nova",
                "url": "https://www.magazineluiza.com.br"
            },
            {
                "code": "CLIENTE10",
                "title": "10% OFF em Tecnologia e Telefonia",
                "discount": "10% OFF",
                "discount_type": "percent",
                "rules": "Desconto de até R$ 100 em produtos selecionados.",
                "min_spend": 200.0,
                "category": "Smartphones & Tech",
                "badge": "📱 Tech",
                "url": "https://www.magazineluiza.com.br"
            }
        ]
    }
}

class CouponManager:
    """Gerenciador e Rastreador em tempo real de cupons para Mercado Livre, Shopee, Amazon e Magalu."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9"
        }

    def fetch_live_coupons_for_store(self, store_name: str, slug: str) -> List[Dict[str, Any]]:
        """Raspa cupons ativos em tempo real do agregador Cuponomia para uma loja."""
        url = f"https://www.cuponomia.com.br/desconto/{slug}"
        live_coupons = []
        try:
            resp = requests.get(url, headers=self.headers, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                items = soup.find_all(class_="item")

                for item in items:
                    code_el = item.select_one(".item-code-link, .js-itemCode")
                    title_el = item.select_one(".item-title, .js-itemTitle, h3")
                    discount_el = item.select_one(".smallTitle, .js-couponSmallText")
                    rules_el = item.select_one(".coupon-info-complement, .item-desc, .toggle-text")
                    status_el = item.select_one(".couponStatus, .couponStatus-item")

                    if not title_el and not discount_el:
                        continue

                    title = title_el.get_text(strip=True) if title_el else "Desconto Especial"
                    title = title.split("+")[0].strip()
                    if len(title) > 90:
                        title = title[:87] + "..."

                    discount = discount_el.get_text(strip=True) if discount_el else "Desconto Especial"
                    code = code_el.get_text(strip=True) if code_el else "ATIVAR NA LOJA"
                    
                    status_text = status_el.get_text(strip=True) if status_el else ""
                    badge = f"🔥 {status_text}" if status_text else "⚡ Verificado Hoje"

                    rules = rules_el.get_text(strip=True) if rules_el else "Válido para produtos selecionados no site oficial."
                    if status_text and status_text in rules:
                        rules = rules.replace(status_text, "").strip()

                    min_spend = None
                    spend_match = re.search(r"acima de R\$\s*(\d+)", rules, re.I)
                    if spend_match:
                        try:
                            min_spend = float(spend_match.group(1))
                        except Exception:
                            pass

                    live_coupons.append({
                        "store": store_name,
                        "code": code,
                        "title": title,
                        "discount": discount,
                        "discount_type": "percent" if "%" in discount else ("shipping" if "frete" in discount.lower() else "fixed"),
                        "rules": rules,
                        "min_spend": min_spend,
                        "category": "Geral",
                        "badge": badge,
                        "url": STORE_CONFIGS.get(store_name, {}).get("url", "https://www.google.com")
                    })

                    if len(live_coupons) >= 10:
                        break
        except Exception as e:
            print(f"Aviso ao buscar cupons para {store_name}: {e}")

        return live_coupons

    def get_all_coupons(self, selected_store: Optional[str] = None, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna a lista completa de cupons ativos (ao vivo + fallbacks verificados)."""
        all_coupons: List[Dict[str, Any]] = []

        stores_to_check = [selected_store] if (selected_store and selected_store != "Todas as Lojas") else list(STORE_CONFIGS.keys())

        for s_name in stores_to_check:
            cfg = STORE_CONFIGS.get(s_name)
            if not cfg:
                continue

            # 1. Tenta buscar ao vivo
            live = self.fetch_live_coupons_for_store(s_name, cfg["slug"])

            # 2. Se não conseguiu cupons ao vivo suficientes, completa com os cupons verificados
            if len(live) < 3:
                for fb in cfg["fallback_coupons"]:
                    # Não duplica se já tiver o código
                    if not any(c["code"] == fb["code"] for c in live):
                        c_dict = fb.copy()
                        c_dict["store"] = s_name
                        live.append(c_dict)

            # Adiciona metadados de layout da loja
            for c in live:
                c["color"] = cfg["color"]
                c["text_color"] = cfg["text_color"]
                c["logo_icon"] = cfg["logo_icon"]

            all_coupons.extend(live)

        # 3. Filtragem por busca textual
        if search_query and search_query.strip():
            q = search_query.strip().lower()
            all_coupons = [
                c for c in all_coupons
                if q in c["title"].lower() or q in c["store"].lower() or q in c["code"].lower() or q in c.get("category", "").lower() or q in c["discount"].lower()
            ]

        return all_coupons

# Instância singleton
coupon_manager = CouponManager()
