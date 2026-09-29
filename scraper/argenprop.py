"""
Scraper especializado para Argenprop en Mendoza.
Zonas: Mendoza Capital, Godoy Cruz y Guaymallén (filtrado por Dorrego).
"""

import re
import time
import logging
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

BASE_URL = "https://www.argenprop.com"

ARGENPROP_TARGETS = [
    {
        "zone": "Mendoza",
        "url": f"{BASE_URL}/casas-o-departamentos/venta/mendoza/dolares-hasta-152000"
    },
    {
        "zone": "Godoy Cruz",
        "url": f"{BASE_URL}/casas-o-departamentos/venta/godoy-cruz/dolares-hasta-152000"
    },
    {
        "zone": "Guaymallen",
        "url": f"{BASE_URL}/casas-o-departamentos/venta/guaymallen/dolares-hasta-152000"
    }
]


def clean_price_usd(price_str: str) -> Optional[float]:
    """Extrae el precio numérico en USD."""
    if not price_str:
        return None
    raw = price_str.upper()
    if "USD" not in raw and "U$S" not in raw and "U$D" not in raw and "$" not in raw:
        return None
    # Eliminar textos y obtener dígitos
    digits = re.sub(r"[^\d]", "", price_str)
    if not digits:
        return None
    try:
        val = float(digits)
        if val < 25000:
            return None
        return val
    except ValueError:
        return None


def scrape_argenprop(max_price_usd: float = 152000, max_pages: int = 2) -> List[Dict[str, Any]]:
    """Rastrea publicaciones de Argenprop para Mendoza."""
    results = []
    seen_urls = set()

    for target in ARGENPROP_TARGETS:
        zone = target["zone"]
        base_target_url = target["url"]
        logger.info(f"Consultando Argenprop: {zone}...")

        for page in range(1, max_pages + 1):
            url = f"{base_target_url}?pagina-{page}" if page > 1 else base_target_url
            try:
                resp = requests.get(url, headers=HEADERS, timeout=12)
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select(".listing__item") or soup.select("div.card")
                if not cards:
                    break

                for card in cards:
                    # Enlace
                    link_el = card.select_one("a[href]")
                    if not link_el or not link_el.get("href"):
                        continue
                    href = link_el["href"]
                    item_url = f"{BASE_URL}{href}" if href.startswith("/") else href

                    if item_url in seen_urls:
                        continue
                    seen_urls.add(item_url)

                    # Título
                    title_el = card.select_one(".card__title--primary") or card.select_one(".card__title")
                    title = title_el.text.strip() if title_el else f"Inmueble en {zone}"

                    # Precio
                    price_el = card.select_one(".card__price")
                    price_usd = clean_price_usd(price_el.text if price_el else "")
                    if not price_usd or price_usd > max_price_usd:
                        continue

                    # Dirección
                    address_el = card.select_one(".card__address")
                    address = address_el.text.strip() if address_el else ""

                    # Tipo de propiedad (inferido de url o título)
                    prop_type = "departamento" if "departamento" in item_url.lower() or "departamento" in title.lower() else "casa"

                    # Características (superficie, baños, dormitorios)
                    features = [f.text.strip().lower() for f in card.select(".card__main-features li")]
                    surface_m2 = None
                    bathrooms = None

                    for f in features:
                        # Superficie
                        m2_match = re.search(r"(\d+)\s*m", f)
                        if m2_match and not surface_m2:
                            try:
                                surface_m2 = float(m2_match.group(1))
                            except ValueError:
                                pass
                        # Baños
                        if "baño" in f or "bano" in f:
                            bath_match = re.search(r"(\d+)", f)
                            if bath_match:
                                try:
                                    bathrooms = int(bath_match.group(1))
                                except ValueError:
                                    pass

                    # Descripción o extracto
                    desc_el = card.select_one(".card__info") or card.select_one(".card__description")
                    description = desc_el.text.strip() if desc_el else f"{title}. Dirección: {address}."

                    # Imagen
                    img_el = card.select_one("img")
                    img_url = ""
                    if img_el:
                        img_url = img_el.get("data-src") or img_el.get("src") or ""

                    # ID único
                    item_id_match = re.search(r"--(\d+)", item_url)
                    item_id = f"argenprop_{item_id_match.group(1)}" if item_id_match else f"argenprop_{len(results)+1}"

                    results.append({
                        "id": item_id,
                        "portal": "Argenprop",
                        "title": title,
                        "property_type": prop_type,
                        "price_usd": price_usd,
                        "surface_m2": surface_m2,
                        "bathrooms": bathrooms,
                        "has_parking_attribute": any("cochera" in f or "garage" in f for f in features),
                        "location_zone": zone,
                        "address": address,
                        "url": item_url,
                        "image_url": img_url,
                        "description": f"{title}. {description}. Ubicación: {address}",
                        "coordinates": None, # Argenprop no expone lat/lng en la lista de resultados
                    })

                time.sleep(1)

            except Exception as e:
                logger.error(f"Error raspando Argenprop ({zone}, pág {page}): {e}")
                break

    logger.info(f"Argenprop: {len(results)} propiedades encontradas.")
    return results
