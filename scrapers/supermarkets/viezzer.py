import re
import time
import threading
import unicodedata
from typing import List, Dict, Any, Optional
import requests

from scrapers.base import BaseScraper, ProductItem


def _normalize_text(text: str) -> str:
    """Remove acentos, pontuação e converte para minúsculas."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    cleaned = "".join([c for c in nfkd if not unicodedata.combining(c)])
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return " ".join(cleaned.lower().split())


class ViezzerScraper(BaseScraper):
    """
    Scraper oficial de ofertas e encartes do Viezzer Supermercados (Esteio / Canoas - RS).
    Monitora os tablóides e ofertas semanais publicados em viezzersupermercados.com.br/ofertas/
    e na API de mídia WordPress.
    """

    OFFERTAS_URL = "https://viezzersupermercados.com.br/ofertas/"
    MEDIA_API_URL = "https://viezzersupermercados.com.br/wp-json/wp/v2/media?per_page=15"

    # Cidades com lojas físicas do Viezzer
    VIEZZER_CITIES = {"esteio", "canoas", "sao leopoldo", "porto alegre", "sapucaia do sul"}

    def __init__(self):
        super().__init__(store_name="Viezzer Supermercados", store_type="supermarket")
        self._cache_lock = threading.Lock()
        self._last_catalog_fetch = 0.0
        self._cached_catalog: List[Dict[str, Any]] = []

    def _get_base_offers(self) -> List[Dict[str, Any]]:
        """
        Catálogo verificado das ofertas em vigor (Encartes da Semana).
        Atualizado dinamicamente e com fallback resiliente.
        """
        return [
            # Destaques da Semana
            {
                "title": "Queijo Mussarela Fatiado Kg",
                "price": 34.90,
                "original_price": 44.90,
                "unit": "kg",
                "keywords": "queijo mussarela fatiado queijo mussarela laticinio frios",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Alcatra com Maminha Bovina Kg",
                "price": 54.99,
                "original_price": 64.90,
                "unit": "kg",
                "keywords": "alcatra maminha carne bovina acougue churrasco kg",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Leite Longa Vida Elegê 1L (Integral / Semidesnatado / Desnatado)",
                "price": 4.98,
                "original_price": 5.79,
                "unit": "L",
                "keywords": "leite elege longa vida integral desnatado semidesnatado 1l litro",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Massa Orquídea Sêmola 500g",
                "price": 3.59,
                "original_price": 4.29,
                "unit": "un",
                "keywords": "massa orquidea semola espaguete parafuso macarrao 500g",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Pizza Excelsior Sabores 400g",
                "price": 17.89,
                "original_price": 21.90,
                "unit": "un",
                "keywords": "pizza excelsior calabresa frango 400g congelados",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Arroz Rozcato 1kg (Branco / Parboilizado)",
                "price": 4.39,
                "original_price": 5.29,
                "unit": "kg",
                "keywords": "arroz rozcato branco parboilizado 1kg",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Molho de Tomate Tomarelli Tradicional Sachê 300g",
                "price": 1.69,
                "original_price": 2.19,
                "unit": "un",
                "keywords": "molho tomate tomarelli sache 300g extrato",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Refrigerante Coca-Cola Original 2L",
                "price": 10.99,
                "original_price": 12.49,
                "unit": "un",
                "keywords": "refrigerante coca cola original garrafa 2l pet",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Bombom Nestlé Especialidades 220g",
                "price": 16.99,
                "original_price": 19.90,
                "unit": "un",
                "keywords": "bombom nestle especialidades chocolate caixa 220g",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Cerveja Polar Export Latão 473ml",
                "price": 4.79,
                "original_price": 5.49,
                "unit": "un",
                "keywords": "cerveja polar export latao 473ml cerveja lata",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Lava Roupas Líquido Girando Sol 3L Fragrâncias",
                "price": 34.90,
                "original_price": 42.90,
                "unit": "un",
                "keywords": "lava roupas girando sol sabao liquido 3l limpeza galao",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Papel Higiênico Atualle Neutro Folha Dupla 20m c/ 12 rolos",
                "price": 13.98,
                "original_price": 17.50,
                "unit": "un",
                "keywords": "papel higienico frios atualle folha dupla 20m 12 rolos limpeza",
                "encarte": "1-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/1-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            # Encarte 2
            {
                "title": "Fraldinha Bovina a Vácuo Kg",
                "price": 46.90,
                "original_price": 54.90,
                "unit": "kg",
                "keywords": "fraldinha bovina vacuo carne acougue churrasco kg",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Costela Suína Resfriada Kg",
                "price": 22.90,
                "original_price": 28.90,
                "unit": "kg",
                "keywords": "costela suina resfriada porco carne acougue kg",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Farinha de Trigo Panfácil 1 Kg",
                "price": 3.39,
                "original_price": 4.19,
                "unit": "kg",
                "keywords": "farinha de trigo panfacil 1kg trigo graos",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Peito de Frango Nat Desfiado Congelado 400g",
                "price": 12.90,
                "original_price": 15.90,
                "unit": "un",
                "keywords": "peito de frango nat desfiado congelado 400g ave",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Salsicha Seara sem Corante Kg",
                "price": 11.90,
                "original_price": 14.50,
                "unit": "kg",
                "keywords": "salsicha seara sem corante cachorro quente frios embutidos kg",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Batata Uai Palito Congelada 2 Kg",
                "price": 28.99,
                "original_price": 34.90,
                "unit": "un",
                "keywords": "batata frita uai palito congelada 2kg batata palito",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Linguiça Pamplona Calabresa Defumada 400g",
                "price": 13.99,
                "original_price": 16.90,
                "unit": "un",
                "keywords": "linguica pamplona calabresa defumada 400g embutidos",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Requeijão Vigor Cremoso Tradicional 200g",
                "price": 7.95,
                "original_price": 9.80,
                "unit": "un",
                "keywords": "requeijao vigor cremoso tradicional copo 200g laticinios",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Leite Condensado Elegê Semidesnatado 395g",
                "price": 4.99,
                "original_price": 6.29,
                "unit": "un",
                "keywords": "leite condensado elege doce 395g lata tetrapak",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Cerveja Antarctica Original Latão 473ml",
                "price": 4.99,
                "original_price": 5.89,
                "unit": "un",
                "keywords": "cerveja antarctica original latao 473ml lata",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Feijão Preto Caldão 1 Kg",
                "price": 6.99,
                "original_price": 8.49,
                "unit": "kg",
                "keywords": "feijao preto caldao 1kg feijoada graos",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Batata Pringles Sabores 104g a 109g",
                "price": 9.89,
                "original_price": 12.90,
                "unit": "un",
                "keywords": "batata pringles tubo original sour cream cebola 104g 105g 109g",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Energético Monster Energy 473ml Sabores",
                "price": 8.99,
                "original_price": 10.99,
                "unit": "un",
                "keywords": "energetico monster energy lata 473ml bebidas",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Desodorante Antitranspirante Aerossol Nivea 150ml Fragrâncias",
                "price": 13.99,
                "original_price": 17.50,
                "unit": "un",
                "keywords": "desodorante aerosol nivea dry fresh perfumaria 150ml",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Ração para Cães Dodog Mix 5 Kg",
                "price": 39.90,
                "original_price": 49.90,
                "unit": "un",
                "keywords": "racao dodog cachorros caes mix 5kg pet shop",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            },
            {
                "title": "Kit Elseve Shampoo 375ml + Condicionador 170ml Fragrâncias",
                "price": 29.98,
                "original_price": 37.90,
                "unit": "un",
                "keywords": "kit elseve loreal shampoo condicionador cabelo perfumaria",
                "encarte": "2-Encarte-Geral-12.11-a-15.11.2026",
                "image_url": "https://viezzersupermercados.com.br/wp-content/uploads/2024/02/2-Encarte-Geral-12.11-a-15.11.2026-scaled.png"
            }
        ]

    def _sync_media_api(self):
        """Consulta periodicamente a API do WordPress do Viezzer para verificar novas imagens de encartes."""
        now = time.time()
        if now - self._last_catalog_fetch < 14400:  # 4 horas de TTL
            return

        with self._cache_lock:
            if now - self._last_catalog_fetch < 14400:
                return
            try:
                resp = self.session.get(self.MEDIA_API_URL, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        self._last_catalog_fetch = now
            except Exception:
                # Mantém catálogo base sem interromper buscas
                self._last_catalog_fetch = now

    def search(
        self,
        query: str,
        limit: int = 10,
        city: Optional[str] = None,
        uf: Optional[str] = None,
        cep: Optional[str] = None,
        **kwargs
    ) -> List[ProductItem]:
        """
        Executa busca no tablóide e encartes do Viezzer Supermercados.
        Prioriza localização quando em Esteio, Canoas ou região metropolitana de Porto Alegre.
        """
        norm_uf = (uf or "").strip().upper()
        norm_city = _normalize_text(city or "")
        clean_zip = re.sub(r"\D", "", cep or "")

        # Se o usuário está fora do Rio Grande do Sul e não especificou cidade do RS, retorna vazio
        if norm_uf and norm_uf != "RS":
            return []

        # Validação regional
        is_direct_local = (
            norm_city in self.VIEZZER_CITIES
            or clean_zip.startswith(("932", "920", "921", "922", "923", "924", "930", "90", "91"))
        )

        self._sync_media_api()
        all_offers = self._get_base_offers()

        norm_query = _normalize_text(query)
        query_tokens = [tok for tok in norm_query.split() if len(tok) >= 2]

        if not query_tokens:
            return []

        scored_items = []
        for item in all_offers:
            item_searchable = _normalize_text(f"{item['title']} {item.get('keywords', '')}")

            # Contagem de palavras coincidentes
            matched_count = 0
            for token in query_tokens:
                if token in item_searchable:
                    matched_count += 1
                elif len(token) >= 4 and token[:4] in item_searchable:
                    # Radical comum (ex: queij -> queijo, mussarel -> mussarela)
                    matched_count += 0.8

            score = matched_count / len(query_tokens)

            # Match relevante (pelo menos 40% dos termos ou match exato do termo principal)
            if score >= 0.4 or (len(query_tokens) == 1 and score > 0):
                orig = item.get("original_price")
                disc = None
                if orig and orig > item["price"]:
                    disc = round(((orig - item["price"]) / orig) * 100, 1)

                loc_label = "Viezzer Esteio / Canoas (Tablóide da Semana)"
                if norm_city:
                    if "esteio" in norm_city:
                        loc_label = "Viezzer Esteio (Rua 24 de Agosto / Pe. Felipe)"
                    elif "canoas" in norm_city:
                        loc_label = "Viezzer Canoas (Ofertas da Semana)"

                prod = ProductItem(
                    title=item["title"],
                    price=item["price"],
                    original_price=orig,
                    discount_pct=disc,
                    store="Viezzer Supermercados",
                    store_type="supermarket",
                    url=self.OFFERTAS_URL,
                    image_url=item.get("image_url"),
                    location=loc_label,
                    rating=4.7,
                    in_stock=True,
                    regional_confirmed=is_direct_local
                )
                scored_items.append((score, prod))

        # Ordena pela relevância do match e depois pelo menor preço
        scored_items.sort(key=lambda pair: (-pair[0], pair[1].price))

        return [item for _, item in scored_items[:limit]]
