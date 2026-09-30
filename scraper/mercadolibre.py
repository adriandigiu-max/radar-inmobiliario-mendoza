"""
Scraper especializado para Mercado Libre Inmuebles en Mendoza.
Zonas: Mendoza Capital, Godoy Cruz y Guaymallén (Dorrego).
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

ML_TARGETS = [
    {
        "zone": "Mendoza",
        "url": "https://inmuebles.mercadolibre.com.ar/venta/mendoza/mendoza/departamento-o-casa_PriceRange_0USD-152000USD"
    },
    {
        "zone": "Godoy Cruz",
        "url": "https://inmuebles.mercadolibre.com.ar/departamentos-casas/venta/mendoza/godoy-cruz/_PriceRange_0USD-152000USD"
    },
    {
        "zone": "Guaymallen",
        "url": "https://inmuebles.mercadolibre.com.ar/venta/mendoza/guaymallen/dorrego/departamento-o-casa_PriceRange_0USD-152000USD"
    }
]


def clean_price_usd(card: BeautifulSoup) -> Optional[float]:
    """Extrae el precio en USD si la publicación está cotizada en dólares."""
    curr_el = card.select_one(".andes-money-amount__currency-symbol") or card.select_one(".price-tag-symbol")
    frac_el = card.select_one(".andes-money-amount__fraction") or card.select_one(".price-tag-fraction")
    if not frac_el:
        return None

    currency = curr_el.text.strip().upper() if curr_el else ""
    # En Mercado Libre, los precios en dólares usan 'U$S', 'US$' o 'USD'
    if "$" in currency and "US" not in currency and "U$S" not in currency and "USD" not in currency:
        # Es en pesos argentinos (ARS)
        return None

    raw_frac = frac_el.text.strip().replace(".", "").replace(",", "")
    try:
        val = float(raw_frac)
        if val < 25000:
            return None
        return val
    except ValueError:
        return None


def scrape_mercadolibre(max_price_usd: float = 152000, max_pages: int = 2) -> List[Dict[str, Any]]:
    """Rastrea publicaciones de Mercado Libre Inmuebles para Mendoza."""
    results = []
    seen_urls = set()

    for target in ML_TARGETS:
        zone = target["zone"]
        base_url = target["url"]
        logger.info(f"Consultando Mercado Libre: {zone}...")

        try:
            resp = requests.get(base_url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select(".ui-search-layout__item") or soup.select("li.ui-search-layout__item")

            for it in items:
                link_el = it.select_one("a[href]")
                if not link_el or not link_el.get("href"):
                    continue

                item_url = link_el["href"].split("#")[0] # Limpiar anclas de tracking
                if item_url in seen_urls:
                    continue
                seen_urls.add(item_url)

                # Precio
                price_usd = clean_price_usd(it)
                if not price_usd or price_usd > max_price_usd:
                    continue

                # Título
                title_el = it.select_one(".poly-component__title") or it.select_one(".ui-search-item__title") or it.select_one("h2")
                title = title_el.text.strip() if title_el else f"Propiedad en {zone}"

                # Atributos (ej: '3 dormitorios', '2 baños', '137 m² cubiertos')
                attrs_el = it.select(".poly-attributes_list__item") or it.select(".ui-search-card-attributes__attribute")
                attrs = [a.text.strip().lower() for a in attrs_el]

                surface_m2 = None
                bathrooms = None
                bedrooms = None
                rooms = None
                has_parking = False

                for a in attrs:
                    # Metros cuadrados
                    if "m²" in a or "m2" in a:
                        m_match = re.search(r"(\d+)", a)
                        if m_match and not surface_m2:
                            try:
                                surface_m2 = float(m_match.group(1))
                            except ValueError:
                                pass
                    # Baños
                    if "baño" in a or "bano" in a:
                        b_match = re.search(r"(\d+)", a)
                        if b_match:
                            try:
                                bathrooms = int(b_match.group(1))
                            except ValueError:
                                pass
                    # Dormitorios / Habitaciones
                    if "dorm" in a or "habitac" in a:
                        d_match = re.search(r"(\d+)", a)
                        if d_match:
                            try:
                                bedrooms = int(d_match.group(1))
                            except ValueError:
                                pass
                    # Ambientes
                    if "amb" in a:
                        amb_match = re.search(r"(\d+)", a)
                        if amb_match:
                            try:
                                rooms = int(amb_match.group(1))
                            except ValueError:
                                pass
                    # Cochera
                    if "cochera" in a or "garage" in a or "estac." in a:
                        has_parking = True

                # Tipo de propiedad
                prop_type = "departamento" if "departamento" in item_url.lower() or "departamento" in title.lower() else "casa"

                # Imagen
                img_el = it.select_one("img")
                img_url = ""
                if img_el:
                    img_url = img_el.get("data-src") or img_el.get("src") or ""

                # ID
                id_match = re.search(r"MLA-?(\d+)", item_url)
                item_id = f"ml_{id_match.group(1)}" if id_match else f"ml_{len(results)+1}"

                results.append({
                    "id": item_id,
                    "portal": "Mercado Libre",
                    "title": title,
                    "property_type": prop_type,
                    "price_usd": price_usd,
                    "surface_m2": surface_m2,
                    "bathrooms": bathrooms,
                    "bedrooms": bedrooms,
                    "rooms": rooms,
                    "has_parking_attribute": has_parking,
                    "location_zone": zone,
                    "url": item_url,
                    "image_url": img_url,
                    "description": f"{title}. Características: {', '.join(attrs)}. Zona: {zone}.",
                    "coordinates": None,
                })

            time.sleep(1)

        except Exception as e:
            logger.error(f"Error raspando Mercado Libre ({zone}): {e}")

    logger.info(f"Mercado Libre: {len(results)} propiedades encontradas.")
    return results
