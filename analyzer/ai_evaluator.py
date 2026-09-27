"""
Evaluador de Oportunidades con IA (Gemini Flash) y modo Heurístico de respaldo (0 tokens).
Analiza las características de la Categoría C, evalúa el potencial de contraoferta
y asigna el Score Global de Oportunidad (0 a 100).
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def evaluate_heuristics(prop: Dict[str, Any], cat_b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluación algorítmica sin tokens (fallback instantáneo y gratuito).
    Analiza palabras clave en la descripción y ficha técnica.
    """
    text = f"{prop.get('title', '')} {prop.get('description', '')}".lower()
    prop_type = prop.get("property_type", "").lower()
    price = prop.get("price_usd", 0)

    # 1. Seguridad / Barrio Privado (Categoría C)
    sec_keywords = ["barrio privado", "barrio cerrado", "seguridad 24", "seguridad privada", "garita", "vigilancia", "guardia"]
    has_security = any(k in text for k in sec_keywords)
    sec_score = 20 if has_security else (10 if prop_type == "departamento" else 0)

    # 2. Red de gas natural (Categoría C)
    gas_keywords = ["gas natural", "red de gas", "calefaccion central", "radiadores", "tiro balanceado"]
    no_gas_keywords = ["gas envasado", "garrafa", "solo electrico", "sin gas"]
    has_gas = any(k in text for k in gas_keywords) and not any(k in text for k in no_gas_keywords)
    gas_score = 20 if has_gas else 5

    # 3. Cochera (Categoría C)
    parking_keywords = ["cochera", "garage", "garaje", "estacionamiento", "vehiculo", "auto"]
    has_parking = bool(prop.get("has_parking_attribute")) or any(k in text for k in parking_keywords)
    parking_score = 20 if has_parking else 0

    # 4. Dos o más baños (Categoría C)
    bath_keywords = ["2 baños", "dos baños", "2 banos", "dos banos", "baño y toilette", "bano y toilette", "en suite"]
    prop_baths = prop.get("bathrooms") or 0
    has_two_baths = prop_baths >= 2 or any(k in text for k in bath_keywords)
    bath_score = 15 if has_two_baths else 5

    # 5. Último piso en departamento (Categoría C)
    floor_keywords = ["ultimo piso", "último piso", "piso superior", "penthouse", "terraza propia", "duplex"]
    is_top_floor = any(k in text for k in floor_keywords) if prop_type == "departamento" else False
    top_floor_score = 15 if is_top_floor else (10 if prop_type == "casa" else 0)

    # 6. Detección de Margen de Negociación
    nego_keywords = ["escucha oferta", "escuchan ofertas", "retasado", "rebajado", "urgencia", "permuta", "toma menor", "acepta vehiculo"]
    has_negotiation_signals = any(k in text for k in nego_keywords)
    
    nego_potential = "Alta" if has_negotiation_signals else ("Moderada" if price > 120000 else "Estándar")

    # Score ponderado final (0 a 100)
    # 30% Precio + 25% Superficie + 45% Características C
    cat_c_score = (sec_score + gas_score + parking_score + bath_score + top_floor_score) * (100 / 90)
    cat_c_score = min(100.0, cat_c_score)

    price_score = cat_b.get("price_score", 70.0)
    if price > 120000 and has_negotiation_signals:
        price_score = min(100.0, price_score + 15.0)

    final_score = (
        (price_score * 0.35) +
        (cat_b.get("surface_score", 70.0) * 0.25) +
        (cat_c_score * 0.40)
    )

    pros = []
    cons = []
    if price <= 120000:
        pros.append(f"Dentro del presupuesto base (USD {price:,.0f})")
    else:
        cons.append(f"Publicado en USD {price:,.0f} (Requiere negociación del {(price-120000)/1200:.1f}%)")

    if has_security:
        pros.append("Cuenta con seguridad / barrio privado")
    elif prop_type == "casa":
        cons.append("No menciona expresamente barrio privado o seguridad")

    if has_gas:
        pros.append("Menciona red de gas natural")
    else:
        cons.append("Verificar conexión a red de gas natural")

    if has_parking:
        pros.append("Incluye cochera / garage")
    if has_two_baths:
        pros.append("Tiene 2 baños o suite")
    if is_top_floor:
        pros.append("Último piso (sin vecinos arriba)")
    if has_negotiation_signals:
        pros.append("Publicación indica apertura a ofertas o permutas")

    return {
        "opportunity_score": round(final_score, 1),
        "evaluation_source": "heurística",
        "category_c": {
            "has_security": has_security,
            "has_gas_network": has_gas,
            "has_parking": has_parking,
            "two_bathrooms": has_two_baths,
            "is_top_floor": is_top_floor,
        },
        "negotiation_analysis": {
            "potential": nego_potential,
            "signals_detected": has_negotiation_signals,
            "summary": "Presenta términos de flexibilización o permuta en la descripción." if has_negotiation_signals else "Precio habitual de mercado.",
        },
        "pros": pros[:4],
        "cons": cons[:3],
        "ai_summary": (
            f"Propiedad en {prop.get('location_zone')} de {prop.get('surface_m2', 'N/A')} m2 a USD {price:,.0f}. "
            f"Score de oportunidad: {round(final_score, 1)}/100."
        ),
    }


