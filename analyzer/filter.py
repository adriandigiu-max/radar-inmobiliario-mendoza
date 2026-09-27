"""
Módulo de Filtrado Algorítmico y Pre-Scoring.
Ejecuta la Categoría A (Excluyentes estrictos) y el cálculo matemático de la Categoría B.
Cero consumo de tokens.
"""

from typing import Dict, Any, Tuple, Optional


def check_category_a(prop: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Evalúa la Categoría A (Criterios Excluyentes).
    Retorna (pasa_filtro: bool, motivo_descarte: Optional[str]).
    """
    search_cfg = config.get("search", {})
    budget_cfg = search_cfg.get("budget", {})
    surface_cfg = search_cfg.get("surface", {})
    
    # 1. Tipo de propiedad (Departamento o Casa)
    prop_type = (prop.get("property_type") or "").lower()
    allowed_types = [t.lower() for t in search_cfg.get("property_types", ["departamento", "casa"])]
    if not any(t in prop_type for t in allowed_types):
        return False, f"Tipo de propiedad no deseado: {prop_type}"

    # 2. Precio máximo absoluto (presupuesto + margen de contraoferta)
    price = prop.get("price_usd")
    max_price = budget_cfg.get("max_search_price_usd", 132000)
    if not price or price <= 0:
        return False, "Sin precio definido en USD"
    if price > max_price:
        return False, f"Precio USD {price:,.0f} supera el tope máximo evaluable de USD {max_price:,.0f}"

    # 3. Superficie mínima con tolerancia estricta
    surface = prop.get("surface_m2")
    min_surface = surface_cfg.get("min_m2_acceptable", 40)
    if surface is not None and surface > 0 and surface < min_surface:
        return False, f"Superficie {surface} m2 es menor al mínimo de tolerancia ({min_surface} m2)"

    # 4. Zona / Ubicación
    prop_zone = (prop.get("location_zone") or "").lower()
    primary_zones = [z.lower() for z in search_cfg.get("locations", {}).get("primary", [])]
    secondary_zones = [z.lower() for z in search_cfg.get("locations", {}).get("secondary", [])]
    all_allowed = primary_zones + secondary_zones

    if all_allowed and not any(allowed in prop_zone for allowed in all_allowed):
        return False, f"Zona '{prop_zone}' fuera de las áreas autorizadas"

    return True, None


def calculate_category_b_score(prop: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcula los puntajes de la Categoría B (Valores deseados con tolerancia):
    - Superficie (objetivo 50 m2, tolerancia 40-50)
    - Precio y Margen de negociación ($120.000 + 10%)
    """
    search_cfg = config.get("search", {})
    budget_cfg = search_cfg.get("budget", {})
    surface_cfg = search_cfg.get("surface", {})

    target_budget = budget_cfg.get("total_available_usd", 120000)
    max_price = budget_cfg.get("max_search_price_usd", 132000)
    price = prop.get("price_usd", 0)

    # 1. Scoring de Precio (0 a 100)
    # Si precio <= $120.000: 100 pts (incluso mayor puntaje si es mucho menor)
    # Si $120.000 < precio <= $132.000: penalización lineal hacia 50 pts
    if price <= target_budget:
        # Entre menor sea el precio respecto al presupuesto, excelente
        discount_ratio = (target_budget - price) / target_budget  # ej: 100k vs 120k -> 0.16
        price_score = min(100.0, 90.0 + (discount_ratio * 30.0))
        price_status = "DENTRO_PRESUPUESTO"
    else:
        # Está en el margen de negociación (120k a 132k)
        excess = price - target_budget
        max_excess = max_price - target_budget
        # Pasa de 85 a 55 según qué tan cerca de 132k esté
        price_score = max(50.0, 85.0 - (excess / max_excess) * 35.0)
        price_status = "REQUIERE_CONTRAOFERTA"

    # 2. Scoring de Superficie (0 a 100)
    target_m2 = surface_cfg.get("target_m2", 50)
    min_m2 = surface_cfg.get("min_m2_acceptable", 40)
    surface = prop.get("surface_m2")

    if surface is None or surface <= 0:
        surface_score = 70.0  # Sin dato explícito, neutral
        surface_notes = "Superficie no informada expresamente"
    elif surface >= target_m2:
        # Cumple o supera los 50 m2
        bonus = min(20.0, (surface - target_m2) * 0.5)
        surface_score = min(100.0, 90.0 + bonus)
        surface_notes = f"{surface:.0f} m2 (Cumple objetivo de {target_m2} m2)"
    else:
        # Entre 40 y 50 m2 (Tolerancia)
        ratio = (surface - min_m2) / (target_m2 - min_m2)
        surface_score = max(40.0, 50.0 + ratio * 35.0)
        surface_notes = f"{surface:.0f} m2 (Dentro de tolerancia pero menor a {target_m2} m2)"

    # Precio por m2
    price_per_m2 = (price / surface) if surface and surface > 0 else None

    return {
        "price_score": round(price_score, 1),
        "price_status": price_status,
        "surface_score": round(surface_score, 1),
        "surface_notes": surface_notes,
        "price_per_m2": round(price_per_m2, 1) if price_per_m2 else None,
    }
