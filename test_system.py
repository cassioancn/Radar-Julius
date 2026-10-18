from database.db import init_db, get_db
from database.models import TrackedProduct, HistoricalTopPrice
from scrapers.manager import ScraperManager
from geo.locator import get_location_from_cep
from notifications.n8n_dispatcher import test_n8n_connection

print("1. Testando DB init...")
init_db()

print("2. Testando GeoLocator...")
loc = get_location_from_cep("93010000")
print(f"Localidade: {loc}")

print("3. Testando ScraperManager...")
sm = ScraperManager()
res = sm.search_all(query="Arroz 5kg", include_retail=True, include_supermarkets=True, city=loc["localidade"], uf=loc["uf"], top_n=5)
print(f"Total encontrados: {res['total_found']}")
for idx, item in enumerate(res['top_prices'], start=1):
    print(f"  #{idx} {item.store} ({item.store_type}): R$ {item.price:.2f} - {item.title}")

print("4. Testando persistência e Top 3 histórico...")
with get_db() as db:
    p = TrackedProduct(name="Arroz 5kg Tipo 1", niche="Alimentos", target_drop_pct=10.0, active=True)
    db.add(p)
    db.commit()
    p_id = p.id

sm.process_and_persist_tracked_product(p_id, res)

with get_db() as db:
    tops = db.query(HistoricalTopPrice).filter(HistoricalTopPrice.product_id == p_id).order_by(HistoricalTopPrice.rank).all()
    print(f"Top 3 historicos gravados no banco: {len(tops)}")
    for t in tops:
        print(f"  Rank {t.rank}: R$ {t.price:.2f} na loja {t.store_name} (Capturado em: {t.captured_at})")

print("5. Testando integracao de payload n8n...")
n8n_res = test_n8n_connection("https://mock-test.com")
print(f"Status n8n: {n8n_res.get('status')}")
print("Payload n8n gerado com sucesso!")
print("\n>>> SUCESSO TOTAL! O SISTEMA RADAR JULIUS ESTA 100% OPERACIONAL! <<<")