def evaluate_with_gemini(prop: Dict[str, Any], cat_b: Dict[str, Any], api_key: str) -> Optional[Dict[str, Any]]:
    """
    Evaluación cualitativa profunda utilizando Google Gemini 2.0 / 1.5 Flash.
    """
    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = f"""
Eres un asesor inmobiliario experto analizando una oportunidad en Mendoza, Argentina.
Analiza la siguiente publicación inmobiliaria y compárala con las preferencias del comprador:

[DATOS DE LA PROPIEDAD]
- Tipo: {prop.get('property_type')}
- Zona: {prop.get('location_zone')}
- Precio publicado: USD {prop.get('price_usd')}
- Superficie: {prop.get('surface_m2')} m2
- Título: {prop.get('title')}
- Descripción del aviso:
\"\"\"{prop.get('description', '')[:2000]}\"\"\"

[PREFERENCIAS DEL COMPRADOR]
- Presupuesto máximo total: USD 120.000 (Si el precio está entre 120k y 132k, evaluar si el aviso muestra señales de urgencia, retasado o 'escucha ofertas' para contraofertar).
- Superficie deseada: desde 50 m2 cubiertos (40-50m2 tolerable).
- Deseables clave:
  1. Seguridad (si es casa, barrio privado; si es depto, seguridad del edificio).
  2. Red de gas natural (fundamental por clima mendocino).
  3. Cochera propia.
  4. Dos baños.
  5. Último piso (si es departamento).

Responde EXCLUSIVAMENTE con un objeto JSON válido con la siguiente estructura exacta:
{{
  "opportunity_score": <número entre 0 y 100>,
  "has_security": <true|false|null>,
  "has_gas_network": <true|false|null>,
  "has_parking": <true|false|null>,
  "two_bathrooms": <true|false|null>,
  "is_top_floor": <true|false|null>,
  "negotiation_potential": <"Alta"|"Media"|"Baja">,
  "negotiation_reasoning": <"breve explicación de por qué es o no negociable">,
  "pros": [<lista de 2 a 3 puntos a favor concretos>],
  "cons": [<lista de 1 a 2 advertencias o dudas a confirmar>],
  "ai_summary": <"resumen ejecutivo de 2 oraciones para el comprador">
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
                "two_bathrooms": data.get("two_bathrooms"),
                "is_top_floor": data.get("is_top_floor"),
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
        logger.warning(f"Fallo en evaluación con Gemini ({e}), usando evaluación heurística")
        return None


def evaluate_property(prop: Dict[str, Any], cat_b: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Función principal de análisis: intenta con Gemini si hay API Key disponible,
    o utiliza la evaluación heurística con 0 tokens.
    """
    if api_key:
        result = evaluate_with_gemini(prop, cat_b, api_key)
        if result:
            return result

    return evaluate_heuristics(prop, cat_b)
