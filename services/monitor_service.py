import os
import time
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler

from database.db import get_db
from database.models import TrackedProduct
from scrapers.manager import ScraperManager

class BackgroundPriceMonitor:
    """Serviço em background para varredura e monitoramento contínuo de preços."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BackgroundPriceMonitor, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self.scheduler = BackgroundScheduler(daemon=True)
        self.scraper_manager = ScraperManager()
        self.is_running = False
        self.interval_minutes = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
        self.last_run_time: Optional[datetime] = None
        self.last_run_results: List[Dict[str, Any]] = []
        self._initialized = True

    def start(self, interval_minutes: Optional[int] = None):
        """Inicia o agendador em background."""
        if interval_minutes:
            self.interval_minutes = interval_minutes

        if not self.scheduler.running:
            self.scheduler.add_job(
                func=self.run_cycle,
                trigger="interval",
                minutes=self.interval_minutes,
                id="price_radar_cycle",
                replace_existing=True
            )
            self.scheduler.start()
            self.is_running = True

    def stop(self):
        """Interrompe o agendador em background."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False

    def run_cycle(self) -> List[Dict[str, Any]]:
        """Executa um ciclo completo de varredura para todos os produtos ativos."""
        results = []
        self.last_run_time = datetime.utcnow()

        # Busca produtos ativos
        products_to_check = []
        with get_db() as db:
            active_products = db.query(TrackedProduct).filter(TrackedProduct.active == True).all()
            for p in active_products:
                products_to_check.append({
                    "id": p.id,
                    "name": p.name,
                    "city": p.user_city,
                    "state": p.user_state,
                    "target_drop": p.target_drop_pct
                })

        for prod in products_to_check:
            try:
                # 1. Executa busca ampla nos varejistas e supermercados
                search_res = self.scraper_manager.search_all(
                    query=prod["name"],
                    city=prod.get("city"),
                    uf=prod.get("state"),
                    top_n=5
                )

                # 2. Persiste capturas, atualiza Top 3 histórico e alerta se queda >= X%
                proc_res = self.scraper_manager.process_and_persist_tracked_product(
                    product_id=prod["id"],
                    search_result=search_res
                )

                results.append({
                    "product_id": prod["id"],
                    "product_name": prod["name"],
                    "best_price": proc_res.get("best_price"),
                    "best_store": proc_res.get("best_store"),
                    "alert_dispatched": proc_res.get("alert_dispatched", False),
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S")
                })
            except Exception as e:
                results.append({
                    "product_id": prod["id"],
                    "product_name": prod["name"],
                    "error": str(e)
                })

        self.last_run_results = results
        return results

def get_monitor_instance() -> BackgroundPriceMonitor:
    """Retorna a instância singleton do monitor."""
    return BackgroundPriceMonitor()

