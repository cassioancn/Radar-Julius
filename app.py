import os
import streamlit as st
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Carrega variáveis locais
load_dotenv()

from database.db import init_db, get_db
from database.models import TrackedProduct, PriceCapture, HistoricalTopPrice, NotificationLog
from scrapers.manager import ScraperManager
from geo.locator import get_location_from_cep, get_available_supermarkets_for_location
from notifications.n8n_dispatcher import dispatch_price_drop_alert, test_n8n_connection, get_julius_quote
from services.monitor_service import get_monitor_instance

# Configuração da página Streamlit
st.set_page_config(
    page_title="Radar Julius - Caçador de Preços Baixos",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializa banco de dados
init_db()

# Instâncias
scraper_manager = ScraperManager()
monitor = get_monitor_instance()

# CSS Customizado com tema Julius
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 24px;
        border-radius: 12px;
        border-left: 6px solid #22c55e;
        margin-bottom: 24px;
    }
    .julius-badge {
        background-color: #22c55e;
        color: #022c22;
        font-weight: bold;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 13px;
        display: inline-block;
    }
    .quote-box {
        background-color: #1e293b;
        border-left: 4px solid #eab308;
        padding: 10px 14px;
        border-radius: 6px;
        font-style: italic;
        color: #f1f5f9;
        margin-top: 8px;
    }
    .price-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
        transition: transform 0.2s ease;
    }
    .price-card:hover {
        border-color: #22c55e;
        transform: translateY(-2px);
    }
    .top-1-card {
        border: 2px solid #22c55e !important;
        background-color: #064e3b22;
    }
    .price-tag {
        font-size: 26px;
        font-weight: 800;
        color: #22c55e;
    }
    .discount-pill {
        background-color: #b91c1c;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Barra lateral com Perfil e Geolocalização
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=70)
    st.title("🎯 Radar Julius")
    st.caption("Onde cada centavo conta!")
    
    st.markdown("---")
    st.subheader("📍 Sua Localização")
    user_cep = st.text_input("Seu CEP:", value=os.getenv("DEFAULT_USER_CEP", "93010000"), help="Usado para localizar estoques e preços nos mercados próximos.")
    
    loc_info = get_location_from_cep(user_cep)
    user_city = "São Leopoldo"
    user_state = "RS"
    if loc_info:
        user_city = loc_info.get("localidade", "São Leopoldo")
        user_state = loc_info.get("uf", "RS")
        st.success(f"📌 {user_city} - {user_state}")
    
    st.markdown("---")
    st.subheader("⚙️ Monitor em Segundo Plano")
    if monitor.is_running:
        st.success("🟢 Monitor Ativo")
        if st.button("Pausar Monitor", use_container_width=True):
            monitor.stop()
            st.rerun()
    else:
        st.warning("⚪ Monitor Pausado")
        if st.button("Iniciar Monitor Contínuo", use_container_width=True):
            monitor.start(interval_minutes=60)
            st.rerun()
            
    st.markdown("---")
    st.caption(f"💡 *\"{get_julius_quote(25.0)}\"*")

