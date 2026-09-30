"""
Evaluador de Oportunidades con IA (Gemini Flash) y modo Heurístico de respaldo (0 tokens).
Categoría C: Gas Natural, Cochera, Ascensor, y Seguridad 24hs (con alta penalidad por no tenerla).
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def evaluate_heuristics(prop: Dict[str, Any], cat_b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluación algorítmica sin tokens con los nuevos criterios y penalidades.
    """
    text = f"{prop.get('title', '')} {prop.get('description', '')}".lower()
    prop_type = prop.get("property_type", "").lower()
    price = prop.get("price_usd", 0)

    # 1. Seguridad 24 hs / Barrio Privado (Categoría C - Ponderación alta y penalización severa)
    sec_keywords = [
        "seguridad 24", "vigilancia 24", "guardia 24", "seguridad privada",
        "barrio privado", "barrio cerrado", "garita", "porteria 24", "portería 24",
        "control de acceso", "vigilancia permanente"
    ]
    has_security = any(k in text for k in sec_keywords)
    # Si tiene seguridad suma 30 pts, si no tiene recibe penalidad severa
    sec_score = 30 if has_security else 0

    # 2. Red de gas natural (Categoría C)
    gas_keywords = ["gas natural", "red de gas", "calefaccion central", "radiadores", "tiro balanceado"]
    no_gas_keywords = ["gas envasado", "garrafa", "solo electrico", "sin gas"]
    has_gas = any(k in text for k in gas_keywords) and not any(k in text for k in no_gas_keywords)
    gas_score = 20 if has_gas else 5

    # 3. Cochera (Categoría C)
    parking_keywords = ["cochera", "garage", "garaje", "estacionamiento", "vehiculo", "auto"]
    has_parking = bool(prop.get("has_parking_attribute")) or any(k in text for k in parking_keywords)
    parking_score = 20 if has_parking else 0

    # 4. Ascensor (Categoría C - Especialmente relevante para departamentos)
    elevator_keywords = ["ascensor", "elevador", "doble ascensor"]
    has_elevator = any(k in text for k in elevator_keywords)
    if prop_type == "departamento":
        elevator_score = 15 if has_elevator else (10 if "planta baja" in text or " pb" in text else 0)
    else:
        elevator_score = 10  # En casas no aplica

    # 5. Detección de Margen de Negociación
    nego_keywords = ["escucha oferta", "escuchan ofertas", "retasado", "rebajado", "urgencia", "permuta", "toma menor", "acepta vehiculo"]
    has_negotiation_signals = any(k in text for k in nego_keywords)
    nego_potential = "Alta" if has_negotiation_signals else ("Moderada" if price > 140000 else "Estándar")

    # Score base ponderado
    # 30% Precio + 25% Superficie (target 80m2) + 45% Características C
    cat_c_sum = sec_score + gas_score + parking_score + elevator_score  # Max 85 pts
    cat_c_score = min(100.0, (cat_c_sum / 85.0) * 100.0)

    price_score = cat_b.get("price_score", 70.0)
    if price > 140000 and has_negotiation_signals:
        price_score = min(100.0, price_score + 15.0)

    base_score = (
        (price_score * 0.30) +
        (cat_b.get("surface_score", 70.0) * 0.25) +
        (cat_c_score * 0.45)
    )

    # APLICAR ALTA PENALIDAD POR NO TENER SEGURIDAD 24HS / BARRIO PRIVADO (-20 puntos)
    if not has_security:
        base_score = max(30.0, base_score - 20.0)

    pros = []
    cons = []

    # EVALUACIÓN DE BARRIO EN GODOY CRUZ:
    # "Godoy cruz sigue siendo aceptado, pero penaliza a los barrios que no sea el Bombal"
    geo = prop.get("geo_verification", {})
    prop_zone = (prop.get("location_zone") or "").lower()
    real_city = (geo.get("real_city") or "").lower()
    real_neighborhood = (geo.get("real_neighborhood") or "").lower()
    loc_full = f"{prop_zone} {real_city} {real_neighborhood} {text}".lower()

    is_godoy_cruz = "godoy cruz" in prop_zone or "godoy cruz" in real_city
    is_bombal = "bombal" in loc_full or "bombal sur" in loc_full

    if is_godoy_cruz:
        if is_bombal:
            pros.append("📍 Excelente ubicación: Barrio Bombal / Bombal Sur (Godoy Cruz)")
        else:
            base_score = max(20.0, base_score - 15.0)
            cons.append("⚠️ Ubicado en Godoy Cruz fuera de Barrio Bombal (-15 pts)")

    # BONIFICACIÓN POR ESPACIO EXTRA (3+ DORMITORIOS O 4+ AMBIENTES)
    bedrooms = prop.get("bedrooms")
    rooms = prop.get("rooms")
    has_extra_rooms = (
        (bedrooms is not None and bedrooms >= 3) or
        (rooms is not None and rooms >= 4) or
        any(k in text for k in [
            "3 dormitorios", "tres dormitorios", "4 dormitorios", "cuatro dormitorios", "5 dormitorios",
            "3 habitaciones", "tres habitaciones", "4 habitaciones", "cuatro habitaciones",
            "4 ambientes", "cuatro ambientes", "5 ambientes", "cinco ambientes", "3 dorm", "4 dorm"
        ])
    )
    if has_extra_rooms:
        base_score = min(100.0, base_score + 10.0)
        pros.append("✨ Amplio: cuenta con 3+ dormitorios o 4+ ambientes (+10 pts)")

    final_score = min(100.0, round(base_score, 1))

    if price <= 140000:
        pros.append(f"Dentro del presupuesto (USD {price:,.0f})")
    else:
        cons.append(f"Publicado en USD {price:,.0f} (Requiere contraoferta del {(price-140000)/1400:.1f}%)")

    if has_security:
        pros.append("🛡️ Cuenta con seguridad 24 hs / barrio privado")
    else:
        cons.append("⚠️ Sin seguridad 24 hs ni barrio privado (penalizado en puntaje)")

    if has_gas:
        pros.append("🔥 Red de gas natural confirmada")
    else:
        cons.append("Consultar conexión a red de gas natural")

    if has_parking:
        pros.append("🚗 Cuenta con cochera")
    if has_elevator and prop_type == "departamento":
        pros.append("🛗 Edificio con ascensor")
    if has_negotiation_signals:
        pros.append("💡 Publicación indica apertura a ofertas o permutas")

    return {
        "opportunity_score": final_score,
        "evaluation_source": "heurística",
        "category_c": {
            "has_security": has_security,
            "has_gas_network": has_gas,
            "has_parking": has_parking,
            "has_elevator": has_elevator,
            "two_bathrooms": True,  # Ya filtrado como excluyente en Cat A
        },
        "negotiation_analysis": {
            "potential": nego_potential,
            "signals_detected": has_negotiation_signals,
            "summary": "Señales de negociación/permuta detectadas en la publicación." if has_negotiation_signals else "Precio estándar de mercado.",
        },
        "pros": pros[:4],
        "cons": cons[:3],
        "ai_summary": (
            f"Propiedad en {prop.get('location_zone')} ({prop.get('property_type')}) de {prop.get('surface_m2', 'N/A')} m2 a USD {price:,.0f}. "
            f"Score: {final_score}/100 {'(Con seguridad 24hs)' if has_security else '(Penalizado por falta de seguridad 24hs)'}."
        ),
    }


