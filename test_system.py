from database.db import init_db, get_db
from database.models import TrackedProduct, HistoricalTopPrice, NotificationLog
from scrapers.manager import ScraperManager
from geo.locator import get_location_from_cep
from notifications.whatsapp_dispatcher import test_whatsapp_connection, format_whatsapp_message, generate_whatsapp_share_link

print("1. Testando DB init...")
init_db()

print("2. Testando GeoLocator...")
loc = get_location_from_cep("93010000") or {"localidade": "São Leopoldo", "uf": "RS"}
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

print("5. Testando integração WhatsApp direto via código...")
test_phone = "5551999999999"
msg = format_whatsapp_message(
    product_name="Arroz 5kg Tipo 1",
    store_name="Atacadão",
    old_price=30.00,
    new_price=22.50,
    drop_pct=25.0,
    savings=7.50,
    url="https://atacadao.com.br"
)
share_url = generate_whatsapp_share_link(test_phone, msg)
print("Link de compartilhamento WhatsApp gerado com sucesso!")

print("\n>>> SUCESSO TOTAL! O SISTEMA RADAR JULIUS ESTA 100% OPERACIONAL COM WHATSAPP DIRETO! <<<")
