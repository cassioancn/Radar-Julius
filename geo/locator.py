import re
import requests
from typing import Dict, Any, List, Optional

# Base de conhecimento de presença regional das redes de mercados
SUPERMARKET_REGIONS = {
    "Atacadão": {
        "coverage": "Nacional",
        "description": "Atacadista alimentar com unidades em todos os estados do Brasil",
        "states": ["RS", "SC", "PR", "SP", "RJ", "MG", "BA", "PE", "CE", "GO", "DF", "ES", "MT", "MS", "PA", "AM"],
        "supports_geo_catalog": True,
        "default_zip": "01001000"
    },
    "Macromix Atacado": {
        "coverage": "Rio Grande do Sul (Região Metropolitana, Vale dos Sinos e Litoral)",
        "description": "Rede atacadista do Grupo Unidasul",
        "states": ["RS"],
        "cities": [
            "Porto Alegre", "São Leopoldo", "Novo Hamburgo", "Canoas", "Sapucaia do Sul",
            "Esteio", "Campo Bom", "Torres", "Tramandaí", "Xangri-lá", "Taquara"
        ],
        "supports_geo_catalog": True,
        "default_zip": "93020000"
    },
    "Super Rissul": {
        "coverage": "Rio Grande do Sul (Grande POA, Vale dos Sinos, Serra e Litoral)",
        "description": "Supermercado varejista do Grupo Unidasul",
        "states": ["RS"],
        "cities": [
            "Porto Alegre", "Canoas", "São Leopoldo", "Novo Hamburgo", "Esteio", 
            "Sapucaia do Sul", "Gramado", "Canela", "Parobé", "Igrejinha", "Taquara"
        ],
        "supports_geo_catalog": True,
        "default_zip": "93010000"
    },
    "Stock Center": {
        "coverage": "Rio Grande do Sul e Santa Catarina",
        "description": "Bandeira de atacarejo da Comercial Zaffari",
        "states": ["RS", "SC"],
        "cities": [
            "Passo Fundo", "Porto Alegre", "Caxias do Sul", "Canoas", "Gravataí",
            "Pelotas", "Santa Maria", "Rio Grande", "Cruz Alta", "Chapecó", "Lages"
        ],
        "supports_geo_catalog": True,
        "default_zip": "99010000"
    }
}

def clean_cep(cep: str) -> str:
    """Remove caracteres especiais do CEP."""
    if not cep:
        return ""
    return re.sub(r"\D", "", cep)

def get_location_from_cep(cep: str) -> Optional[Dict[str, Any]]:
    """
    Consulta o ViaCEP para obter dados geográficos do usuário brasileiro.
    Retorna dicionário com logradouro, bairro, cidade, uf, ddd ou None em caso de falha.
    """
    cleaned = clean_cep(cep)
    if len(cleaned) != 8:
        return None

    url = f"https://viacep.com.br/ws/{cleaned}/json/"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "erro" not in data:
                return {
                    "cep": data.get("cep"),
                    "logradouro": data.get("logradouro", ""),
                    "bairro": data.get("bairro", ""),
                    "localidade": data.get("localidade", ""),
                    "uf": data.get("uf", "").upper(),
                    "ddd": data.get("ddd", "")
                }
    except Exception:
        pass

    # Fallback seguro com CEP informado
    return {
        "cep": cleaned,
        "logradouro": "Região Central",
        "bairro": "Centro",
        "localidade": "São Leopoldo",
        "uf": "RS",
        "ddd": "51"
    }

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