def evaluate_with_gemini(prop: Dict[str, Any], cat_b: Dict[str, Any], api_key: str) -> Optional[Dict[str, Any]]:
    """Evaluación profunda con Gemini Flash (usando los nuevos criterios)."""
    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = f"""
Eres un analista inmobiliario en Mendoza, Argentina.
Analiza la siguiente publicación inmobiliaria según estos criterios:

[PROPIEDAD]
- Tipo: {prop.get('property_type')}
- Zona: {prop.get('location_zone')}
- Precio: USD {prop.get('price_usd')}
- Superficie: {prop.get('surface_m2')} m2
- Título: {prop.get('title')}
- Descripción:
\"\"\"{prop.get('description', '')[:2000]}\"\"\"

[CRITERIOS DEL COMPRADOR]
- Presupuesto objetivo: USD 140.000 (Tope máximo con contraoferta de mercado: USD 152.000).
- Superficie deseada: 80 m2 cubiertos (tolerancia desde 65 m2).
- Mínimo 2 baños (excluyente).
- Deseables:
  1. Red de gas natural conectada.
  2. Cochera propia.
  3. Ascensor (en departamentos).
  4. Seguridad 24 hs (en casas: barrio cerrado; en deptos: seguridad 24hs o portería permanente).
     *ATENCIÓN: Si NO tiene seguridad 24 hs o barrio privado, aplicar una fuerte penalización en opportunity_score (-20 a -25 puntos).*

Responde EXCLUSIVAMENTE con un JSON válido:
{{
  "opportunity_score": <número entre 0 y 100>,
  "has_security": <true|false>,
  "has_gas_network": <true|false>,
  "has_parking": <true|false>,
  "has_elevator": <true|false>,
  "negotiation_potential": <"Alta"|"Media"|"Baja">,
  "negotiation_reasoning": <"breve análisis del margen de negociación en Mendoza">,
  "pros": [<lista de 2 a 3 puntos a favor>],
  "cons": [<lista de 1 a 2 advertencias>],
  "ai_summary": <"resumen de 2 oraciones para el comprador">
}}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        )
        data = json.loads(response.text)
        return {
            "opportunity_score": float(data.get("opportunity_score", 70.0)),
            "evaluation_source": "gemini_ai",
            "category_c": {
                "has_security": data.get("has_security"),
                "has_gas_network": data.get("has_gas_network"),
                "has_parking": data.get("has_parking"),
                "has_elevator": data.get("has_elevator"),
                "two_bathrooms": True,
            },
            "negotiation_analysis": {
                "potential": data.get("negotiation_potential", "Media"),
                "summary": data.get("negotiation_reasoning", ""),
            },
            "pros": data.get("pros", []),
            "cons": data.get("cons", []),
            "ai_summary": data.get("ai_summary", ""),
        }
    except Exception as e:
        logger.warning(f"Fallback a heurística: {e}")
        return None


def evaluate_property(prop: Dict[str, Any], cat_b: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    if api_key:
        result = evaluate_with_gemini(prop, cat_b, api_key)
        if result:
            return result
    return evaluate_heuristics(prop, cat_b)
