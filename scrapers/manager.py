from datetime import datetime
from typing import List, Dict, Any, Optional
import concurrent.futures

from .base import ProductItem
from .retail import BuscapeScraper, MercadoLivreScraper, AmazonScraper, MagaluScraper, ShopeeScraper
from .supermarkets import AtacadaoScraper, MacromixScraper, RissulScraper, StockCenterScraper
from database.db import get_db
from database.models import TrackedProduct, PriceCapture, HistoricalTopPrice
from notifications.n8n_dispatcher import dispatch_price_drop_alert

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
        top_n: int = 5
    ) -> Dict[str, Any]:
        """
        Executa busca concorrente em todas as fontes selecionadas.
        Retorna o Top N melhores preços e lista completa.
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

        # Ordenação rigorosa por menor preço
        all_items.sort(key=lambda x: x.price)

        # Top N melhores preços
        top_items = all_items[:top_n]

        # Estatísticas da busca
        avg_price = sum(item.price for item in all_items) / len(all_items) if all_items else 0.0
        min_price = top_items[0].price if top_items else 0.0
        max_price = all_items[-1].price if all_items else 0.0
        potential_savings = max_price - min_price if all_items else 0.0

        return {
            "query": query,
            "timestamp": datetime.utcnow().isoformat(),
            "total_found": len(all_items),
            "top_prices": top_items,
            "all_results": all_items,
            "stats": {
                "min_price": round(min_price, 2),
                "max_price": round(max_price, 2),
                "avg_price": round(avg_price, 2),
                "potential_savings": round(potential_savings, 2)
            }
        }

    def process_and_persist_tracked_product(
        self,
        product_id: int,
        search_result: Dict[str, Any],
        custom_webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Grava capturas, atualiza os 3 melhores preços históricos e detecta queda >= X% para notificar n8n.
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
                    # Dispara notificação via n8n
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
                        custom_webhook_url=custom_webhook_url
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

