import re
import urllib.parse
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
import requests

HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
]

@dataclass
class ProductItem:
    """Item de produto padronizado retornado pelos scrapers."""
    title: str
    price: float
    original_price: Optional[float] = None
    discount_pct: Optional[float] = None
    store: str = ""
    store_type: str = "retail"  # 'retail' ou 'supermarket'
    url: str = ""
    image_url: Optional[str] = None
    location: Optional[str] = None
    rating: Optional[float] = None
    in_stock: bool = True
    unit_price: Optional[float] = None
    unit_label: Optional[str] = None
    detected_size: Optional[str] = None
    has_unit_price: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def parse_price_brl(price_str: Any) -> Optional[float]:
    """Converte strings com preços em formato BRL (ex: 'R$ 1.299,90' ou '24,50') para float."""
    if price_str is None:
        return None
    if isinstance(price_str, (int, float)):
        return float(price_str)
    
    text = str(price_str).strip()
    # Remove R$, espaços e caracteres não numéricos exceto ponto e vírgula
    text = re.sub(r"[^\d,\.]", "", text)
    if not text:
        return None

    # Trata formatos '1.250,50' ou '1250.50' ou '25,90'
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        val = float(text)
        return round(val, 2)
    except ValueError:
        return None

class BaseScraper(ABC):
    """Classe base para todos os scrapers de varejo e supermercados."""

    def __init__(self, store_name: str, store_type: str = "retail"):
        self.store_name = store_name
        self.store_type = store_type
        self.headers = HEADERS_LIST[0]
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    @abstractmethod
    def search(self, query: str, limit: int = 10, **kwargs) -> List[ProductItem]:
        """Executa busca e retorna lista de ProductItem."""
        pass