# Cabeçalho Principal
st.markdown(f"""
<div class="main-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin: 0; color: #f8fafc; font-size: 28px;">🎯 Radar Julius - Comparador & Monitor de Preços</h1>
            <p style="margin: 5px 0 0 0; color: #94a3b8; font-size: 15px;">
                Varredura em tempo real no Varejo (Amazon, Mercado Livre, Shopee, Magalu) e Mercados (Atacadão, Macromix, Rissul, Stock Center).
            </p>
        </div>
        <div style="text-align: right;">
            <span class="julius-badge">MODO ECONOMIA ATIVADO</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Abas Principais
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Buscar Preços (Top 5)",
    "📊 Produtos Monitorados & Top 3 Histórico",
    "⏱️ Varredura & Monitoramento",
    "⚡ Integração n8n (WhatsApp / E-mail)",
    "📍 Mercados & Geolocalização"
])

# -------------------------------------------------------------
# ABA 1: BUSCAR PREÇOS (TOP 5)
# -------------------------------------------------------------
with tab1:
    col_search, col_niche = st.columns([3, 1])
    with col_search:
        search_query = st.text_input(
            "Digite o produto específico que deseja cotar:",
            placeholder="Ex: Arroz 5kg, Feijão Preto, Cerveja Heineken, Azeite de Oliva, Playstation 5, Smart TV 50..."
        )
    with col_niche:
        niche_option = st.selectbox(
            "Ou selecione um nicho:",
            ["Personalizado", "Alimentos Básicos", "Bebidas & Cervejas", "Limpeza", "Eletrônicos & Games", "Higiene & Fraldas", "Carnes & Churrasco"]
        )

    # Preenche query rápida se selecionar nicho
    if niche_option != "Personalizado" and not search_query:
        if niche_option == "Alimentos Básicos":
            search_query = "Arroz 5kg Tipo 1"
        elif niche_option == "Bebidas & Cervejas":
            search_query = "Cerveja Heineken Lata 350ml"
        elif niche_option == "Limpeza":
            search_query = "Detergente Líquido 500ml"
        elif niche_option == "Eletrônicos & Games":
            search_query = "Smart TV 50 Polegadas 4K"
        elif niche_option == "Higiene & Fraldas":
            search_query = "Fralda Pampers Confort Sec G"
        elif niche_option == "Carnes & Churrasco":
            search_query = "Picanha Bovina Resfriada kg"

    col_filters1, col_filters2, col_btn = st.columns([2, 2, 1.5])
    with col_filters1:
        inc_retail = st.checkbox("Incluir Grandes Varejistas (Amazon, ML, Shopee, Magalu)", value=True)
    with col_filters2:
        inc_markets = st.checkbox(f"Incluir Supermercados ({user_city} - {user_state})", value=True)
    with col_btn:
        search_btn = st.button("🚀 Buscar Melhores Preços", use_container_width=True, type="primary")

    if search_btn and search_query:
        with st.spinner(f"Varrendo lojas e atacados para '{search_query}'..."):
            results = scraper_manager.search_all(
                query=search_query,
                include_retail=inc_retail,
                include_supermarkets=inc_markets,
                city=user_city,
                uf=user_state,
                top_n=5
            )
            st.session_state["last_search_results"] = results
            st.session_state["last_search_query"] = search_query

    # Exibe resultados armazenados
    if "last_search_results" in st.session_state:
        res = st.session_state["last_search_results"]
        stats = res.get("stats", {})
        top_prices = res.get("top_prices", [])

        st.markdown("---")
        # Banner de Métricas de Economia
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Menor Preço Encontrado", f"R$ {stats.get('min_price', 0.0):.2f}")
        col_m2.metric("Preço Mais Alto", f"R$ {stats.get('max_price', 0.0):.2f}")
        col_m3.metric("Preço Médio", f"R$ {stats.get('avg_price', 0.0):.2f}")
        col_m4.metric("Economia Potencial", f"R$ {stats.get('potential_savings', 0.0):.2f}", delta=f"{round((stats.get('potential_savings', 0)/(stats.get('max_price', 1) or 1))*100, 1)}% menos")

        st.subheader(f"🏆 Top 5 Melhores Preços para \"{res.get('query')}\"")

        for idx, item in enumerate(top_prices, start=1):
            is_top1 = (idx == 1)
            card_class = "price-card top-1-card" if is_top1 else "price-card"
            
            with st.container():
                st.markdown(f"""
                <div class="{card_class}">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <span class="julius-badge" style="background-color: {'#22c55e' if is_top1 else '#3b82f6'}; color: white;">
                                {'🥇 1º CAMPEÃO DO PREÇO BAIXO' if is_top1 else f'#{idx} Menor Preço'}
                            </span>
                            <span style="color: #94a3b8; font-size: 13px; margin-left: 10px;">
                                🏪 {item.store} ({'Supermercado / Atacado' if item.store_type == 'supermarket' else 'Varejo Online'})
                                {' • 📍 ' + item.location if item.location else ''}
                            </span>
                            <h3 style="margin: 8px 0 4px 0; color: #f8fafc; font-size: 18px;">{item.title}</h3>
                        </div>
                        <div style="text-align: right;">
                            <span class="price-tag">R$ {item.price:.2f}</span>
                            {f'<div style="color: #94a3b8; font-size: 13px; text-decoration: line-through;">R$ {item.original_price:.2f}</div>' if item.original_price else ''}
                            {f'<span class="discount-pill">-{item.discount_pct}% OFF</span>' if item.discount_pct else ''}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c_link, c_track = st.columns([1, 4])
                with c_link:
                    st.link_button("👉 Ir para Oferta", item.url, use_container_width=True)
                with c_track:
                    pass

        # Botão para colocar esse produto em monitoramento contínuo
        st.markdown("---")
        st.subheader("📌 Deseja monitorar este produto automaticamente?")
        col_t1, col_t2, col_t3 = st.columns([3, 1.5, 2])
        with col_t1:
            prod_name = st.text_input("Nome do Produto Alvo:", value=res.get("query"), key="track_name_input")
        with col_t2:
            drop_target = st.number_input("Alertar se cair >= (%)", min_value=1.0, max_value=80.0, value=10.0, step=1.0)
        with col_t3:
            st.write("")
            st.write("")
            if st.button("➕ Monitorar e Gravar no Banco", type="primary", use_container_width=True):
                with get_db() as db:
                    # Verifica se já existe
                    existing = db.query(TrackedProduct).filter(TrackedProduct.name.ilike(prod_name)).first()
                    if existing:
                        st.info(f"O produto '{prod_name}' já está cadastrado para monitoramento.")
                    else:
                        new_prod = TrackedProduct(
                            name=prod_name,
                            niche=niche_option if niche_option != "Personalizado" else "Geral",
                            target_drop_pct=drop_target,
                            last_best_price=top_prices[0].price if top_prices else 0.0,
                            user_cep=user_cep,
                            user_city=user_city,
                            user_state=user_state,
                            active=True
                        )
                        db.add(new_prod)
                        db.commit()
                        
                        # Processa e grava top 3 histórico inicial
                        scraper_manager.process_and_persist_tracked_product(new_prod.id, res)
                        st.success(f"✅ '{prod_name}' cadastrado com sucesso! Top 3 preços históricos gravados no banco.")

# -------------------------------------------------------------
# ABA 2: PRODUTOS MONITORADOS & TOP 3 HISTÓRICO
# -------------------------------------------------------------
with tab2:
    st.subheader("📊 Produtos em Monitoramento Ativo")
    st.caption("O Radar Julius armazena os 3 menores preços de todos os tempos de cada produto e a data exata da captura para fins de comparação.")

    products_data = []
    with get_db() as db:
        tracked_list = db.query(TrackedProduct).order_by(TrackedProduct.created_at.desc()).all()
        for p in tracked_list:
            historical_tops = db.query(HistoricalTopPrice).filter(
                HistoricalTopPrice.product_id == p.id
            ).order_by(HistoricalTopPrice.rank).all()

            captures = db.query(PriceCapture).filter(
                PriceCapture.product_id == p.id
            ).order_by(PriceCapture.captured_at.desc()).limit(15).all()

            products_data.append({
                "id": p.id,
                "name": p.name,
                "niche": p.niche or "Geral",
                "target_drop_pct": p.target_drop_pct or 10.0,
                "last_best_price": p.last_best_price or 0.0,
                "user_city": p.user_city or "São Leopoldo",
                "user_state": p.user_state or "RS",
                "last_checked_at": p.last_checked_at,
                "active": p.active,
                "historical_tops": [{
                    "rank": h.rank,
                    "price": h.price,
                    "store_name": h.store_name,
                    "captured_at": h.captured_at
                } for h in historical_tops],
                "captures": [{
                    "captured_at": c.captured_at.strftime("%d/%m %H:%M") if c.captured_at else "",
                    "store_name": c.store_name,
                    "price": c.price
                } for c in captures]
            })

    if not products_data:
        st.info("Nenhum produto cadastrado ainda. Use a aba de busca acima para pesquisar e adicionar produtos ao radar!")
    else:
        for p in products_data:
            with st.expander(f"📦 {p['name']} — Menor Preço Atual: R$ {p['last_best_price']:.2f} (Alerta: queda >= {p['target_drop_pct']}%)", expanded=True):
                col_info1, col_info2, col_info3 = st.columns([2, 2, 2])
                with col_info1:
                    st.write(f"**Categoria / Nicho:** {p['niche']}")
                    st.write(f"**Localização Alvo:** {p['user_city']} - {p['user_state']}")
                with col_info2:
                    st.write(f"**Última Checagem:** {p['last_checked_at'].strftime('%d/%m/%Y %H:%M') if p['last_checked_at'] else 'Pendente'}")
                    st.write(f"**Status:** {'🟢 Ativo' if p['active'] else '⚪ Inativo'}")
                with col_info3:
                    if st.button(f"🔄 Rechecar Agora", key=f"recheck_{p['id']}"):
                        with st.spinner(f"Buscando preços atualizados para {p['name']}..."):
                            s_res = scraper_manager.search_all(query=p['name'], city=p['user_city'], uf=p['user_state'])
                            scraper_manager.process_and_persist_tracked_product(p['id'], s_res)
                            st.success("Atualizado!")
                            st.rerun()

                st.markdown("#### 🥇🥈🥉 Os 3 Melhores Preços Históricos Gravados")
                if p["historical_tops"]:
                    h_cols = st.columns(3)
                    ranks_labels = ["🥇 1º Menor Preço de Todos os Tempos", "🥈 2º Menor Preço Histórico", "🥉 3º Menor Preço Histórico"]
                    for idx, h in enumerate(p["historical_tops"]):
                        with h_cols[idx]:
                            st.markdown(f"""
                            <div style="background-color: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155; text-align: center;">
                                <div style="font-size: 13px; font-weight: bold; color: #38bdf8;">{ranks_labels[idx]}</div>
                                <div style="font-size: 24px; font-weight: bold; color: #22c55e; margin: 6px 0;">R$ {h['price']:.2f}</div>
                                <div style="font-size: 13px; color: #cbd5e1;">🏪 {h['store_name']}</div>
                                <div style="font-size: 11px; color: #64748b; margin-top: 4px;">📅 {h['captured_at'].strftime('%d/%m/%Y às %H:%M') if h['captured_at'] else ''}</div>
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info("Ainda não há histórico consolidado.")

                if p["captures"]:
                    st.markdown("##### 📈 Registro de Preços Capturados")
                    df_caps = pd.DataFrame([{
                        "Data/Hora": c["captured_at"],
                        "Loja": c["store_name"],
                        "Preço (R$)": c["price"]
                    } for c in p["captures"]])
                    st.dataframe(df_caps, use_container_width=True)

# -------------------------------------------------------------
# ABA 3: MONITORAMENTO AUTOMÁTICO EM BACKGROUND
# -------------------------------------------------------------
with tab3:
    st.subheader("⏱️ Configuração do Monitor Automático")
    st.markdown("""
    O serviço de monitoramento roda em background (com **APScheduler**), varrendo periodicamente os preços de todos os produtos ativos cadastrados.
    Quando detecta que o preço caiu **>= X%**, ele grava no banco de dados e aciona o webhook do **n8n**.
    """)

    col_m_ctrl1, col_m_ctrl2, col_m_ctrl3 = st.columns(3)
    with col_m_ctrl1:
        st.metric("Status do Monitor", "Ativo 🟢" if monitor.is_running else "Pausado ⚪")
    with col_m_ctrl2:
        st.metric("Intervalo de Checagem", f"{monitor.interval_minutes} minutos")
    with col_m_ctrl3:
        st.metric("Última Execução", monitor.last_run_time.strftime("%H:%M:%S") if monitor.last_run_time else "Nenhuma")

    st.markdown("---")
    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("🚀 Executar Ciclo de Varredura Agora (Manual)", type="primary", use_container_width=True):
            with st.spinner("Executando ciclo de varredura em todos os produtos monitorados..."):
                cycle_results = monitor.run_cycle()
                st.success(f"Ciclo concluído! {len(cycle_results)} produto(s) verificados.")
                st.json(cycle_results)
    with col_act2:
        new_interval = st.number_input("Ajustar intervalo do ciclo (minutos):", min_value=5, max_value=1440, value=monitor.interval_minutes)
        if st.button("Salvar Novo Intervalo", use_container_width=True):
            monitor.interval_minutes = new_interval
            if monitor.is_running:
                monitor.stop()
                monitor.start(new_interval)
            st.success(f"Intervalo ajustado para {new_interval} minutos!")

# -------------------------------------------------------------
# ABA 4: INTEGRAÇÃO n8n (WHATSAPP E E-MAIL)
# -------------------------------------------------------------
with tab4:
    st.subheader("⚡ Integração com n8n para Disparo de Notificações")
    st.markdown("""
    O Radar Julius é projetado para integração desacoplada com o **n8n**.
    Ao detectar uma queda de preço de **>= X%**, o sistema faz uma requisição HTTP POST para o Webhook configurado, entregando:
    - Dados do produto e lojas (preço antigo, preço novo, desconto %, economia em R$).
    - Mensagem pronta formatada para nós de **WhatsApp** (Evolution API / Z-API / Baileys).
    - Template HTML profissional formatado para nós de **E-mail** (SMTP / Resend / Gmail).
    - Citações temáticas do Julius Rock para engajar o usuário!
    """)

    n8n_url = st.text_input(
        "URL do Webhook do n8n:",
        value=os.getenv("N8N_WEBHOOK_URL", "https://seu-n8n.exemplo.com/webhook/radar-julius-alert"),
        help="Insira a URL do nó Webhook criado no seu workflow n8n."
    )

    col_test_btn, col_json_preview = st.columns([1, 2])
    with col_test_btn:
        if st.button("🧪 Disparar Alerta de Teste para o n8n", use_container_width=True):
            with st.spinner("Enviando webhook de teste..."):
                test_res = test_n8n_connection(n8n_url)
                if test_res.get("success"):
                    st.success("🎉 Webhook disparado com sucesso para o n8n!")
                    st.json(test_res)
                else:
                    st.warning(f"Status do disparo: {test_res.get('status')} - {test_res.get('message', 'Erro ao conectar')}")
                    st.json(test_res)

    with col_json_preview:
        st.markdown("##### 📄 Exemplo do Payload enviado para o n8n:")
        mock_payload = {
            "event": "PRICE_DROP_ALERT",
            "product": {"name": "Arroz Branco 5kg Tipo 1", "niche": "Alimentos"},
            "pricing": {
                "store_name": "Atacadão",
                "old_price": 32.90,
                "new_price": 24.50,
                "discount_percentage": 25.5,
                "savings_reais": 8.40
            },
            "location": {"city": "São Leopoldo - RS"},
            "formatted_messages": {
                "whatsapp": "🚨 *RADAR JULIUS: QUEDA DE PREÇO DETECTADA!* ...",
                "email_html": "<div>...</div>"
            }
        }
        st.code(mock_payload, language="json")

# -------------------------------------------------------------
# ABA 5: GEOLOCALIZAÇÃO & MERCADOS PRÓXIMOS
# -------------------------------------------------------------
with tab5:
    st.subheader(f"📍 Redes de Mercados Disponíveis para {user_city} - {user_state}")
    available_markets = get_available_supermarkets_for_location(user_state, user_city)

    for m in available_markets:
        with st.container():
            st.markdown(f"""
            <div class="price-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="margin: 0; color: #f8fafc;">🏪 {m['name']}</h4>
                        <p style="margin: 4px 0; color: #94a3b8; font-size: 14px;">{m['description']}</p>
                        <span style="font-size: 12px; color: #38bdf8;">🌐 Cobertura: {m['coverage']}</span>
                    </div>
                    <div>
                        <span class="julius-badge" style="background-color: {'#22c55e' if m['is_direct_city_match'] else '#64748b'}; color: white;">
                            {'📍 Unidade Direta na Cidade' if m['is_direct_city_match'] else '🚚 Atende a Região'}
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

