"""
Módulo de Filtrado Algorítmico y Pre-Scoring.
Ejecuta la Categoría A (Excluyentes estrictos) y el cálculo de la Categoría B.
Cero consumo de tokens.
"""

import re
from typing import Dict, Any, Tuple, Optional


def check_category_a(prop: Dict[str, Any], config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Evalúa la Categoría A (Criterios Excluyentes):
    - Zonas: Mendoza Capital, Godoy Cruz, o Guaymallén ÚNICAMENTE si es Dorrego.
    - Baños: Mínimo 2 baños (excluyente).
    - Tipo: Casa o Departamento.
    - Precio máximo: USD 152.000 (USD 140.000 + 8.5% de contraoferta).
    """
    search_cfg = config.get("search", {})
    budget_cfg = search_cfg.get("budget", {})
    surface_cfg = search_cfg.get("surface", {})
    
    # 1. Tipo de propiedad
    prop_type = (prop.get("property_type") or "").lower()
    allowed_types = [t.lower() for t in search_cfg.get("property_types", ["departamento", "casa"])]
    if not any(t in prop_type for t in allowed_types):
        return False, f"Tipo de propiedad no deseado: {prop_type}"

    # 2. Precio máximo absoluto (presupuesto + margen de contraoferta: $152.000)
    price = prop.get("price_usd")
    max_price = budget_cfg.get("max_search_price_usd", 152000)
    if not price or price <= 0:
        return False, "Sin precio definido en USD"
    if price > max_price:
        return False, f"Precio USD {price:,.0f} supera el tope máximo evaluable de USD {max_price:,.0f}"

    # 3. Zonas permitidas (Mendoza Capital, Godoy Cruz, o Guaymallén solo Dorrego)
    prop_zone = (prop.get("location_zone") or "").lower()
    full_text = f"{prop.get('title', '')} {prop.get('description', '')} {prop.get('url', '')}".lower()

    if "mendoza" in prop_zone or "capital" in prop_zone:
        # Permitido
        pass
    elif "godoy cruz" in prop_zone:
        # Permitido
        pass
    elif "guaymallen" in prop_zone or "guaymallén" in prop_zone:
        # Solo permitido si menciona explícitamente "Dorrego"
        if "dorrego" not in full_text:
            return False, "Guaymallén descartado por no pertenecer al barrio Dorrego"
    else:
        # Fuera de zona (ej. Las Heras, Maipú, etc.)
        return False, f"Zona '{prop_zone}' no permitida"

    # 4. Mínimo 2 baños (EXCLUYENTE)
    baths = prop.get("bathrooms")
    has_two_baths_in_text = any(k in full_text for k in [
        "2 baños", "dos baños", "2 banos", "dos banos", "3 baños", "tres baños",
        "baño y toilette", "bano y toilette", "toilette", "en suite", "dos plantas con baño"
    ])
    has_single_bath_in_text = any(k in full_text for k in ["1 baño", "un baño", "1 bano", "un bano", "baño completo"])

    if baths is not None and baths >= 2:
        pass  # Cumple por ficha técnica
    elif has_two_baths_in_text:
        pass  # Cumple por texto
    elif baths == 1 or (baths is not None and baths < 2):
        return False, "Descartado: Solo cuenta con 1 baño (mínimo excluyente: 2 baños)"
    elif not has_two_baths_in_text and has_single_bath_in_text:
        return False, "Descartado: Publicación indica 1 solo baño"

    # 5. Mínimo 2 habitaciones (dormitorios) y mínimo 3 ambientes (EXCLUYENTE)
    bedrooms = prop.get("bedrooms")
    rooms = prop.get("rooms")

    has_two_plus_bedrooms = any(k in full_text for k in [
        "2 dormitorios", "dos dormitorios", "3 dormitorios", "tres dormitorios", "4 dormitorios", "cuatro dormitorios",
        "2 habitaciones", "dos habitaciones", "3 habitaciones", "tres habitaciones", "4 habitaciones",
        "2 dorm", "3 dorm", "4 dorm", "2 hab", "3 hab", "4 hab"
    ])
    has_single_bedroom = any(k in full_text for k in [
        "1 dormitorio", "un dormitorio", "1 habitacion", "1 habitación", "una habitacion", "una habitación",
        "1 dorm", "monoambiente", "mono ambiente", "mono-ambiente"
    ])

    has_three_plus_rooms = any(k in full_text for k in [
        "3 ambientes", "tres ambientes", "4 ambientes", "cuatro ambientes", "5 ambientes", "cinco ambientes",
        "3 amb", "4 amb", "5 amb"
    ])
    has_one_or_two_rooms = any(k in full_text for k in [
        "1 ambiente", "un ambiente", "2 ambientes", "dos ambientes", "1 amb", "2 amb"
    ])

    # Validación de habitaciones / dormitorios (mínimo 2)
    if bedrooms is not None:
        if bedrooms < 2:
            return False, f"Descartado: Cuenta con {bedrooms} dormitorio(s) (mínimo excluyente: 2 habitaciones)"
    elif has_single_bedroom and not has_two_plus_bedrooms:
        return False, "Descartado: Publicación indica 1 solo dormitorio o monoambiente (mínimo: 2 habitaciones)"

    # Validación de ambientes (mínimo 3 ambientes)
    if rooms is not None:
        if rooms < 3:
            return False, f"Descartado: Cuenta con {rooms} ambiente(s) (mínimo excluyente: 3 ambientes)"
    elif has_one_or_two_rooms and not (has_three_plus_rooms or has_two_plus_bedrooms):
        return False, "Descartado: Publicación indica 1 o 2 ambientes (mínimo excluyente: 3 ambientes)"

    # 6. Superficie mínima con tolerancia
    surface = prop.get("surface_m2")
    min_surface = surface_cfg.get("min_m2_acceptable", 65)
    if surface is not None and surface > 0 and surface < min_surface:
        return False, f"Superficie {surface} m2 es menor al piso de tolerancia ({min_surface} m2)"

    return True, None


def calculate_category_b_score(prop: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcula los puntajes de la Categoría B:
    - Superficie: Target 80 m2, tolerancia desde 65 m2.
    - Precio y Margen de negociación: Base $140.000, margen hasta $152.000.
    """
    search_cfg = config.get("search", {})
    budget_cfg = search_cfg.get("budget", {})
    surface_cfg = search_cfg.get("surface", {})

    target_budget = budget_cfg.get("total_available_usd", 140000)
    max_price = budget_cfg.get("max_search_price_usd", 152000)
    price = prop.get("price_usd", 0)

    # 1. Scoring de Precio (0 a 100)
    if price <= target_budget:
        discount_ratio = (target_budget - price) / target_budget
        price_score = min(100.0, 90.0 + (discount_ratio * 25.0))
        price_status = "DENTRO_PRESUPUESTO"
    else:
        # Entre 140k y 152k (Margen de contraoferta del 8.5%)
        excess = price - target_budget
        max_excess = max_price - target_budget
        price_score = max(55.0, 85.0 - (excess / max_excess) * 30.0)
        price_status = "REQUIERE_CONTRAOFERTA"

    # 2. Scoring de Superficie (0 a 100 con target 80 m2)
    target_m2 = surface_cfg.get("target_m2", 80)
    min_m2 = surface_cfg.get("min_m2_acceptable", 65)
    surface = prop.get("surface_m2")

    if surface is None or surface <= 0:
        surface_score = 70.0
        surface_notes = "Superficie no informada expresamente"
    elif surface >= target_m2:
        bonus = min(15.0, (surface - target_m2) * 0.3)
        surface_score = min(100.0, 90.0 + bonus)
        surface_notes = f"{surface:.0f} m2 (Cumple objetivo de {target_m2} m2)"
    else:
        # Entre 65 y 80 m2
        ratio = (surface - min_m2) / (target_m2 - min_m2)
        surface_score = max(50.0, 55.0 + ratio * 35.0)
        surface_notes = f"{surface:.0f} m2 (En tolerancia, cercano al target de {target_m2} m2)"

    price_per_m2 = (price / surface) if surface and surface > 0 else None

    return {
        "price_score": round(price_score, 1),
        "price_status": price_status,
        "surface_score": round(surface_score, 1),
        "surface_notes": surface_notes,
        "price_per_m2": round(price_per_m2, 1) if price_per_m2 else None,
    }
