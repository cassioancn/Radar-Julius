import math
import re
import threading
import time
import unicodedata
from typing import Dict, Any, List, Optional
import requests

# Base de conhecimento de presença regional das redes de mercados
SUPERMARKET_REGIONS = {
    "Super Rissul": {
        "coverage": "Rio Grande do Sul (Grande POA, Vale dos Sinos, Serra e Litoral)",
        "description": "Supermercado varejista do Grupo Unidasul (com regionalização online por CEP)",
        "states": ["RS"],
        "cities": [
            "Esteio", "Porto Alegre", "Canoas", "São Leopoldo", "Novo Hamburgo",
            "Sapucaia do Sul", "Gramado", "Canela", "Parobé", "Igrejinha", "Taquara"
        ],
        "supports_geo_catalog": True,
        "default_zip": "93010000"
    },
    "Zaffari / Bourbon": {
        "coverage": "Rio Grande do Sul e São Paulo (Porto Alegre, Canoas, São Leopoldo, Novo Hamburgo...)",
        "description": "Rede Cia. Zaffari com busca online regionalizada (Clique & Retire / Delivery)",
        "states": ["RS", "SP"],
        "cities": [
            "Porto Alegre", "Canoas", "São Leopoldo", "Novo Hamburgo", "Gravataí",
            "Viamão", "Caxias do Sul", "Passo Fundo", "Esteio", "Sapucaia do Sul", "São Paulo"
        ],
        "supports_geo_catalog": True,
        "default_zip": "90010150"
    },
    "Atacadão": {
        "coverage": "Nacional (Lojas físicas em Porto Alegre, Canoas, Sapucaia, Novo Hamburgo, Gravataí...)",
        "description": "Atacadista alimentar com unidades físicas em todo o Brasil (catálogo online)",
        "states": ["RS", "SC", "PR", "SP", "RJ", "MG", "BA", "PE", "CE", "GO", "DF", "ES", "MT", "MS", "PA", "AM"],
        "cities": [
            "Porto Alegre", "Canoas", "Sapucaia do Sul", "Esteio", "São Leopoldo", "Novo Hamburgo",
            "Gravataí", "Viamão", "Alvorada", "Caxias do Sul", "Pelotas", "Santa Maria", "Passo Fundo", "Rio Grande"
        ],
        "supports_geo_catalog": True,
        "default_zip": "01001000"
    },
    "Macromix Atacado": {
        "coverage": "Rio Grande do Sul (Esteio, Sapucaia, Canoas, São Leopoldo, Novo Hamburgo, Litoral)",
        "description": "Rede atacadista física do Grupo Unidasul (sem e-commerce público aberto)",
        "states": ["RS"],
        "cities": [
            "Esteio", "Porto Alegre", "São Leopoldo", "Novo Hamburgo", "Canoas", "Sapucaia do Sul",
            "Campo Bom", "Torres", "Tramandaí", "Xangri-lá", "Taquara", "Alvorada", "Gravataí"
        ],
        "supports_geo_catalog": False,
        "default_zip": "93020000"
    },
    "Stock Center": {
        "coverage": "Rio Grande do Sul e Santa Catarina (Canoas, Gravataí, POA, Passo Fundo...)",
        "description": "Atacarejo físico da Comercial Zaffari (sem e-commerce público aberto)",
        "states": ["RS", "SC"],
        "cities": [
            "Esteio", "Canoas", "Porto Alegre", "Gravataí", "Passo Fundo", "Caxias do Sul",
            "Pelotas", "Santa Maria", "Rio Grande", "Cruz Alta", "Chapecó", "Lages"
        ],
        "supports_geo_catalog": False,
        "default_zip": "99010000"
    }
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"
}

OSM_HEADERS = {
    "User-Agent": "RadarJulius/2.0 (Price Radar Local Discovery)",
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9"
}

_CACHE_LOCK = threading.Lock()
_CEP_CACHE: Dict[str, tuple] = {}
_NEARBY_CACHE: Dict[tuple, tuple] = {}
_CACHE_TTL_SECONDS = 1800

