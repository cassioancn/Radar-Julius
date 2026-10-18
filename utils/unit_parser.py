import re
from typing import Dict, Any, Optional

def parse_volume_or_weight(title: str, fallback_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Analisa o título de um produto de mercado (ou fallback como slug da URL)
    e extrai peso, volume ou quantidade de unidades, normalizando para unidades padrão (kg, L ou un).
    Detecta também embalagens múltiplas (ex: 12x350ml, 6 x 1L, pack 12 un).
    """
    if not title:
        return {"has_unit": False}

    def _extract_from_text(raw_text: str) -> Optional[Dict[str, Any]]:
        text = raw_text.lower()
        # Normaliza pontuação para facilitar regex
        text_spaced = re.sub(r"[-_/]", " ", text)

        # 1. Padrão Multipack com volume/peso (ex: 12x350ml, 6x1l, 3 x 500g, fardo 12x 350 ml)
        pack_match = re.search(r"(\d+)\s*(?:x|de|\*)\s*(\d+(?:[.,]\d+)?)\s*(kg|kilo|quilo|g|gr|gramas|l|litro|litros|ml|mls)\b", text_spaced)
        if pack_match:
            multiplier = float(pack_match.group(1))
            val_str = pack_match.group(2).replace(",", ".")
            val = float(val_str)
            unit = pack_match.group(3)
            total_val = multiplier * val

            if unit in ["kg", "kilo", "quilo"]:
                return {
                    "has_unit": True,
                    "category": "weight",
                    "detected_str": f"{int(multiplier)}x {val_str}kg ({total_val:g}kg)",
                    "std_qty": total_val,
                    "std_unit": "kg",
                    "display_unit": "kg"
                }
            elif unit in ["g", "gr", "gramas"]:
                std_kg = total_val / 1000.0
                return {
                    "has_unit": True,
                    "category": "weight",
                    "detected_str": f"{int(multiplier)}x {val_str}g ({std_kg:g}kg)",
                    "std_qty": std_kg,
                    "std_unit": "kg",
                    "display_unit": "kg"
                }
            elif unit in ["l", "litro", "litros"]:
                return {
                    "has_unit": True,
                    "category": "volume",
                    "detected_str": f"{int(multiplier)}x {val_str}L ({total_val:g}L)",
                    "std_qty": total_val,
                    "std_unit": "L",
                    "display_unit": "L"
                }
            elif unit in ["ml", "mls"]:
                std_l = total_val / 1000.0
                return {
                    "has_unit": True,
                    "category": "volume",
                    "detected_str": f"{int(multiplier)}x {val_str}ml ({std_l:g}L)",
                    "std_qty": std_l,
                    "std_unit": "L",
                    "display_unit": "L"
                }

        # 2. Padrão Peso Unitário: Quilos (kg, quilo)
        # Ex: 5kg, 1.5kg, 1kg, "ao quilo", "quilo"
        kg_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:kg|kilo|quilos?)\b", text_spaced)
        if kg_match:
            val = float(kg_match.group(1).replace(",", "."))
            return {
                "has_unit": True,
                "category": "weight",
                "detected_str": f"{val:g} kg",
                "std_qty": val,
                "std_unit": "kg",
                "display_unit": "kg"
            }
        
        # Se diz expressamente "quilo" ou "kg" sem número (ex: "Queijo mussarela quilo", "preço por kg")
        if re.search(r"\b(?:quilo|ao quilo|por kg|/kg|kg)\b", text_spaced):
            return {
                "has_unit": True,
                "category": "weight",
                "detected_str": "1 kg (Granel/Quilo)",
                "std_qty": 1.0,
                "std_unit": "kg",
                "display_unit": "kg"
            }

        # 3. Padrão Peso Unitário: Gramas (g, gr, gramas)
        g_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:g|gr|gramas?)\b", text_spaced)
        if g_match:
            val = float(g_match.group(1).replace(",", "."))
            std_kg = val / 1000.0
            return {
                "has_unit": True,
                "category": "weight",
                "detected_str": f"{val:g} g",
                "std_qty": std_kg,
                "std_unit": "kg",
                "display_unit": "kg"
            }

        # 4. Padrão Volume: Litros (L, litros)
        l_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:l|litros?)\b", text_spaced)
        if l_match:
            val = float(l_match.group(1).replace(",", "."))
            return {
                "has_unit": True,
                "category": "volume",
                "detected_str": f"{val:g} L",
                "std_qty": val,
                "std_unit": "L",
                "display_unit": "L"
            }

        # 5. Padrão Volume: Mililitros (ml, mls)
        ml_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:ml|mls)\b", text_spaced)
        if ml_match:
            val = float(ml_match.group(1).replace(",", "."))
            std_l = val / 1000.0
            return {
                "has_unit": True,
                "category": "volume",
                "detected_str": f"{val:g} ml",
                "std_qty": std_l,
                "std_unit": "L",
                "display_unit": "L"
            }

        # 6. Padrão Unidades / Contagem (ex: 30 tiras, 16 capsulas, 12 rolos, 30 ovos, 4 un)
        un_match = re.search(r"(\d+)\s*(?:un|unid|unidades?|tiras?|capsulas?|cápsulas?|rolos?|sachês?|saches?|ovos)\b", text_spaced)
        if un_match:
            val = float(un_match.group(1))
            return {
                "has_unit": True,
                "category": "count",
                "detected_str": f"{int(val)} un",
                "std_qty": val,
                "std_unit": "un",
                "display_unit": "un"
            }

        return None

    res = _extract_from_text(title)
    if res:
        return res

    if fallback_text:
        fallback_res = _extract_from_text(fallback_text)
        if fallback_res:
            return fallback_res

    return {"has_unit": False}

def calculate_normalized_price(
    price: float,
    title: str,
    fallback_text: Optional[str] = None,
    target_unit: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calcula o preço por unidade (ex: R$ / kg, R$ / L ou R$ / un).
    Permite comparação justa de custo-benefício.
    
    Se target_unit for especificado ('kg', 'L', 'un'):
    Indica se o item é compatível com a unidade selecionada pelo usuário.
    """
    parsed = parse_volume_or_weight(title, fallback_text=fallback_text)
    if not parsed.get("has_unit") or not parsed.get("std_qty") or parsed["std_qty"] <= 0:
        return {
            "has_unit_price": False,
            "original_price": price,
            "unit_price": price,
            "unit_label": None,
            "category": "other",
            "detected_size": "Embalagem Padrão",
            "matches_target": True if not target_unit or target_unit == "auto" else False
        }

    std_qty = parsed["std_qty"]
    std_unit = parsed["std_unit"]
    category = parsed.get("category", "other")
    unit_price = round(price / std_qty, 2)

    matches_target = True
    if target_unit and target_unit != "auto":
        if target_unit == "kg" and category != "weight":
            matches_target = False
        elif target_unit == "L" and category != "volume":
            matches_target = False
        elif target_unit == "un" and category != "count":
            matches_target = False

    return {
        "has_unit_price": True,
        "original_price": price,
        "unit_price": unit_price,
        "unit_label": f"R$ {unit_price:.2f} / {std_unit}",
        "std_unit": std_unit,
        "category": category,
        "std_qty": std_qty,
        "detected_size": parsed["detected_str"],
        "matches_target": matches_target
    }
