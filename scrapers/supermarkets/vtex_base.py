import re
import threading
import time
import urllib.parse
from typing import Any, Dict, List, Optional
from ..base import BaseScraper, ProductItem


class VTEXSupermarketScraper(BaseScraper):
    """
    Base compartilhada para supermercados baseados na plataforma VTEX.
    Suporta consulta regional real por CEP via /api/checkout/pub/regions e
    validação de estoque/preço/SLAs locais via /api/checkout/pub/orderForms/simulation.
    """

    _region_cache_lock = threading.Lock()
    _region_cache: Dict[tuple, tuple] = {}
    _REGION_TTL_SECONDS = 900  # 15 minutos

    def __init__(
        self,
        store_name: str,
        base_url: str,
        default_fallback_label: str = "Catálogo Online",
        allow_catalog_fallback: bool = True,
        max_sellers_to_try: int = 3
    ):
        super().__init__(store_name=store_name, store_type="supermarket")
        self.base_url = base_url.rstrip("/")
        self.default_fallback_label = default_fallback_label
        self.allow_catalog_fallback = allow_catalog_fallback
        self.max_sellers_to_try = max_sellers_to_try
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9"
        })

    def _normalize_link(self, raw_link: Optional[str], product: Dict[str, Any]) -> str:
        """Converte links internos/relativos da VTEX em URL pública navegável."""
        link = (raw_link or "").strip()
        if not link and product.get("linkText"):
            link = f"{self.base_url}/{product['linkText']}/p"
        elif link.startswith("/"):
            link = f"{self.base_url}{link}"
        return link

    def _get_regional_sellers(self, cep_digits: str) -> List[Dict[str, str]]:
        """Consulta vendedores regionais da VTEX para o CEP informado (com cache TTL)."""
        cache_key = (self.base_url, cep_digits)
        now = time.time()
        with self._region_cache_lock:
            cached = self._region_cache.get(cache_key)
            if cached and (now - cached[0]) < self._REGION_TTL_SECONDS:
                return [dict(s) for s in cached[1]]

        sellers: List[Dict[str, str]] = []
        try:
            url = f"{self.base_url}/api/checkout/pub/regions?country=BRA&postalCode={cep_digits}"
            resp = self.session.get(url, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    raw_sellers = data[0].get("sellers", []) or []
                    sellers = [
                        {"id": str(s["id"]), "name": str(s.get("name") or s["id"]).strip()}
                        for s in raw_sellers
                        if s.get("id")
                    ]
        except Exception:
            sellers = []

        with self._region_cache_lock:
            self._region_cache[cache_key] = (now, [dict(s) for s in sellers])
        return sellers

    @staticmethod
    def _prioritize_sellers(sellers: List[Dict[str, str]], city: Optional[str]) -> List[Dict[str, str]]:
        """Prioriza vendedores cujo nome contenha a cidade do usuário, preservando a ordem original."""
        if not city or not sellers:
            return sellers
        city_lower = city.strip().lower()
        matching = [s for s in sellers if city_lower in s["name"].lower()]
        others = [s for s in sellers if city_lower not in s["name"].lower()]
        return matching + others

    @staticmethod
    def _format_channel_label(slas: List[Dict[str, Any]]) -> str:
        channels = {str(s.get("deliveryChannel") or "").lower() for s in slas}
        has_delivery = "delivery" in channels
        has_pickup = "pickup-in-point" in channels
        if has_delivery and has_pickup:
            return "Entrega ou Retirada"
        if has_delivery:
            return "Entrega no CEP"
        if has_pickup:
            return "Clique & Retire"
        return "Disponível na Região"

    def _simulate_regional_products(
        self,
        candidates: List[Dict[str, Any]],
        cep_digits: str,
        city: Optional[str],
        limit: int
    ) -> List[ProductItem]:
        """Executa simulação de checkout em lote para obter preços/estoque reais no CEP."""
        if not candidates:
            return []

        sellers = self._prioritize_sellers(self._get_regional_sellers(cep_digits), city)
        if not sellers:
            return []

        cep_fmt = f"{cep_digits[:5]}-{cep_digits[5:]}"

        for seller in sellers[:self.max_sellers_to_try]:
            seller_id = seller["id"]
            seller_name = seller["name"]
            batch_items = [
                {"id": c["sku_id"], "quantity": 1, "seller": seller_id}
                for c in candidates
                if c.get("sku_id")
            ]
            if not batch_items:
                continue

            try:
                sim_resp = self.session.post(
                    f"{self.base_url}/api/checkout/pub/orderForms/simulation",
                    json={"items": batch_items, "postalCode": cep_digits, "country": "BRA"},
                    timeout=8
                )
                if sim_resp.status_code not in (200, 206):
                    continue
                sim_data = sim_resp.json() or {}
            except Exception:
                continue

            sim_items = sim_data.get("items", []) or []
            logistics_info = sim_data.get("logisticsInfo", []) or []
            slas_by_item_idx: Dict[int, List[Dict[str, Any]]] = {}
            for idx, li in enumerate(logistics_info):
                raw_item_idx = li.get("itemIndex")
                item_idx = int(raw_item_idx) if raw_item_idx is not None else idx
                slas_by_item_idx[item_idx] = li.get("slas", []) or []

            # Mapeia requestIndex -> candidato original enviado no batch
            valid_candidates = [c for c in candidates if c.get("sku_id")]
            regional_items: List[ProductItem] = []

            for idx, s_item in enumerate(sim_items):
                if s_item.get("availability") != "available":
                    continue
                slas = slas_by_item_idx.get(idx, [])
                if not slas:
                    continue

                raw_price_cents = s_item.get("sellingPrice")
                if not raw_price_cents or int(raw_price_cents) <= 0:
                    raw_price_cents = s_item.get("price")
                if not raw_price_cents or int(raw_price_cents) <= 0:
                    continue

                raw_req_idx = s_item.get("requestIndex")
                req_idx = raw_req_idx if isinstance(raw_req_idx, int) else idx
                if req_idx < 0 or req_idx >= len(valid_candidates):
                    continue

                cand = valid_candidates[req_idx]
                price_val = round(float(raw_price_cents) / 100.0, 2)
                raw_list_cents = s_item.get("listPrice")
                orig_val = (
                    round(float(raw_list_cents) / 100.0, 2)
                    if raw_list_cents and (float(raw_list_cents) / 100.0) > price_val
                    else None
                )
                disc_pct = round(((orig_val - price_val) / orig_val) * 100, 1) if orig_val else None
                channel_label = self._format_channel_label(slas)

                regional_items.append(ProductItem(
                    title=cand["title"],
                    price=price_val,
                    original_price=orig_val,
                    discount_pct=disc_pct,
                    store=self.store_name,
                    store_type=self.store_type,
                    url=cand["url"],
                    image_url=cand["image_url"],
                    location=f"{seller_name} ({channel_label} • CEP {cep_fmt})",
                    in_stock=True,
                    regional_confirmed=True
                ))

                if len(regional_items) >= limit:
                    break

            if regional_items:
                return regional_items

        return []

    def search(
        self,
        query: str,
        limit: int = 10,
        city: Optional[str] = None,
        uf: Optional[str] = None,
        cep: Optional[str] = None,
        **kwargs
    ) -> List[ProductItem]:
        encoded = urllib.parse.quote(query)
        fetch_cap = min(max(limit * 2, 12), 20)
        url = f"{self.base_url}/api/catalog_system/pub/products/search?ft={encoded}&_from=0&_to={fetch_cap - 1}"

        candidates: List[Dict[str, Any]] = []
        try:
            resp = self.session.get(url, timeout=7)
            if resp.status_code in (200, 206):
                data = resp.json()
                if isinstance(data, list):
                    for p in data[:fetch_cap]:
                        name = p.get("productName")
                        prod_items = p.get("items", []) or []
                        if not name or not prod_items:
                            continue

                        sku_obj = prod_items[0]
                        sku_id = str(sku_obj.get("itemId") or "")
                        images = sku_obj.get("images", []) or []
                        img_url = images[0].get("imageUrl") if images else ""
                        public_link = self._normalize_link(p.get("link"), p)

                        price = None
                        orig_price = None
                        sellers = sku_obj.get("sellers", []) or []
                        if sellers:
                            comm = sellers[0].get("commertialOffer", {}) or {}
                            price = comm.get("Price")
                            orig_price = comm.get("ListPrice")

                        candidates.append({
                            "sku_id": sku_id,
                            "title": name,
                            "url": public_link,
                            "image_url": img_url,
                            "fallback_price": float(price) if price and float(price) > 0 else None,
                            "fallback_orig_price": float(orig_price) if orig_price and float(orig_price) > 0 else None
                        })
        except Exception:
            return []

        if not candidates:
            return []

        cep_digits = re.sub(r"\D", "", str(cep or ""))
        if len(cep_digits) == 8:
            regional_items = self._simulate_regional_products(
                candidates=candidates,
                cep_digits=cep_digits,
                city=city,
                limit=limit
            )
            if regional_items:
                return regional_items

        if not self.allow_catalog_fallback:
            return []

        loc_city = f"{city} - {uf}" if city and uf else (city or uf or self.default_fallback_label)
        fallback_label = (
            f"Catálogo Online Geral (confirmar loja em {loc_city})"
            if len(cep_digits) == 8
            else loc_city
        )

        fallback_items: List[ProductItem] = []
        for cand in candidates:
            price = cand.get("fallback_price")
            if not price or price <= 0:
                continue
            price_val = round(price, 2)
            orig_raw = cand.get("fallback_orig_price")
            orig_val = round(orig_raw, 2) if orig_raw and orig_raw > price_val else None
            disc_pct = round(((orig_val - price_val) / orig_val) * 100, 1) if orig_val else None

            fallback_items.append(ProductItem(
                title=cand["title"],
                price=price_val,
                original_price=orig_val,
                discount_pct=disc_pct,
                store=self.store_name,
                store_type=self.store_type,
                url=cand["url"],
                image_url=cand["image_url"],
                location=fallback_label,
                in_stock=True,
                regional_confirmed=False
            ))
            if len(fallback_items) >= limit:
                break

        return fallback_items