_GROCERY_SHOP_TYPES = {
    "supermarket",
    "wholesale",
    "convenience",
    "greengrocer",
    "beverages",
    "department_store",
    "butcher",
    "bakery"
}

_BLOCKED_OSM_CLASSES = {"highway", "leisure", "boundary", "landuse", "waterway", "natural", "railway"}

_MARKET_NAME_KEYWORDS = (
    "supermercado", "mercado", "atacado", "atacadao", "atacarejo", "rissul",
    "macromix", "zaffari", "bourbon", "stok center", "stock center", "asun",
    "unisuper", "viezzer", "carrefour", "nacional", "ofertao", "hiper",
    "bistek", "komprao", "fort", "gecepel", "fruteira", "sacolao", "mercearia",
    "minimercado", "mini mercado", "dia"
)


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    ascii_text = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_text).strip().lower()


def clean_cep(cep: str) -> str:
    """Remove caracteres especiais do CEP."""
    if not cep:
        return ""
    return re.sub(r"\D", "", str(cep))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância em quilômetros entre duas coordenadas geográficas."""
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def _geocode_nominatim(query: str) -> Optional[tuple]:
    """Resolve latitude e longitude aproximadas via OpenStreetMap Nominatim."""
    if not query or not query.strip():
        return None
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "br"},
            headers=OSM_HEADERS,
            timeout=5
        )
        if resp.status_code == 200:
            results = resp.json()
            if isinstance(results, list) and results:
                return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None


def _extract_brasilapi_coords(data: Dict[str, Any]) -> tuple:
    """Extrai (lat, lon) de resposta v2 da BrasilAPI quando disponível."""
    try:
        coords = data.get("location", {}).get("coordinates", {})
        lat_raw = coords.get("latitude")
        lon_raw = coords.get("longitude")
        if lat_raw is not None and lon_raw is not None:
            return float(lat_raw), float(lon_raw)
    except (TypeError, ValueError):
        pass
    return None, None


def get_location_from_cep(cep: str) -> Optional[Dict[str, Any]]:
    """
    Consulta serviços de CEP (BrasilAPI -> ViaCEP -> OpenCEP) com redundância e coordenadas.
    Retorna dicionário com cep, logradouro, bairro, localidade, uf, ddd, lat e lon.
    """
    cleaned = clean_cep(cep)
    if len(cleaned) != 8:
        return None

    now = time.time()
    with _CACHE_LOCK:
        cached = _CEP_CACHE.get(cleaned)
        if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
            return dict(cached[1])

    result: Optional[Dict[str, Any]] = None

    # 1. Provedor 1: BrasilAPI v2 (retorna coordenadas geográficas na maioria dos CEPs)
    try:
        url_brasilapi = f"https://brasilapi.com.br/api/cep/v2/{cleaned}"
        resp = requests.get(url_brasilapi, headers=DEFAULT_HEADERS, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            city = data.get("city")
            uf = (data.get("state") or "").upper()
            if city and uf:
                lat, lon = _extract_brasilapi_coords(data)
                result = {
                    "cep": f"{cleaned[:5]}-{cleaned[5:]}",
                    "logradouro": data.get("street") or "",
                    "bairro": data.get("neighborhood") or "",
                    "localidade": city,
                    "uf": uf,
                    "ddd": "",
                    "lat": lat,
                    "lon": lon
                }
    except Exception:
        pass

    # 2. Provedor 2: ViaCEP
    if not result:
        try:
            url_viacep = f"https://viacep.com.br/ws/{cleaned}/json/"
            resp = requests.get(url_viacep, headers=DEFAULT_HEADERS, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if "erro" not in data and data.get("localidade"):
                    result = {
                        "cep": data.get("cep") or f"{cleaned[:5]}-{cleaned[5:]}",
                        "logradouro": data.get("logradouro") or "",
                        "bairro": data.get("bairro") or "",
                        "localidade": data.get("localidade"),
                        "uf": (data.get("uf") or "").upper(),
                        "ddd": data.get("ddd") or "",
                        "lat": None,
                        "lon": None
                    }
        except Exception:
            pass

    # 3. Provedor 3: OpenCEP
    if not result:
        try:
            url_opencep = f"https://opencep.com/v1/{cleaned}"
            resp = requests.get(url_opencep, headers=DEFAULT_HEADERS, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("localidade"):
                    result = {
                        "cep": data.get("cep") or f"{cleaned[:5]}-{cleaned[5:]}",
                        "logradouro": data.get("logradouro") or "",
                        "bairro": data.get("bairro") or "",
                        "localidade": data.get("localidade"),
                        "uf": (data.get("uf") or "").upper(),
                        "ddd": "",
                        "lat": None,
                        "lon": None
                    }
        except Exception:
            pass

    if not result:
        return None

    # Garante coordenadas caso o provedor principal não tenha fornecido
    if result.get("lat") is None or result.get("lon") is None:
        street = result.get("logradouro", "")
        city = result.get("localidade", "")
        uf = result.get("uf", "")
        coords = None
        if street and city:
            coords = _geocode_nominatim(f"{street}, {city}, {uf}, Brazil")
        if not coords and city:
            coords = _geocode_nominatim(f"{city}, {uf}, Brazil")
        if coords:
            result["lat"], result["lon"] = coords

    with _CACHE_LOCK:
        _CEP_CACHE[cleaned] = (now, dict(result))

    return dict(result)


def detect_online_integration(market_name: str, brand: str = "") -> Dict[str, Any]:
    """Identifica se o mercado físico descoberto possui integração de preços online no Radar Julius."""
    norm = _normalize_text(f"{market_name} {brand}")

    if "rissul" in norm:
        return {
            "chain": "Super Rissul",
            "has_online_scraper": True,
            "status_label": "Busca Online Regionalizada (VTEX)",
            "status_type": "online"
        }
    if "zaffari" in norm or "bourbon" in norm:
        if "comercial zaffari" in norm or "stok" in norm or "stock" in norm:
            return {
                "chain": "Stock Center / Comercial Zaffari",
                "has_online_scraper": False,
                "status_label": "Loja Física (sem e-commerce aberto)",
                "status_type": "physical"
            }
        return {
            "chain": "Zaffari / Bourbon",
            "has_online_scraper": True,
            "status_label": "Busca Online Regionalizada (VTEX)",
            "status_type": "online"
        }
    if "atacadao" in norm:
        return {
            "chain": "Atacadão",
            "has_online_scraper": True,
            "status_label": "Catálogo Online Integrado (Atacadão)",
            "status_type": "online"
        }

    physical_chains = [
        ("macromix", "Macromix Atacado"),
        ("stok center", "Stok Center"),
        ("stock center", "Stock Center"),
        ("asun", "Asun Supermercados"),
        ("unisuper", "UniSuper"),
        ("viezzer", "Viezzer Supermercados"),
        ("carrefour", "Carrefour"),
        ("nacional", "Nacional"),
        ("bistek", "Bistek"),
        ("big", "BIG / Bompreço"),
    ]
    for key, label in physical_chains:
        if key in norm:
            return {
                "chain": label,
                "has_online_scraper": False,
                "status_label": "Loja Física (sem e-commerce público aberto)",
                "status_type": "physical"
            }

    return {
        "chain": brand or "Mercado Local",
        "has_online_scraper": False,
        "status_label": "Mercado Local (apenas loja física)",
        "status_type": "physical"
    }


def _is_valid_osm_market(item: Dict[str, Any]) -> bool:
    """Filtra ruídos geográficos (ruas sem nome comercial, praças, parques) mantendo lojas reais."""
    osm_class = (item.get("class") or "").lower()
    osm_type = (item.get("type") or "").lower()
    extratags = item.get("extratags") or {}
    raw_name = (item.get("name") or extratags.get("brand") or "").strip()
    norm_name = _normalize_text(raw_name)

    if not norm_name or len(norm_name) < 2:
        return False

    if osm_class in _BLOCKED_OSM_CLASSES:
        return False

    # Evita elementos tagueados como shop mas que só herdaram nome de logradouro
    if re.match(r"^(rua|avenida|av\.?|travessa|estrada|rodovia|br-\d+|alameda|beco)\b", norm_name):
        return False

    if osm_class == "shop" and osm_type in _GROCERY_SHOP_TYPES:
        return True

    # Aceita outros elementos apenas se o nome indicar claramente supermercado/atacado
    return any(kw in norm_name for kw in _MARKET_NAME_KEYWORDS)


def _format_osm_address(addr: Dict[str, Any]) -> Dict[str, str]:
    road = addr.get("road") or addr.get("pedestrian") or ""
    number = addr.get("house_number") or ""
    street = f"{road}, {number}".strip(", ") if road else ""
    neighborhood = addr.get("suburb") or addr.get("neighbourhood") or addr.get("quarter") or ""
    city = addr.get("city") or addr.get("town") or addr.get("municipality") or addr.get("village") or ""
    state = addr.get("state") or ""
    return {
        "street": street,
        "neighborhood": neighborhood,
        "city": city,
        "state": state
    }


def discover_nearby_supermarkets(
    cep: str = "",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    city: str = "",
    uf: str = "",
    radius_km: float = 5.0,
    limit: int = 40
) -> Dict[str, Any]:
    """
    Descobre supermercados, atacarejos e mercados físicos reais ao redor das coordenadas do CEP,
    ordenados pela menor distância em quilômetros (Haversine), cruzando limites de municípios no raio.
    """
    cleaned = clean_cep(cep)
    radius_km = max(1.0, min(float(radius_km or 5.0), 30.0))

    resolved_city = city or ""
    resolved_uf = (uf or "").upper()
    resolved_neighborhood = ""

    if (lat is None or lon is None) and cleaned:
        loc = get_location_from_cep(cleaned)
        if loc:
            lat = loc.get("lat")
            lon = loc.get("lon")
            resolved_city = resolved_city or loc.get("localidade", "")
            resolved_uf = resolved_uf or loc.get("uf", "")
            resolved_neighborhood = loc.get("bairro", "")

    if (lat is None or lon is None) and resolved_city:
        coords = _geocode_nominatim(f"{resolved_city}, {resolved_uf}, Brazil")
        if coords:
            lat, lon = coords

    if lat is None or lon is None:
        return {
            "center": {
                "cep": cep,
                "city": resolved_city,
                "uf": resolved_uf,
                "neighborhood": resolved_neighborhood,
                "lat": None,
                "lon": None
            },
            "radius_km": radius_km,
            "markets": [],
            "summary": {
                "total": 0,
                "online_integrated": 0,
                "physical_only": 0,
                "cities_covered": []
            }
        }

    cache_key = (round(float(lat), 4), round(float(lon), 4), round(radius_km, 1))
    now = time.time()
    with _CACHE_LOCK:
        cached = _NEARBY_CACHE.get(cache_key)
        if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
            cached_data = dict(cached[1])
            cached_data["markets"] = [dict(m) for m in cached_data["markets"][:limit]]
            return cached_data

    # Caixa envolvente aproximada para cobrir o raio em km
    search_margin_km = radius_km * 1.15
    d_lat = search_margin_km / 111.0
    d_lon = search_margin_km / max(0.2, 111.0 * abs(math.cos(math.radians(lat))))
    viewbox = f"{lon - d_lon},{lat + d_lat},{lon + d_lon},{lat - d_lat}"

    raw_by_osm_id: Dict[Any, Dict[str, Any]] = {}
    for term in ("supermercado", "atacado", "mercado"):
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": term,
                    "format": "json",
                    "limit": 50,
                    "viewbox": viewbox,
                    "bounded": 1,
                    "addressdetails": 1,
                    "extratags": 1
                },
                headers=OSM_HEADERS,
                timeout=8
            )
            if resp.status_code == 200:
                payload = resp.json()
                if isinstance(payload, list):
                    for item in payload:
                        osm_id = f"{item.get('osm_type', '')}_{item.get('osm_id', '')}"
                        if _is_valid_osm_market(item):
                            raw_by_osm_id[osm_id] = item
        except Exception:
            continue

    candidates: List[Dict[str, Any]] = []
    for item in raw_by_osm_id.values():
        try:
            m_lat = float(item["lat"])
            m_lon = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue

        dist = haversine_km(lat, lon, m_lat, m_lon)
        if dist > radius_km:
            continue

        extratags = item.get("extratags") or {}
        brand = (extratags.get("brand") or "").strip()
        name = (item.get("name") or brand or item.get("display_name", "").split(",")[0]).strip()
        addr = _format_osm_address(item.get("address") or {})
        integration = detect_online_integration(name, brand)

        candidates.append({
            "name": name,
            "brand": brand or integration["chain"],
            "shop_type": (item.get("type") or "supermarket").lower(),
            "distance_km": dist,
            "street": addr["street"],
            "neighborhood": addr["neighborhood"],
            "city": addr["city"] or resolved_city,
            "lat": m_lat,
            "lon": m_lon,
            "has_online_scraper": integration["has_online_scraper"],
            "online_status": integration["status_label"],
            "status_type": integration["status_type"],
            "chain": integration["chain"],
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={m_lat},{m_lon}"
        })

    # Ordena do mais próximo para o mais distante e deduplica nó + polígono do mesmo mercado
    candidates.sort(key=lambda m: (m["distance_km"], m["name"].lower()))
    deduped: List[Dict[str, Any]] = []
    for cand in candidates:
        cand_norm = _normalize_text(cand["name"])
        is_duplicate = False
        for existing in deduped:
            if _normalize_text(existing["name"]) == cand_norm and haversine_km(cand["lat"], cand["lon"], existing["lat"], existing["lon"]) <= 0.18:
                # Prefere o registro que tiver endereço mais completo
                if len(cand["street"]) > len(existing["street"]):
                    existing.update(cand)
                is_duplicate = True
                break
        if not is_duplicate:
            deduped.append(cand)

    cities_covered = sorted({m["city"] for m in deduped if m.get("city")})
    online_count = sum(1 for m in deduped if m["has_online_scraper"])
    result_payload = {
        "center": {
            "cep": f"{cleaned[:5]}-{cleaned[5:]}" if len(cleaned) == 8 else cep,
            "city": resolved_city,
            "uf": resolved_uf,
            "neighborhood": resolved_neighborhood,
            "lat": float(lat),
            "lon": float(lon)
        },
        "radius_km": radius_km,
        "markets": deduped,
        "summary": {
            "total": len(deduped),
            "online_integrated": online_count,
            "physical_only": len(deduped) - online_count,
            "cities_covered": cities_covered
        }
    }

    with _CACHE_LOCK:
        _NEARBY_CACHE[cache_key] = (now, {
            **result_payload,
            "markets": [dict(m) for m in deduped]
        })

    result_payload["markets"] = [dict(m) for m in deduped[:limit]]
    return result_payload


def get_available_supermarkets_for_location(uf: str, city: str = "") -> List[Dict[str, Any]]:
    """
    Retorna as redes de supermercado mapeadas por estado/cidade (compatibilidade legada).
    """
    available = []
    norm_uf = (uf or "").strip().upper()
    norm_city = (city or "").strip().lower()

    for name, info in SUPERMARKET_REGIONS.items():
        is_match = False
        is_local_city = False

        if norm_uf in info.get("states", []):
            is_match = True
            cities = [c.lower() for c in info.get("cities", [])]
            if norm_city and any(norm_city in c or c in norm_city for c in cities):
                is_local_city = True

        if is_match:
            available.append({
                "name": name,
                "coverage": info["coverage"],
                "description": info["description"],
                "is_direct_city_match": is_local_city,
                "supports_geo_catalog": info.get("supports_geo_catalog", False),
                "states": info["states"]
            })

    return available
