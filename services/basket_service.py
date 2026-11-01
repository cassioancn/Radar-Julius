import concurrent.futures
from typing import List, Dict, Any, Optional
import urllib.parse

from scrapers.manager import ScraperManager
from notifications.whatsapp_dispatcher import get_julius_quote

class BasketOptimizerService:
    """
    Serviço Inteligente do Cesto de Compras (Radar Julius).
    Analisa múltiplos itens de supermercado da lista do usuário e compara:
    1. Melhor Loja Única (Maior praticidade - comprar tudo em um só lugar).
    2. Modo Julius Extremo (Cesta Fracionada - comprar cada item no mercado mais barato).
    3. Cálculo exato da Economia Real em R$ e % com citação do Julius Rock.
    """

    def __init__(self):
        self.scraper_manager = ScraperManager()

    def optimize_basket(
        self,
        item_queries: List[str],
        city: Optional[str] = "Esteio",
        uf: Optional[str] = "RS",
        include_retail: bool = False
    ) -> Dict[str, Any]:
        """
        Executa a varredura para cada item e calcula a melhor alocação de compra.
        """
        clean_items = [q.strip() for q in item_queries if q and q.strip()]
        if not clean_items:
            return {"success": False, "message": "Nenhum item informado na cesta."}

        # 1. Busca concorrente dos itens nos mercados
        item_results: Dict[str, List[Any]] = {}

        def _search_item(query: str):
            try:
                res = self.scraper_manager.search_all(
                    query=query,
                    include_retail=include_retail,
                    include_supermarkets=True,
                    city=city,
                    uf=uf,
                    top_n=5
                )
                return query, res.get("top_prices", [])
            except Exception:
                return query, []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_search_item, it) for it in clean_items]
            for f in concurrent.futures.as_completed(futures):
                q, prices = f.result()
                item_results[q] = prices

        # 2. Mapeamento por Mercado
        # store_data = { "Atacadão": { "item_name": best_price_obj, ... } }
        store_items: Dict[str, Dict[str, Any]] = {}

        for item_name, prices in item_results.items():
            for p in prices:
                store = p.store
                if store not in store_items:
                    store_items[store] = {}
                # Guarda o item mais barato daquela loja para o produto
                if item_name not in store_items[store] or p.price < store_items[store][item_name].price:
                    store_items[store][item_name] = p

        # 3. Cenário 1: Avalia cada Loja Única
        store_scores = []
        for store, products in store_items.items():
            found_count = len(products)
            total_val = sum(p.price for p in products.values())
            store_scores.append({
                "store": store,
                "found_count": found_count,
                "total_items": len(clean_items),
                "total_price": total_val,
                "coverage_pct": round((found_count / len(clean_items)) * 100, 1),
                "items": products
            })

        # Ordena pelo maior número de itens e, em caso de empate, menor valor total
        store_scores.sort(key=lambda x: (-x["found_count"], x["total_price"]))

        best_single_store = store_scores[0] if store_scores else None

        # 4. Cenário 2: Modo Julius Extremo (Cesta Fracionada / Melhor item a item)
        divided_items = []
        total_divided_price = 0.0

        for item_name in clean_items:
            candidates = []
            for store, products in store_items.items():
                if item_name in products:
                    candidates.append(products[item_name])

            if candidates:
                best_cand = min(candidates, key=lambda x: x.price)
                divided_items.append({
                    "item_name": item_name,
                    "title": best_cand.title,
                    "price": best_cand.price,
                    "store": best_cand.store,
                    "url": best_cand.url
                })
                total_divided_price += best_cand.price
            else:
                divided_items.append({
                    "item_name": item_name,
                    "title": "Não encontrado nos mercados locais",
                    "price": 0.0,
                    "store": "Indisponível",
                    "url": ""
                })

        # 5. Cálculo de Economia
        single_total = best_single_store["total_price"] if best_single_store else total_divided_price
        savings_brl = max(0.0, single_total - total_divided_price)
        savings_pct = round((savings_brl / single_total) * 100, 1) if single_total > 0 else 0.0

        # Agrupamento da cesta dividida por supermercado
        stores_group: Dict[str, List[Dict[str, Any]]] = {}
        for it in divided_items:
            if it["price"] > 0:
                st_name = it["store"]
                if st_name not in stores_group:
                    stores_group[st_name] = []
                stores_group[st_name].append(it)

        # 6. Gera texto para WhatsApp
        wa_text = self._build_whatsapp_list(
            clean_items=clean_items,
            best_single_store=best_single_store,
            total_divided_price=total_divided_price,
            savings_brl=savings_brl,
            stores_group=stores_group,
            city=city,
            uf=uf
        )

        return {
            "success": True,
            "total_requested_items": len(clean_items),
            "best_single_store": best_single_store,
            "all_single_stores": store_scores,
            "divided_basket": {
                "total_price": total_divided_price,
                "items": divided_items,
                "grouped_by_store": stores_group
            },
            "savings": {
                "amount_brl": savings_brl,
                "percentage": savings_pct,
                "julius_quote": get_julius_quote(savings_brl)
            },
            "whatsapp_text": wa_text,
            "whatsapp_link": f"https://api.whatsapp.com/send?text={urllib.parse.quote(wa_text)}"
        }

    def _build_whatsapp_list(
        self,
        clean_items: List[str],
        best_single_store: Optional[Dict[str, Any]],
        total_divided_price: float,
        savings_brl: float,
        stores_group: Dict[str, List[Dict[str, Any]]],
        city: Optional[str] = "Esteio",
        uf: Optional[str] = "RS"
    ) -> str:
        """Formata a lista de compras para envio prático pelo WhatsApp."""
        lines = [
            "🛒 *LISTA DE COMPRAS OTIMIZADA — RADAR JULIUS* 🎯",
            f"📍 *Região:* {city} - {uf}",
            f"📋 *Itens na Cesta:* {len(clean_items)} produtos\n"
        ]

        if best_single_store:
            lines.append(f"🏪 *Melhor Loja Única:* {best_single_store['store']} (Total: R$ {best_single_store['total_price']:.2f})")

        lines.append(f"🔥 *Modo Julius (Dividido):* R$ {total_divided_price:.2f}")
        if savings_brl > 0:
            lines.append(f"💵 *Economia Real:* R$ {savings_brl:.2f}\n")

        lines.append("👇 *ONDE COMPRAR CADA ITEM:*")
        for store, items in stores_group.items():
            store_subtotal = sum(i["price"] for i in items)
            lines.append(f"\n🏪 *{store}* (Subtotal: R$ {store_subtotal:.2f}):")
            for it in items:
                lines.append(f"  • {it['item_name']}: *R$ {it['price']:.2f}* — _{it['title'][:35]}_")

        lines.append(f"\n💬 _\"{get_julius_quote(savings_brl)}\" — Julius Rock_")
        return "\n".join(lines)

# Instância singleton
basket_service = BasketOptimizerService()

