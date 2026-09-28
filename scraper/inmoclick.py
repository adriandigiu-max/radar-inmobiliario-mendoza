"""
Scraper especializado para Inmoclick (portal líder inmobiliario de Mendoza y Cuyo).
Focalizado en:
- Mendoza (Capital)
- Godoy Cruz
- Guaymallén (luego filtrado exclusivamente por Dorrego)
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.inmoclick.com.ar"

SEARCH_TARGETS = [
    # Mendoza Capital
    {"zone": "Mendoza", "type": "departamento", "slug": "departamentos-en-venta-en-mendoza"},
    {"zone": "Mendoza", "type": "casa", "slug": "casas-en-venta-en-mendoza"},
    # Godoy Cruz
    {"zone": "Godoy Cruz", "type": "departamento", "slug": "departamentos-en-venta-en-godoy-cruz-mendoza"},
    {"zone": "Godoy Cruz", "type": "casa", "slug": "casas-en-venta-en-godoy-cruz-mendoza"},
    # Guaymallén (para extraer Dorrego)
    {"zone": "Guaymallen", "type": "departamento", "slug": "departamentos-en-venta-en-guaymallen-mendoza"},
    {"zone": "Guaymallen", "type": "casa", "slug": "casas-en-venta-en-guaymallen-mendoza"},
]


def clean_price_usd(price_str: str) -> Optional[float]:
    """Extrae el precio numérico en USD si la publicación está en dólares."""
    if not price_str:
        return None
    price_str = price_str.upper().strip()
    if "US$" not in price_str and "USD" not in price_str and "U$D" not in price_str and "U$S" not in price_str:
        return None

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


def parse_surface(val: str) -> Optional[float]:
    """Parsea el valor de superficie (m2)"""
    if not val or val == "disable":
        return None
    clean_val = re.sub(r"[^\d.]", "", val.replace(",", "."))
    try:
        return float(clean_val)
    except ValueError:
        return None


def scrape_slug(target: Dict[str, str], max_price_usd: float = 152000, max_pages: int = 3) -> List[Dict[str, Any]]:
    """Rastrea publicaciones para un tipo de propiedad y zona."""
    slug = target["slug"]
    zone = target["zone"]
    prop_type = target["type"]
    results = []

    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}/inmuebles/{slug}"
        params = {}
        if page > 1:
            params["page"] = page

        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
            if resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            articles = soup.find_all("article")
            if not articles:
                break

            for article in articles:
                raw_price = article.get("precio", "")
                price_usd = clean_price_usd(raw_price)
                if not price_usd or price_usd > max_price_usd:
                    continue

                sup_c = parse_surface(article.get("sup_c", ""))
                sup_t = parse_surface(article.get("sup_t", ""))
                surface_m2 = sup_c if sup_c else sup_t

                raw_baths = article.get("ser_2", "")
                bathrooms = int(raw_baths) if raw_baths.isdigit() else (None if raw_baths == "disable" else 1)
                
                raw_garage = article.get("ser_3", "").lower()
                has_garage = "garage" in raw_garage or "cochera" in raw_garage or raw_garage == "si"

                link_elem = article.select_one(".description-hover a") or article.find("a", href=True)
                item_url = ""
                if link_elem and link_elem.get("href"):
                    href = link_elem["href"]
                    item_url = href if href.startswith("http") else f"{BASE_URL}{href}"

                desc_elem = article.select_one(".description-hover p") or article.select_one(".description-hover")
                description = desc_elem.get_text("\n", strip=True) if desc_elem else ""

                first_line = description.split("\n")[0].strip() if description else ""
                title = first_line if (first_line and len(first_line) > 10) else f"{prop_type.title()} en {zone}"

                img_elem = article.find("img")
                img_url = ""
                if img_elem:
                    img_url = img_elem.get("data-original") or img_elem.get("src") or ""
                    if img_url and not img_url.startswith("http"):
                        img_url = f"{BASE_URL}{img_url}"

                lat = article.get("lat")
                lng = article.get("lng")

                prp_id = article.get("prp_id", "")
                usr_id = article.get("usr_id", "")
                item_id = f"inmoclick_{usr_id}_{prp_id}"

                prop = {
                    "id": item_id,
                    "portal": "Inmoclick",
                    "title": title,
                    "property_type": prop_type,
                    "price_usd": price_usd,
                    "surface_m2": surface_m2,
                    "surface_total_m2": sup_t,
                    "surface_covered_m2": sup_c,
                    "bathrooms": bathrooms,
                    "has_parking_attribute": has_garage,
                    "location_zone": zone,
                    "url": item_url,
                    "image_url": img_url,
                    "description": description,
                    "coordinates": {"lat": lat, "lng": lng} if lat and lng else None,
                }
                results.append(prop)

            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error raspando Inmoclick {slug}: {e}")
            break

    return results


def scrape_all_inmoclick(locations: List[str] = None, max_price_usd: float = 152000) -> List[Dict[str, Any]]:
    """Rastrea Capital, Godoy Cruz y Guaymallén."""
    all_properties = []
    seen_ids = set()

    for target in SEARCH_TARGETS:
        logger.info(f"Consultando Inmoclick: {target['type']}s en {target['zone']}...")
        props = scrape_slug(target, max_price_usd=max_price_usd, max_pages=3)
        for p in props:
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                all_properties.append(p)

    return all_properties
