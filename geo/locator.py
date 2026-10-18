import re
import requests
from typing import Dict, Any, List, Optional

# Base de conhecimento de presença regional das redes de mercados
SUPERMARKET_REGIONS = {
    "Atacadão": {
        "coverage": "Nacional (Lojas físicas em Porto Alegre, Canoas, Sapucaia, Novo Hamburgo, Gravataí...)",
        "description": "Atacadista alimentar com unidades em todos os estados do Brasil",
        "states": ["RS", "SC", "PR", "SP", "RJ", "MG", "BA", "PE", "CE", "GO", "DF", "ES", "MT", "MS", "PA", "AM"],
        "cities": [
            "Porto Alegre", "Canoas", "Sapucaia do Sul", "Esteio", "São Leopoldo", "Novo Hamburgo",
            "Gravataí", "Viamão", "Alvorada", "Caxias do Sul", "Pelotas", "Santa Maria", "Passo Fundo", "Rio Grande"
        ],
        "supports_geo_catalog": True,
        "default_zip": "01001000"
    },
    "Macromix Atacado": {
        "coverage": "Rio Grande do Sul (Região Metropolitana, Vale dos Sinos e Litoral)",
        "description": "Rede atacadista do Grupo Unidasul",
        "states": ["RS"],
        "cities": [
            "Esteio", "Porto Alegre", "São Leopoldo", "Novo Hamburgo", "Canoas", "Sapucaia do Sul",
            "Campo Bom", "Torres", "Tramandaí", "Xangri-lá", "Taquara", "Alvorada", "Gravataí"
        ],
        "supports_geo_catalog": True,
        "default_zip": "93020000"
    },
    "Super Rissul": {
        "coverage": "Rio Grande do Sul (Grande POA, Vale dos Sinos, Serra e Litoral)",
        "description": "Supermercado varejista do Grupo Unidasul",
        "states": ["RS"],
        "cities": [
            "Esteio", "Porto Alegre", "Canoas", "São Leopoldo", "Novo Hamburgo", 
            "Sapucaia do Sul", "Gramado", "Canela", "Parobé", "Igrejinha", "Taquara"
        ],
        "supports_geo_catalog": True,
        "default_zip": "93010000"
    },
    "Stock Center": {
        "coverage": "Rio Grande do Sul e Santa Catarina (Canoas, Gravataí, POA, Passo Fundo...)",
        "description": "Bandeira de atacarejo da Comercial Zaffari",
        "states": ["RS", "SC"],
        "cities": [
            "Esteio", "Canoas", "Porto Alegre", "Gravataí", "Passo Fundo", "Caxias do Sul",
            "Pelotas", "Santa Maria", "Rio Grande", "Cruz Alta", "Chapecó", "Lages"
        ],
        "supports_geo_catalog": True,
        "default_zip": "99010000"
    }
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"
}

def clean_cep(cep: str) -> str:
    """Remove caracteres especiais do CEP."""
    if not cep:
        return ""
    return re.sub(r"\D", "", str(cep))

def get_location_from_cep(cep: str) -> Optional[Dict[str, Any]]:
    """
    Consulta serviços de CEP (BrasilAPI -> ViaCEP -> OpenCEP) com redundância.
    Retorna dicionário com cep, logradouro, bairro, localidade, uf ou None se falhar.
    """
    cleaned = clean_cep(cep)
    if len(cleaned) != 8:
        return None

    # 1. Provedor 1: BrasilAPI (rápido, sem bloqueio de AWS/Cloudflare)
    try:
        url_brasilapi = f"https://brasilapi.com.br/api/cep/v2/{cleaned}"
        resp = requests.get(url_brasilapi, headers=DEFAULT_HEADERS, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            city = data.get("city")
            uf = (data.get("state") or "").upper()
            if city and uf:
                return {
                    "cep": f"{cleaned[:5]}-{cleaned[5:]}",
                    "logradouro": data.get("street") or "",
                    "bairro": data.get("neighborhood") or "",
                    "localidade": city,
                    "uf": uf,
                    "ddd": ""
                }
    except Exception:
        pass

    # 2. Provedor 2: ViaCEP com headers completos de navegador
    try:
        url_viacep = f"https://viacep.com.br/ws/{cleaned}/json/"
        resp = requests.get(url_viacep, headers=DEFAULT_HEADERS, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            if "erro" not in data and data.get("localidade"):
                return {
                    "cep": data.get("cep") or f"{cleaned[:5]}-{cleaned[5:]}",
                    "logradouro": data.get("logradouro") or "",
                    "bairro": data.get("bairro") or "",
                    "localidade": data.get("localidade"),
                    "uf": (data.get("uf") or "").upper(),
                    "ddd": data.get("ddd") or ""
                }
    except Exception:
        pass

    # 3. Provedor 3: OpenCEP
    try:
        url_opencep = f"https://opencep.com/v1/{cleaned}"
        resp = requests.get(url_opencep, headers=DEFAULT_HEADERS, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("localidade"):
                return {
                    "cep": data.get("cep") or f"{cleaned[:5]}-{cleaned[5:]}",
                    "logradouro": data.get("logradouro") or "",
                    "bairro": data.get("bairro") or "",
                    "localidade": data.get("localidade"),
                    "uf": (data.get("uf") or "").upper(),
                    "ddd": ""
                }
    except Exception:
        pass

    return None

def get_available_supermarkets_for_location(uf: str, city: str = "") -> List[Dict[str, Any]]:
    """
    Retorna as redes de supermercado disponíveis e prioritárias para a localização do usuário.
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
                "states": info["states"]
            })

    return available
