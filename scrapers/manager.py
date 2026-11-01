from datetime import datetime
from typing import List, Dict, Any, Optional
import concurrent.futures

from .base import ProductItem
from .retail import BuscapeScraper, MercadoLivreScraper, AmazonScraper, MagaluScraper, ShopeeScraper
from .supermarkets import AtacadaoScraper, MacromixScraper, RissulScraper, StockCenterScraper
from database.db import get_db
from database.models import TrackedProduct, PriceCapture, HistoricalTopPrice
from notifications.whatsapp_dispatcher import dispatch_price_drop_alert
from utils.unit_parser import calculate_normalized_price

class ScraperManager:
    """Orquestrador central de busca, ranqueamento Top 5 e atualização do Top 3 histórico."""

    def __init__(self):
        self.retail_scrapers = [
            BuscapeScraper(),
            MercadoLivreScraper(),
            AmazonScraper(),
            MagaluScraper(),
            ShopeeScraper()
        ]
        self.supermarket_scrapers = [
            AtacadaoScraper(),
            RissulScraper(),
            MacromixScraper(),
            StockCenterScraper()
        ]

    def search_all(
        self,
        query: str,
        include_retail: bool = True,
        include_supermarkets: bool = True,
        city: Optional[str] = None,
        uf: Optional[str] = None,
        top_n: int = 5,
        target_unit: Optional[str] = None,
        sort_by_unit: bool = False,
        filter_unit_match: bool = False
    ) -> Dict[str, Any]:
        """
        Executa busca concorrente em todas as fontes selecionadas.
        Normaliza preços por unidade (R$/kg, R$/L, R$/un) e ranqueia pelo menor preço ou melhor custo-benefício.
        """
        active_scrapers = []
        if include_retail:
            active_scrapers.extend(self.retail_scrapers)
        if include_supermarkets:
            active_scrapers.extend(self.supermarket_scrapers)

        all_items: List[ProductItem] = []

        def _run_scraper(scraper):
            try:
                kwargs = {}
                if scraper.store_type == "supermarket":
                    if city:
                        kwargs["city"] = city
                    if uf:
                        kwargs["uf"] = uf
                return scraper.search(query=query, limit=5, **kwargs)
            except Exception:
                return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_run_scraper, s) for s in active_scrapers]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    all_items.extend(res)

        # 1. Normalização de Preço Unitário (kg, L, un)
        for item in all_items:
            norm = calculate_normalized_price(
                price=item.price,
                title=item.title,
                fallback_text=item.url,
                target_unit=target_unit
            )
            if norm.get("has_unit_price"):
                item.has_unit_price = True
                item.unit_price = norm["unit_price"]
                item.unit_label = norm["unit_label"]
                item.detected_size = norm["detected_size"]
            else:
                item.has_unit_price = False
                item.unit_price = item.price
                item.unit_label = None
                item.detected_size = norm.get("detected_size", "Embalagem Padrão")

        # 2. Filtragem opcional por unidade alvo (ex: apenas quilo ou apenas litro)
        if filter_unit_match and target_unit and target_unit != "auto":
            matched = [it for it in all_items if it.has_unit_price and (
                (target_unit == "kg" and "kg" in (it.unit_label or "").lower()) or
                (target_unit == "L" and "/ l" in (it.unit_label or "").lower()) or
                (target_unit == "un" and "/ un" in (it.unit_label or "").lower())
            )]
            # Se encontrar correspondentes, filtra; se não, mantém todos para não deixar vazio
            if matched:
                all_items = matched

        # 3. Ordenação: por menor custo unitário OU por menor preço total do pacote
        if sort_by_unit:
            # Itens com unidade normalizada vêm na frente ordenados pelo menor preço unitário
            all_items.sort(key=lambda x: (0 if x.has_unit_price else 1, x.unit_price if x.has_unit_price else x.price))
        else:
            all_items.sort(key=lambda x: x.price)

        # Top N melhores preços
        top_items = all_items[:top_n]

        # Estatísticas da busca
        avg_price = sum(item.price for item in all_items) / len(all_items) if all_items else 0.0
        min_price = top_items[0].price if top_items else 0.0
        max_price = all_items[-1].price if all_items else 0.0
        potential_savings = max_price - min_price if all_items else 0.0

        # Estatísticas de unidade quando aplicável
        items_with_unit = [it for it in top_items if it.has_unit_price and it.unit_price]
        min_unit_price = min((it.unit_price for it in items_with_unit), default=0.0) if items_with_unit else 0.0
        max_unit_price = max((it.unit_price for it in items_with_unit), default=0.0) if items_with_unit else 0.0

        return {
            "query": query,
            "timestamp": datetime.utcnow().isoformat(),
            "total_found": len(all_items),
            "top_prices": top_items,
            "all_results": all_items,
            "sort_by_unit": sort_by_unit,
            "target_unit": target_unit,
            "stats": {
                "min_price": round(min_price, 2),
                "max_price": round(max_price, 2),
                "avg_price": round(avg_price, 2),
                "potential_savings": round(potential_savings, 2),
                "min_unit_price": round(min_unit_price, 2),
                "max_unit_price": round(max_unit_price, 2)
            }
        }

    def process_and_persist_tracked_product(
        self,
        product_id: int,
        search_result: Dict[str, Any],
        phone: Optional[str] = None,
        apikey: Optional[str] = None,
        provider: Optional[str] = None,
        custom_url: Optional[str] = None,
        custom_webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Grava capturas, atualiza os 3 melhores preços históricos e detecta queda >= X% para disparar alerta via WhatsApp.
        """
        top_items: List[ProductItem] = search_result.get("top_prices", [])
        if not top_items:
            return {"status": "no_items_found"}

        best_current = top_items[0]
        alert_dispatched = False
        alert_details = None

        with get_db() as db:
            product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
            if not product:
                return {"status": "product_not_found"}

            now = datetime.utcnow()
            product.last_checked_at = now

            # 1. Grava as capturas atuais do Top 5
            for item in top_items:
                capture = PriceCapture(
                    product_id=product.id,
                    store_name=item.store,
                    store_type=item.store_type,
                    product_title=item.title,
                    price=item.price,
                    original_price=item.original_price,
                    discount_pct=item.discount_pct,
                    url=item.url,
                    image_url=item.image_url,
                    location_city=item.location or product.user_city,
                    captured_at=now
                )
                db.add(capture)

            # 2. Verificação de Alerta de Queda de Preço >= X%
            old_price = product.last_best_price
            if old_price and old_price > 0 and best_current.price < old_price:
                drop_pct = ((old_price - best_current.price) / old_price) * 100.0
                if drop_pct >= product.target_drop_pct:
                    # Dispara notificação via WhatsApp direto em código
                    alert_details = dispatch_price_drop_alert(
                        product_id=product.id,
                        product_name=product.name,
                        niche=product.niche,
                        store_name=best_current.store,
                        store_type=best_current.store_type,
                        old_price=old_price,
                        new_price=best_current.price,
                        drop_pct=drop_pct,
                        url=best_current.url,
                        location_city=best_current.location or product.user_city,
                        image_url=best_current.image_url,
                        phone=phone,
                        apikey=apikey,
                        provider=provider,
                        custom_url=custom_url or custom_webhook_url
                    )
                    alert_dispatched = True

            # Atualiza o último melhor preço conhecido
            if not product.last_best_price or best_current.price < product.last_best_price:
                product.last_best_price = best_current.price

            # 3. Atualização dos 3 Melhores Preços Históricos de Todos os Tempos
            existing_history = db.query(HistoricalTopPrice).filter(
                HistoricalTopPrice.product_id == product.id
            ).all()

            # Consolida candidatos históricos
            candidates = []
            for h in existing_history:
                candidates.append({
                    "store_name": h.store_name,
                    "product_title": h.product_title,
                    "price": h.price,
                    "url": h.url,
                    "captured_at": h.captured_at
                })

            for item in top_items:
                candidates.append({
                    "store_name": item.store,
                    "product_title": item.title,
                    "price": item.price,
                    "url": item.url,
                    "captured_at": now
                })

            # Remove duplicados por chave (store_name, price) e ordena pelo menor preço
            seen = set()
            unique_candidates = []
            for c in sorted(candidates, key=lambda x: x["price"]):
                key = (c["store_name"], round(c["price"], 2))
                if key not in seen:
                    seen.add(key)
                    unique_candidates.append(c)

            # Mantém apenas os 3 melhores
            top_3 = unique_candidates[:3]

            # Limpa e regrava top 3 com rank 1, 2, 3
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
            "best_price": best_current.price,
            "best_store": best_current.store,
            "alert_dispatched": alert_dispatched,
            "alert_details": alert_details
        }

    def track_specific_url(
        self,
        url: Optional[str] = None,
        target_drop_pct: float = 10.0,
        user_city: Optional[str] = None,
        user_state: Optional[str] = None,
        user_cep: Optional[str] = None,
        custom_name: Optional[str] = None,
        target_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extrai as informações de um link de produto e cadastra no monitoramento específico."""
        target_link = url or target_url
        if not target_link:
            return {"success": False, "error": "URL não fornecida.", "message": "URL não fornecida."}

        from .url_scraper import url_product_scraper
        item = url_product_scraper.scrape_url(target_link)
        if not item or item.price <= 0:
            err_msg = "Não foi possível extrair o preço e dados do produto automaticamente. Verifique se a página é pública e se o produto está disponível."
            return {
                "success": False,
                "error": err_msg,
                "message": err_msg
            }
        url = target_link

        product_name = custom_name or item.title
        with get_db() as db:
            existing = db.query(TrackedProduct).filter(
                (TrackedProduct.target_url == url) |
                ((TrackedProduct.name == product_name) & (TrackedProduct.is_url_specific == True))
            ).first()

            if existing:
                existing.active = True
                existing.target_drop_pct = target_drop_pct
                existing.current_price = item.price
                existing.last_best_price = min(existing.last_best_price or item.price, item.price)
                existing.last_checked_at = datetime.utcnow()
                if item.image_url:
                    existing.image_url = item.image_url
                prod_id = existing.id
            else:
                new_prod = TrackedProduct(
                    name=product_name,
                    niche=item.store,
                    target_drop_pct=target_drop_pct,
                    last_best_price=item.price,
                    current_price=item.price,
                    user_cep=user_cep,
                    user_city=user_city,
                    user_state=user_state,
                    active=True,
                    created_at=datetime.utcnow(),
                    last_checked_at=datetime.utcnow(),
                    target_url=url,
                    is_url_specific=True,
                    image_url=item.image_url,
                    store_name=item.store
                )
                db.add(new_prod)
                db.flush()
                prod_id = new_prod.id

            now = datetime.utcnow()
            db.add(PriceCapture(
                product_id=prod_id,
                store_name=item.store,
                store_type=item.store_type,
                product_title=item.title,
                price=item.price,
                original_price=item.original_price,
                discount_pct=item.discount_pct,
                url=url,
                image_url=item.image_url,
                location_city=user_city,
                captured_at=now
            ))

            top_h = db.query(HistoricalTopPrice).filter(HistoricalTopPrice.product_id == prod_id).first()
            if not top_h:
                db.add(HistoricalTopPrice(
                    product_id=prod_id,
                    rank=1,
                    store_name=item.store,
                    product_title=item.title,
                    price=item.price,
                    url=url,
                    captured_at=now
                ))

        return {
            "success": True,
            "product_id": prod_id,
            "item": item,
            "store": item.store,
            "price": item.price,
            "title": item.title,
            "message": "Produto monitorado com sucesso!"
        }

    def check_and_persist_tracked_url(
        self,
        product_id: int,
        phone: Optional[str] = None,
        apikey: Optional[str] = None,
        provider: Optional[str] = None,
        custom_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Varre um link específico já cadastrado, verifica quedas e dispara alerta WhatsApp se houver queda >= X%."""
        from .url_scraper import url_product_scraper

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
            if item.image_url:
                product.image_url = item.image_url

            # Grava PriceCapture
            db.add(PriceCapture(
                product_id=product.id,
                store_name=item.store,
                store_type=item.store_type,
                product_title=item.title,
                price=item.price,
                original_price=item.original_price,
                discount_pct=item.discount_pct,
                url=product.target_url,
                image_url=item.image_url,
                location_city=product.user_city,
                captured_at=now
            ))

            # Verifica queda de preço >= X%
            old_price = product.last_best_price
            alert_dispatched = False
            alert_details = None

            if old_price and old_price > 0 and item.price < old_price:
                drop_pct = ((old_price - item.price) / old_price) * 100.0
                if drop_pct >= product.target_drop_pct:
                    alert_details = dispatch_price_drop_alert(
                        product_id=product.id,
                        product_name=product.name,
                        niche=product.niche,
                        store_name=item.store,
                        store_type=item.store_type,
                        old_price=old_price,
                        new_price=item.price,
                        drop_pct=drop_pct,
                        url=product.target_url,
                        location_city=product.user_city,
                        image_url=item.image_url,
                        phone=phone,
                        apikey=apikey,
                        provider=provider,
                        custom_url=custom_url
                    )
                    alert_dispatched = True

            if not product.last_best_price or item.price < product.last_best_price:
                product.last_best_price = item.price

            # Atualiza Top 3 histórico
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
                "store_name": item.store,
                "product_title": item.title,
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
                "store": item.store,
                "alert_dispatched": alert_dispatched,
                "alert_details": alert_details
            }
