import os
import textwrap
from pathlib import Path
import streamlit as st
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Carrega variáveis locais
load_dotenv()

from database.db import init_db, get_db
from database.models import TrackedProduct, PriceCapture, HistoricalTopPrice, NotificationLog
from scrapers.manager import ScraperManager
from geo.locator import get_location_from_cep, get_available_supermarkets_for_location, clean_cep
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

# CSS Customizado com tema Julius e Responsividade Mobile
st.markdown("""
<style>
    /* Estilos Gerais */
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        padding: 22px 24px;
        border-radius: 12px;
        border-left: 6px solid #22c55e;
        margin-bottom: 18px;
    }
    .main-header-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
    }
    .julius-badge {
        background-color: #22c55e;
        color: #022c22;
        font-weight: bold;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 13px;
        display: inline-block;
        white-space: nowrap;
    }
    .mobile-loc-bar {
        display: none;
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
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .price-card:hover {
        border-color: #22c55e;
        transform: translateY(-2px);
    }
    .top-1-card {
        border: 2px solid #22c55e !important;
        background-color: #064e3b22;
    }
    .card-body {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        flex-wrap: wrap;
        gap: 12px;
    }
    .card-info {
        flex: 1;
        min-width: 240px;
    }
    .card-pricing {
        text-align: right;
        min-width: 130px;
    }
    .product-title {
        margin: 8px 0 6px 0;
        color: #f8fafc;
        font-size: 18px;
        line-height: 1.35;
    }
    .store-badge-sub {
        color: #94a3b8;
        font-size: 13px;
        margin-left: 8px;
    }
    .pack-sub {
        color: #94a3b8;
        font-size: 12px;
        margin-top: 2px;
    }
    .badges-row {
        margin-top: 6px;
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }
    .price-tag {
        font-size: 26px;
        font-weight: 800;
        color: #22c55e;
        line-height: 1;
    }
    .discount-pill {
        background-color: #b91c1c;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
    }
    .unit-badge {
        background-color: #0284c7;
        color: #f0f9ff;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 13px;
        display: inline-block;
        border: 1px solid #38bdf8;
    }
    .size-badge {
        background-color: #334155;
        color: #cbd5e1;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 12px;
        display: inline-block;
    }

    /* Abas Touch-Friendly */
    div[data-baseweb="tab-list"] {
        gap: 6px !important;
        border-bottom: 1px solid #334155 !important;
        padding-bottom: 2px !important;
    }
    button[data-baseweb="tab"] {
        border-radius: 8px 8px 0 0 !important;
        font-size: 14px !important;
        padding: 10px 14px !important;
        font-weight: 600 !important;
        white-space: nowrap !important;
    }

    /* ======================================================== */
    /* REGRAS ESPECÍFICAS PARA SMARTPHONES E TELAS PEQUENAS     */
    /* ======================================================== */
    @media (max-width: 768px) {
        /* Redução de margens e padding lateral para aproveitar a tela */
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            max-width: 100% !important;
        }

        /* Prevenção de auto-zoom no iOS Safari em campos de texto */
        input, select, textarea {
            font-size: 16px !important;
        }

        /* Botões com altura mínima ergonômica para toque */
        button[kind="primary"], button[kind="secondary"], .stButton > button {
            min-height: 46px !important;
            font-size: 15px !important;
            border-radius: 8px !important;
        }
        div[data-testid="stLinkButton"] > a {
            min-height: 46px !important;
            font-size: 15px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border-radius: 8px !important;
        }

        /* Cabeçalho compacto em smartphones */
        .main-header {
            padding: 14px 16px !important;
            margin-bottom: 10px !important;
            border-left-width: 4px !important;
        }
        .main-header-content {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 8px !important;
        }
        .main-header h1 {
            font-size: 20px !important;
            line-height: 1.25 !important;
        }
        .main-header p {
            font-size: 12px !important;
            line-height: 1.4 !important;
        }

        /* Barra de Localização para Mobile (já que o sidebar fica oculto) */
        .mobile-loc-bar {
            display: flex !important;
            justify-content: space-between !important;
            align-items: center !important;
            background-color: #1e293b !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            padding: 8px 12px !important;
            margin-bottom: 12px !important;
            font-size: 13px !important;
            color: #f1f5f9 !important;
        }

        /* Abas com rolagem horizontal suave no celular */
        div[data-baseweb="tab-list"] {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
            scrollbar-width: none !important;
            gap: 4px !important;
            padding-bottom: 4px !important;
        }
        div[data-baseweb="tab-list"]::-webkit-scrollbar {
            display: none !important;
        }
        button[data-baseweb="tab"] {
            font-size: 12.5px !important;
            padding: 8px 11px !important;
            min-height: 42px !important;
        }

        /* Grade 2x2 para os 4 Cards de Métricas de Economia */
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) {
            display: grid !important;
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 8px !important;
        }
        div[data-testid="stMetric"] {
            background: #1e293b !important;
            border: 1px solid #334155 !important;
            border-radius: 10px !important;
            padding: 8px 10px !important;
            min-width: 0 !important;
        }
        div[data-testid="stMetricLabel"] p {
            font-size: 11px !important;
            color: #94a3b8 !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 17px !important;
            font-weight: 800 !important;
        }

        /* Card de Produto Mobile */
        .price-card {
            padding: 12px 14px !important;
            margin-bottom: 10px !important;
        }
        .card-body {
            flex-direction: column !important;
            gap: 6px !important;
        }
        .card-info {
            width: 100% !important;
            min-width: 100% !important;
        }
        .product-title {
            font-size: 16px !important;
            margin: 6px 0 !important;
        }
        .store-badge-sub {
            display: block !important;
            margin-left: 0 !important;
            margin-top: 4px !important;
            font-size: 12px !important;
        }
        .card-pricing {
            width: 100% !important;
            display: flex !important;
            justify-content: space-between !important;
            align-items: center !important;
            padding-top: 8px !important;
            margin-top: 6px !important;
            border-top: 1px dashed #334155 !important;
            text-align: left !important;
        }
        .price-tag {
            font-size: 22px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Barra lateral com Perfil e Geolocalização
with st.sidebar:
    julius_assets = Path(__file__).resolve().parent / "assets" / "julius.jpg"
    julius_root = Path(__file__).resolve().parent / "julius.png"
    img_path = str(julius_assets) if julius_assets.exists() else (str(julius_root) if julius_root.exists() else None)
    
    if img_path:
        st.image(img_path, width=110)
    else:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=70)
    st.title("🎯 Radar Julius")
    st.caption("Onde cada centavo conta!")
    
    st.markdown("---")
    st.subheader("📍 Sua Localização")

    # Inicialização segura na sessão
    if "user_cep" not in st.session_state:
        st.session_state["user_cep"] = "93280475"
    if "user_city" not in st.session_state:
        st.session_state["user_city"] = "Esteio"
    if "user_state" not in st.session_state:
        st.session_state["user_state"] = "RS"
    if "user_neighborhood" not in st.session_state:
        st.session_state["user_neighborhood"] = "Olímpica"

    def handle_cep_update(novo_cep: str):
        if not novo_cep:
            return
        loc_res = get_location_from_cep(novo_cep)
        if loc_res and loc_res.get("localidade"):
            st.session_state["user_cep"] = loc_res["cep"]
            st.session_state["user_city"] = loc_res["localidade"]
            st.session_state["user_state"] = loc_res["uf"]
            st.session_state["user_neighborhood"] = loc_res.get("bairro", "")
            st.session_state["cep_msg"] = ("success", f"📌 {loc_res['localidade']} - {loc_res['uf']}" + (f" ({loc_res['bairro']})" if loc_res.get("bairro") else ""))
        else:
            st.session_state["cep_msg"] = ("error", "⚠️ CEP não localizado na base dos Correios.")

    c_input_col, c_btn_col = st.columns([2.5, 1.2])
    with c_input_col:
        input_cep = st.text_input(
            "Seu CEP:",
            value=st.session_state["user_cep"],
            key="input_cep_field",
            help="Digite seu CEP com ou sem traço e clique em Buscar ou pressione Enter."
        )
    with c_btn_col:
        st.write("")
        st.write("")
        if st.button("🔍 Buscar", use_container_width=True):
            handle_cep_update(input_cep)
            st.rerun()

    # Se o valor no campo de texto for diferente do gravado, atualiza
    if input_cep and clean_cep(input_cep) != clean_cep(st.session_state["user_cep"]):
        handle_cep_update(input_cep)
        st.rerun()

    user_city = st.session_state["user_city"]
    user_state = st.session_state["user_state"]
    user_neighborhood = st.session_state.get("user_neighborhood", "")
    user_cep = st.session_state["user_cep"]

    if "cep_msg" in st.session_state:
        msg_type, msg_text = st.session_state["cep_msg"]
        if msg_type == "success":
            st.success(msg_text)
        else:
            st.warning(msg_text)
    else:
        st.success(f"📌 {user_city} - {user_state}" + (f" ({user_neighborhood})" if user_neighborhood else ""))

    with st.expander("✏️ Ajustar Cidade Manualmente", expanded=False):
        m_city = st.text_input("Nome da Cidade:", value=user_city, key="m_city_key")
        m_state = st.text_input("UF (Estado):", value=user_state, key="m_state_key")
        if st.button("Salvar Local Manual", use_container_width=True):
            st.session_state["user_city"] = m_city.strip()
            st.session_state["user_state"] = m_state.strip().upper()
            st.session_state["cep_msg"] = ("success", f"📌 {m_city.strip()} - {m_state.strip().upper()} (Manual)")
            st.rerun()
    
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

# Cabeçalho Principal com suporte a Mobile
st.markdown(f"""
<div class="main-header">
    <div class="main-header-content">
        <div>
            <h1 style="margin: 0; color: #f8fafc; font-size: 26px;">🎯 Radar Julius - Preços & Economia</h1>
            <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 14px;">
                Varredura em tempo real no Varejo e Mercados da sua região ({user_city} - {user_state}).
            </p>
        </div>
        <div>
            <span class="julius-badge">MODO ECONOMIA ATIVADO</span>
        </div>
    </div>
</div>
<div class="mobile-loc-bar">
    <div>
        📍 <strong>{user_city} - {user_state}</strong>{f' ({user_neighborhood})' if user_neighborhood else ''}
    </div>
    <div style="font-size: 11px; color: #38bdf8;">
        Alterar CEP na barra lateral ☰
    </div>
</div>
""", unsafe_allow_html=True)

# Abas Principais (Rótulos Otimizados para Mobile e Desktop)
tab_mercado, tab_varejo, tab_monitor, tab_scan, tab_n8n, tab_geo = st.tabs([
    "🛒 Mercado",
    "📺 Bens de Consumo",
    "📊 Monitorados",
    "⏱️ Varredura",
    "⚡ n8n Alertas",
    "📍 Mercados"
])

# -------------------------------------------------------------
# ABA 1: 🛒 SUPERMERCADO & ALIMENTOS (COM PREÇO POR UNIDADE/KG/L)
# -------------------------------------------------------------
with tab_mercado:
    st.subheader("🛒 Supermercados & Atacarejos (Alimentos, Bebidas & Limpeza)")
    st.caption("O Radar Julius varre os atacados e mercados da sua região e calcula o **preço normalizado por Quilo (R$/kg), Litro (R$/L) ou Unidade (R$/un)** para garantir que você encontre a melhor economia real, eliminando a pegadinha das embalagens pequenas!")

    col_m_search, col_m_niche = st.columns([3, 1.3])
    with col_m_search:
        mercado_query = st.text_input(
            "Produto de mercado procurado:",
            placeholder="Ex: Queijo mussarela, Arroz 5kg, Cerveja lata 350ml, Picanha, Azeite de oliva...",
            key="mercado_search_input"
        )
    with col_m_niche:
        mercado_niche = st.selectbox(
            "Sugestões de Produtos:",
            [
                "Personalizado",
                "🧀 Queijo Mussarela",
                "🌾 Arroz 5kg Tipo 1",
                "🥩 Picanha Bovina kg",
                "🍺 Cerveja Heineken Lata",
                "🫒 Azeite de Oliva Extra Virgem",
                "🥛 Leite Integral 1L",
                "🧼 Sabão Líquido Omo",
                "☕ Café em Pó 500g"
            ],
            key="mercado_niche_select"
        )

    # Preenche query automática se selecionou sugestão
    if mercado_niche != "Personalizado" and not mercado_query:
        if "Queijo" in mercado_niche:
            mercado_query = "Queijo mussarela"
        elif "Arroz" in mercado_niche:
            mercado_query = "Arroz 5kg"
        elif "Picanha" in mercado_niche:
            mercado_query = "Picanha bovina"
        elif "Cerveja" in mercado_niche:
            mercado_query = "Cerveja Heineken lata"
        elif "Azeite" in mercado_niche:
            mercado_query = "Azeite de oliva extra virgem"
        elif "Leite" in mercado_niche:
            mercado_query = "Leite integral"
        elif "Sabão" in mercado_niche:
            mercado_query = "Sabao liquido"
        elif "Café" in mercado_niche:
            mercado_query = "Cafe em po"

    # Linha de Controles: Unidade e Critério de Ranqueamento
    col_u1, col_u2, col_u3 = st.columns([1.8, 2.2, 1.4])
    with col_u1:
        unit_select = st.selectbox(
            "⚖️ Base de Comparação / Volume:",
            [
                "⚡ Automático (Detectar kg, L ou un)",
                "⚖️ Preço por Quilo (R$ / kg) — Frios, Carnes, Grãos",
                "🥛 Preço por Litro (R$ / L) — Bebidas, Óleos, Leite",
                "📦 Preço por Unidade (R$ / un) — Ovos, Rolos, Sabonetes"
            ],
            index=0,
            key="mercado_unit_base"
        )
        target_unit_code = "auto"
        if "Quilo" in unit_select:
            target_unit_code = "kg"
        elif "Litro" in unit_select:
            target_unit_code = "L"
        elif "Unidade" in unit_select:
            target_unit_code = "un"

    with col_u2:
        sort_mode = st.radio(
            "Critério de Ranqueamento:",
            [
                "🏆 Custo-Benefício (por kg/L/un)",
                "📦 Preço Total da Embalagem"
            ],
            horizontal=True,
            key="mercado_sort_mode"
        )
        sort_by_unit = ("Custo-Benefício" in sort_mode)

    with col_u3:
        filter_unit_match = st.checkbox(
            "Filtrar apenas itens com essa unidade",
            value=False,
            help="Desconsidera ofertas que não informarem o peso/volume selecionado."
        )

    col_btn_m, _ = st.columns([2, 3])
    with col_btn_m:
        btn_search_mercado = st.button("🚀 Buscar no Supermercado & Atacado", use_container_width=True, type="primary", key="btn_mercado_search")

    if btn_search_mercado and mercado_query:
        with st.spinner(f"Consultando Atacadão e Rissul para '{mercado_query}' ({user_city} - {user_state})..."):
            mercado_res = scraper_manager.search_all(
                query=mercado_query,
                include_retail=False,
                include_supermarkets=True,
                city=user_city,
                uf=user_state,
                top_n=8,
                target_unit=target_unit_code,
                sort_by_unit=sort_by_unit,
                filter_unit_match=filter_unit_match
            )
            st.session_state["mercado_results"] = mercado_res
            st.session_state["mercado_last_query"] = mercado_query

    # Exibição dos Resultados de Mercado
    if "mercado_results" in st.session_state:
        res = st.session_state["mercado_results"]
        stats = res.get("stats", {})
        top_prices = res.get("top_prices", [])

        if not top_prices:
            st.warning(f"⚠️ Nenhuma oferta de mercado encontrada para \"{res.get('query')}\". Tente simplificar a busca (ex: 'queijo', 'cerveja', 'arroz').")
        else:
            # Banner de Métricas
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            if res.get("sort_by_unit") and stats.get("min_unit_price", 0) > 0:
                col_m1.metric("🏆 Melhor Preço / Unidade", f"R$ {stats['min_unit_price']:.2f}")
                col_m2.metric("Preço Mais Alto / Unidade", f"R$ {stats['max_unit_price']:.2f}")
                unit_diff = stats['max_unit_price'] - stats['min_unit_price']
                col_m3.metric("Economia por Unidade", f"R$ {unit_diff:.2f}")
                col_m4.metric("Embalagem Mais Acessível", f"R$ {stats.get('min_price', 0.0):.2f}")
            else:
                col_m1.metric("Menor Preço Encontrado", f"R$ {stats.get('min_price', 0.0):.2f}")
                col_m2.metric("Preço Mais Alto", f"R$ {stats.get('max_price', 0.0):.2f}")
                col_m3.metric("Preço Médio", f"R$ {stats.get('avg_price', 0.0):.2f}")
                col_m4.metric("Economia Potencial", f"R$ {stats.get('potential_savings', 0.0):.2f}")

            order_title = "🏆 Top Melhores Ofertas (Ordenado por Custo-Benefício por Unidade)" if res.get("sort_by_unit") else "🏆 Top Melhores Ofertas (Menor Preço da Embalagem)"
            st.subheader(f"{order_title} para \"{res.get('query')}\"")

            for idx, item in enumerate(top_prices, start=1):
                is_top1 = (idx == 1)
                card_class = "price-card top-1-card" if is_top1 else "price-card"
                badge_color = "#22c55e" if is_top1 else "#0284c7"
                badge_text = "🥇 1º CAMPEÃO DO CUSTO-BENEFÍCIO" if (is_top1 and res.get("sort_by_unit")) else ("🥇 1º MENOR PREÇO" if is_top1 else f"#{idx} Oferta")
                loc_label = f" • 📍 {item.location}" if item.location else f" • 📍 {user_city} - {user_state}"
                orig_html = f'<div style="color: #94a3b8; font-size: 13px; text-decoration: line-through;">R$ {item.original_price:.2f}</div>' if item.original_price else ''
                disc_html = f'<span class="discount-pill">-{item.discount_pct}% OFF</span>' if item.discount_pct else ''

                unit_html = f'<span class="unit-badge">⚖️ {item.unit_label}</span>' if item.has_unit_price and item.unit_label else ''
                size_html = f'<span class="size-badge">📦 {item.detected_size}</span>' if item.detected_size else ''

                card_html = textwrap.dedent(f"""
                <div class="{card_class}">
                    <div class="card-body">
                        <div class="card-info">
                            <span class="julius-badge" style="background-color: {badge_color}; color: white;">
                                {badge_text}
                            </span>
                            <span class="store-badge-sub">
                                🏪 {item.store}{loc_label}
                            </span>
                            <h3 class="product-title">{item.title}</h3>
                            <div class="badges-row">
                                {unit_html}
                                {size_html}
                            </div>
                        </div>
                        <div class="card-pricing">
                            <div>
                                <span class="price-tag">R$ {item.price:.2f}</span>
                                <div class="pack-sub">Preço da Embalagem</div>
                            </div>
                            <div style="text-align: right;">
                                {orig_html}
                                {disc_html}
                            </div>
                        </div>
                    </div>
                </div>
                """).strip()

                st.markdown(card_html, unsafe_allow_html=True)
                st.link_button(f"👉 Ver Oferta no {item.store}", item.url, use_container_width=True)

            # Monitorar
            st.markdown("---")
            st.subheader("📌 Deseja monitorar este produto de mercado?")
            col_tm1, col_tm2, col_tm3 = st.columns([3, 1.5, 2])
            with col_tm1:
                prod_m_name = st.text_input("Nome do Produto Alvo:", value=res.get("query"), key="track_m_name_input")
            with col_tm2:
                drop_m_target = st.number_input("Alertar se cair >= (%)", min_value=1.0, max_value=80.0, value=10.0, step=1.0, key="track_m_drop")
            with col_tm3:
                st.write("")
                st.write("")
                if st.button("➕ Monitorar Mercado no Banco", type="primary", use_container_width=True, key="btn_track_m"):
                    with get_db() as db:
                        existing = db.query(TrackedProduct).filter(TrackedProduct.name.ilike(prod_m_name)).first()
                        if existing:
                            st.info(f"O produto '{prod_m_name}' já está cadastrado para monitoramento.")
                        else:
                            new_prod = TrackedProduct(
                                name=prod_m_name,
                                niche="Mercado & Alimentos",
                                target_drop_pct=drop_m_target,
                                last_best_price=top_prices[0].price if top_prices else 0.0,
                                user_cep=user_cep,
                                user_city=user_city,
                                user_state=user_state,
                                active=True
                            )
                            db.add(new_prod)
                            db.commit()
                            scraper_manager.process_and_persist_tracked_product(new_prod.id, res)
                            st.success(f"✅ '{prod_m_name}' cadastrado! Monitoramento ativo.")

# -------------------------------------------------------------
# ABA 2: 📺 BENS DE CONSUMO (ELETRÔNICOS, ELETRODOMÉSTICOS, MÓVEIS)
# -------------------------------------------------------------
with tab_varejo:
    st.subheader("📺 Bens de Consumo & Grandes E-commerces")
    st.caption("Varredura em tempo real nos maiores e-commerces do país (Amazon, Mercado Livre, Magalu, Shopee, Fast Shop, Casas Bahia, etc.) via motor Buscapé para eletrônicos, eletrodomésticos, informática e móveis.")

    col_v_search, col_v_niche = st.columns([3, 1.3])
    with col_v_search:
        varejo_query = st.text_input(
            "Produto de consumo que deseja cotar:",
            placeholder="Ex: Smart TV 50 4K, Geladeira Frost Free, Playstation 5 Slim, Airfryer Mondial, Sofá 3 lugares...",
            key="varejo_search_input"
        )
    with col_v_niche:
        varejo_niche = st.selectbox(
            "Sugestões de Produtos:",
            [
                "Personalizado",
                "📺 Smart TV 50 Polegadas 4K",
                "❄️ Geladeira Frost Free Duplex",
                "🎮 Playstation 5 Slim",
                "🍳 Fritadeira Airfryer 4L",
                "📱 iPhone 15 128GB",
                "💻 Notebook Dell i5 16GB",
                "🛋️ Sofá Retrátil 3 Lugares"
            ],
            key="varejo_niche_select"
        )

    # Preenche query automática se selecionou sugestão
    if varejo_niche != "Personalizado" and not varejo_query:
        if "Smart TV" in varejo_niche:
            varejo_query = "Smart TV 50 Polegadas 4K"
        elif "Geladeira" in varejo_niche:
            varejo_query = "Geladeira Frost Free"
        elif "Playstation" in varejo_niche:
            varejo_query = "Playstation 5 Slim"
        elif "Airfryer" in varejo_niche:
            varejo_query = "Fritadeira Airfryer Mondial"
        elif "iPhone" in varejo_niche:
            varejo_query = "iPhone 15 128GB"
        elif "Notebook" in varejo_niche:
            varejo_query = "Notebook Dell i5"
        elif "Sofá" in varejo_niche:
            varejo_query = "Sofa Retratil 3 Lugares"

    col_btn_v, _ = st.columns([2, 3])
    with col_btn_v:
        btn_search_varejo = st.button("🚀 Buscar Melhores Preços no Varejo", use_container_width=True, type="primary", key="btn_varejo_search")

    if btn_search_varejo and varejo_query:
        with st.spinner(f"Varrendo Amazon, Mercado Livre, Magalu e outros para '{varejo_query}'..."):
            varejo_res = scraper_manager.search_all(
                query=varejo_query,
                include_retail=True,
                include_supermarkets=False,
                top_n=6,
                sort_by_unit=False
            )
            st.session_state["varejo_results"] = varejo_res
            st.session_state["varejo_last_query"] = varejo_query

    # Exibição dos Resultados de Varejo
    if "varejo_results" in st.session_state:
        res_v = st.session_state["varejo_results"]
        stats_v = res_v.get("stats", {})
        top_v = res_v.get("top_prices", [])

        if not top_v:
            st.warning(f"⚠️ Nenhuma oferta encontrada para \"{res_v.get('query')}\". Tente pesquisar por termos como marca ou modelo exato.")
        else:
            col_v1, col_v2, col_v3, col_v4 = st.columns(4)
            col_v1.metric("Menor Preço Encontrado", f"R$ {stats_v.get('min_price', 0.0):.2f}")
            col_v2.metric("Preço Mais Alto", f"R$ {stats_v.get('max_price', 0.0):.2f}")
            col_v3.metric("Preço Médio", f"R$ {stats_v.get('avg_price', 0.0):.2f}")
            col_v4.metric("Economia Potencial", f"R$ {stats_v.get('potential_savings', 0.0):.2f}")

            st.subheader(f"🏆 Top Melhores Preços para \"{res_v.get('query')}\"")

            for idx, item in enumerate(top_v, start=1):
                is_top1 = (idx == 1)
                card_class = "price-card top-1-card" if is_top1 else "price-card"
                badge_color = "#22c55e" if is_top1 else "#3b82f6"
                badge_text = "🥇 1º CAMPEÃO DO PREÇO BAIXO" if is_top1 else f"#{idx} Menor Preço"
                orig_html = f'<div style="color: #94a3b8; font-size: 13px; text-decoration: line-through;">R$ {item.original_price:.2f}</div>' if item.original_price else ''
                disc_html = f'<span class="discount-pill">-{item.discount_pct}% OFF</span>' if item.discount_pct else ''

                card_html = textwrap.dedent(f"""
                <div class="{card_class}">
                    <div class="card-body">
                        <div class="card-info">
                            <span class="julius-badge" style="background-color: {badge_color}; color: white;">
                                {badge_text}
                            </span>
                            <span class="store-badge-sub">
                                🏪 {item.store} (Varejo Online)
                            </span>
                            <h3 class="product-title">{item.title}</h3>
                        </div>
                        <div class="card-pricing">
                            <div>
                                <span class="price-tag">R$ {item.price:.2f}</span>
                                <div class="pack-sub">Preço à vista / Oferta</div>
                            </div>
                            <div style="text-align: right;">
                                {orig_html}
                                {disc_html}
                            </div>
                        </div>
                    </div>
                </div>
                """).strip()

                st.markdown(card_html, unsafe_allow_html=True)
                st.link_button(f"👉 Ir para Loja Oficial ({item.store})", item.url, use_container_width=True)

            # Monitorar
            st.markdown("---")
            st.subheader("📌 Deseja monitorar este bem de consumo?")
            col_tv1, col_tv2, col_tv3 = st.columns([3, 1.5, 2])
            with col_tv1:
                prod_v_name = st.text_input("Nome do Produto Alvo:", value=res_v.get("query"), key="track_v_name_input")
            with col_tv2:
                drop_v_target = st.number_input("Alertar se cair >= (%)", min_value=1.0, max_value=80.0, value=10.0, step=1.0, key="track_v_drop")
            with col_tv3:
                st.write("")
                st.write("")
                if st.button("➕ Monitorar Varejo no Banco", type="primary", use_container_width=True, key="btn_track_v"):
                    with get_db() as db:
                        existing = db.query(TrackedProduct).filter(TrackedProduct.name.ilike(prod_v_name)).first()
                        if existing:
                            st.info(f"O produto '{prod_v_name}' já está cadastrado para monitoramento.")
                        else:
                            new_prod = TrackedProduct(
                                name=prod_v_name,
                                niche="Bens de Consumo",
                                target_drop_pct=drop_v_target,
                                last_best_price=top_v[0].price if top_v else 0.0,
                                user_cep=user_cep,
                                user_city=user_city,
                                user_state=user_state,
                                active=True
                            )
                            db.add(new_prod)
                            db.commit()
                            scraper_manager.process_and_persist_tracked_product(new_prod.id, res_v)
                            st.success(f"✅ '{prod_v_name}' cadastrado! Monitoramento ativo.")

# -------------------------------------------------------------
# ABA 3: PRODUTOS MONITORADOS & TOP 3 HISTÓRICO
# -------------------------------------------------------------
with tab_monitor:
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
                            cap_date = h['captured_at'].strftime('%d/%m/%Y às %H:%M') if h['captured_at'] else ''
                            h_html = textwrap.dedent(f"""
                            <div style="background-color: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155; text-align: center;">
                                <div style="font-size: 13px; font-weight: bold; color: #38bdf8;">{ranks_labels[idx]}</div>
                                <div style="font-size: 24px; font-weight: bold; color: #22c55e; margin: 6px 0;">R$ {h['price']:.2f}</div>
                                <div style="font-size: 13px; color: #cbd5e1;">🏪 {h['store_name']}</div>
                                <div style="font-size: 11px; color: #64748b; margin-top: 4px;">📅 {cap_date}</div>
                            </div>
                            """).strip()
                            st.markdown(h_html, unsafe_allow_html=True)
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
# ABA 4: MONITORAMENTO AUTOMÁTICO EM BACKGROUND
# -------------------------------------------------------------
with tab_scan:
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
# ABA 5: INTEGRAÇÃO n8n (WHATSAPP E E-MAIL)
# -------------------------------------------------------------
with tab_n8n:
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
# ABA 6: GEOLOCALIZAÇÃO & MERCADOS PRÓXIMOS
# -------------------------------------------------------------
with tab_geo:
    st.subheader(f"📍 Redes de Mercados Disponíveis para {user_city} - {user_state}")
    available_markets = get_available_supermarkets_for_location(user_state, user_city)

    for m in available_markets:
        with st.container():
            m_badge_color = "#22c55e" if m['is_direct_city_match'] else "#64748b"
            m_badge_text = "📍 Unidade Direta na Cidade" if m['is_direct_city_match'] else "🚚 Atende a Região"
            m_html = textwrap.dedent(f"""
            <div class="price-card">
                <div class="card-body" style="align-items: center;">
                    <div>
                        <h4 style="margin: 0; color: #f8fafc; font-size: 16px;">🏪 {m['name']}</h4>
                        <p style="margin: 4px 0; color: #94a3b8; font-size: 13px;">{m['description']}</p>
                        <span style="font-size: 12px; color: #38bdf8;">🌐 Cobertura: {m['coverage']}</span>
                    </div>
                    <div style="margin-top: 4px;">
                        <span class="julius-badge" style="background-color: {m_badge_color}; color: white; font-size: 12px;">
                            {m_badge_text}
                        </span>
                    </div>
                </div>
            </div>
            """).strip()
            st.markdown(m_html, unsafe_allow_html=True)

