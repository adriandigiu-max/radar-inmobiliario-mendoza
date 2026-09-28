"""
Módulo de verificación geográfica con Nominatim (OpenStreetMap).
Valida que las coordenadas GPS de cada propiedad correspondan
realmente a las zonas permitidas (Mendoza Capital, Godoy Cruz, Barrio Dorrego en Guaymallén).
Gratuito, sin API Key, sin tokens.
"""

import time
import logging
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
HEADERS = {"User-Agent": "RadarInmobiliarioMendoza/1.0"}

# Municipios permitidos exactos según Nominatim para la provincia de Mendoza
ALLOWED_MUNICIPALITIES = [
    "ciudad de mendoza",
    "mendoza",
    "departamento mendoza",
    "departamento capital",
    "godoy cruz",
    "departamento godoy cruz",
    "guaymallén",
    "guaymallen",
    "departamento guaymallén",
    "departamento guaymallen",
]

# Para Guaymallén solo se acepta Dorrego
GUAYMALLEN_ALLOWED_NEIGHBORHOODS = [
    "dorrego",
    "barrio dorrego",
    "cuarto dorrego",
]


def reverse_geocode(lat: float, lng: float) -> Optional[Dict]:
    """Consulta Nominatim para obtener la ubicación real de unas coordenadas."""
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"lat": lat, "lon": lng, "format": "json", "addressdetails": 1},
            headers=HEADERS,
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"Error en geocodificación inversa ({lat},{lng}): {e}")
    return None


def verify_zone_by_coordinates(prop: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verifica la zona real de una propiedad usando sus coordenadas GPS.
    Retorna un dict con:
    - is_valid_zone: bool
    - real_city: str
    - real_neighborhood: str
    - rejection_reason: str (si no es válida)
    """
    coords = prop.get("coordinates")
    if not coords or not coords.get("lat") or not coords.get("lng"):
        # Sin coordenadas, no podemos verificar — le damos el beneficio de la duda
        return {
            "is_valid_zone": True,
            "real_city": "Sin coordenadas",
            "real_neighborhood": None,
            "rejection_reason": None,
            "geocode_verified": False
        }

    try:
        lat = float(coords["lat"])
        lng = float(coords["lng"])
    except (ValueError, TypeError):
        return {
            "is_valid_zone": True,
            "real_city": "Coord inválidas",
            "real_neighborhood": None,
            "rejection_reason": None,
            "geocode_verified": False
        }

    # Verificar que las coordenadas estén aproximadamente en Mendoza
    # Mendoza provincia: lat entre -35 y -31, lng entre -70 y -67
    if not (-35.5 <= lat <= -31.0 and -70.5 <= lng <= -66.5):
        return {
            "is_valid_zone": False,
            "real_city": f"Coords fuera de Mendoza ({lat:.3f},{lng:.3f})",
            "real_neighborhood": None,
            "rejection_reason": f"Coordenadas GPS ({lat:.4f}, {lng:.4f}) están fuera de la provincia de Mendoza",
            "geocode_verified": True
        }

    geo = reverse_geocode(lat, lng)
    time.sleep(1.1)  # Cortesía con Nominatim (máx 1 req/seg por ToS)

    if not geo:
        return {
            "is_valid_zone": True,
            "real_city": "No se pudo verificar",
            "real_neighborhood": None,
            "rejection_reason": None,
            "geocode_verified": False
        }

    addr = geo.get("address", {})
    city_raw = (
        addr.get("city") or
        addr.get("town") or
        addr.get("municipality") or
        addr.get("county") or ""
    ).lower().strip()

    suburb_raw = (
        addr.get("suburb") or
        addr.get("neighbourhood") or
        addr.get("quarter") or ""
    ).lower().strip()

    state = (addr.get("state") or "").lower()

    # Verificar que esté en la PROVINCIA de Mendoza
    if "mendoza" not in state:
        return {
            "is_valid_zone": False,
            "real_city": city_raw.title(),
            "real_neighborhood": suburb_raw.title() or None,
            "rejection_reason": f"La publicación está en '{state.title()}', no en Mendoza",
            "geocode_verified": True
        }

    # Verificar municipio permitido
    city_ok = any(allowed in city_raw for allowed in ALLOWED_MUNICIPALITIES)

    if not city_ok:
        return {
            "is_valid_zone": False,
            "real_city": city_raw.title(),
            "real_neighborhood": suburb_raw.title() or None,
            "rejection_reason": f"Municipio real: '{city_raw.title()}' (no es Capital, Godoy Cruz ni Guaymallén)",
            "geocode_verified": True
        }

    # Si es Guaymallén, verificar que sea solo Dorrego
    is_guaymallen = "guaymall" in city_raw
    if is_guaymallen:
        is_dorrego = any(nb in suburb_raw for nb in GUAYMALLEN_ALLOWED_NEIGHBORHOODS)
        if not is_dorrego:
            return {
                "is_valid_zone": False,
                "real_city": "Guaymallén",
                "real_neighborhood": suburb_raw.title() or "Barrio no identificado",
                "rejection_reason": f"En Guaymallén solo se acepta Dorrego. Ubicación real: '{suburb_raw.title() or 'barrio no identificado'}'",
                "geocode_verified": True
            }

    return {
        "is_valid_zone": True,
        "real_city": city_raw.title(),
        "real_neighborhood": suburb_raw.title() or None,
        "rejection_reason": None,
        "geocode_verified": True
    }
