"""
Script principal del Agente Inmobiliario - Mendoza.
Ejecuta el ciclo diario: Scrape -> Filtro Categoría A -> Scoring B -> Evaluación IA / Categoría C -> Notificación.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import yaml
from dotenv import load_dotenv

from scraper.inmoclick import scrape_all_inmoclick
from scraper.argenprop import scrape_argenprop
from scraper.mercadolibre import scrape_mercadolibre
from analyzer.filter import check_category_a, calculate_category_b_score
from analyzer.ai_evaluator import evaluate_property
from notifier.mailer import send_email_report, generate_email_html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RadarInmobiliario")


def load_configuration() -> dict:
    """Carga config.yaml y variables de entorno."""
    base_dir = Path(__file__).parent
    load_dotenv(base_dir / ".env")

    config_path = base_dir / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"No se encontró {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Inyectar variables de entorno en la configuración si existen
    if os.getenv("GEMINI_API_KEY"):
        config["gemini_api_key"] = os.getenv("GEMINI_API_KEY")

    email_cfg = config.get("notifications", {}).get("email", {})
    if os.getenv("SMTP_SENDER_EMAIL"):
        email_cfg["sender_email"] = os.getenv("SMTP_SENDER_EMAIL")
    if os.getenv("SMTP_APP_PASSWORD"):
        email_cfg["sender_app_password"] = os.getenv("SMTP_APP_PASSWORD")
    if os.getenv("SMTP_RECIPIENT_EMAIL"):
        email_cfg["recipient_email"] = os.getenv("SMTP_RECIPIENT_EMAIL")

    return config


def run_pipeline():
    logger.info("Iniciando Radar Inmobiliario de Mendoza...")
    config = load_configuration()

    search_cfg = config.get("search", {})
    locations = (
        search_cfg.get("locations", {}).get("primary", []) +
        search_cfg.get("locations", {}).get("secondary", [])
    )
    max_price = search_cfg.get("budget", {}).get("max_search_price_usd", 132000)

    # 1. Scraping
    logger.info(f"Rastreando portales para zonas: {', '.join(locations)} (Hasta USD {max_price:,.0f})...")
    raw_properties = []

    portals_cfg = config.get("portals", {})
    if portals_cfg.get("inmoclick", {}).get("enabled", True):
        logger.info("Consultando Inmoclick Mendoza...")
        inmoclick_props = scrape_all_inmoclick(locations, max_price_usd=max_price)
        logger.info(f"Inmoclick: {len(inmoclick_props)} propiedades encontradas.")
        raw_properties.extend(inmoclick_props)

    if portals_cfg.get("argenprop", {}).get("enabled", True):
        logger.info("Consultando Argenprop...")
        argenprop_props = scrape_argenprop(max_price_usd=max_price, max_pages=2)
        raw_properties.extend(argenprop_props)

    if portals_cfg.get("mercadolibre", {}).get("enabled", True):
        logger.info("Consultando Mercado Libre Inmuebles...")
        ml_props = scrape_mercadolibre(max_price_usd=max_price)
        raw_properties.extend(ml_props)

    logger.info(f"Total propiedades capturadas antes de filtros: {len(raw_properties)}")

    # 2. Categoría A (Filtro Excluyente)
    logger.info("Aplicando filtros excluyentes de Categoría A...")
    valid_properties = []
    discarded_count = 0

    for prop in raw_properties:
        passes, reason = check_category_a(prop, config)
        if passes:
            valid_properties.append(prop)
        else:
            discarded_count += 1

    logger.info(f"Propiedades que superaron Categoría A: {len(valid_properties)} (Descartadas: {discarded_count})")

    # 2b. Verificación Geográfica por GPS (Nominatim / OpenStreetMap)
    # Confirma que las coordenadas GPS del aviso corresponden realmente a la zona permitida.
    logger.info("Verificando coordenadas GPS de cada propiedad (Nominatim)...")
    geo_verified = []
    geo_rejected = 0
    from analyzer.geo_verifier import verify_zone_by_coordinates
    for prop in valid_properties:
        geo_result = verify_zone_by_coordinates(prop)
        if geo_result["is_valid_zone"]:
            prop["geo_verification"] = geo_result
            geo_verified.append(prop)
        else:
            geo_rejected += 1
            safe_title = prop.get('title', '')[:60].encode('ascii', 'replace').decode('ascii')
            safe_reason = geo_result['rejection_reason'].encode('ascii', 'replace').decode('ascii')
            logger.info(
                f"  Descartado GPS: [{prop.get('location_zone')}] {safe_title} -> {safe_reason}"
            )

    logger.info(f"Verificación GPS: {len(geo_verified)} válidas, {geo_rejected} descartadas por zona incorrecta.")
    valid_properties = geo_verified


    logger.info("Evaluando oportunidades (Categoría B y Categoría C con IA)...")
    evaluated_opportunities = []
    api_key = config.get("gemini_api_key")

    for prop in valid_properties:
        cat_b = calculate_category_b_score(prop, config)
        eval_result = evaluate_property(prop, cat_b, api_key=api_key)

        prop_result = {
            **prop,
            "category_b_metrics": cat_b,
            "analysis": eval_result,
        }
        evaluated_opportunities.append(prop_result)

    # Ordenar por Score de Oportunidad de mayor a menor
    evaluated_opportunities.sort(
        key=lambda x: x.get("analysis", {}).get("opportunity_score", 0),
        reverse=True
    )

    # Guardar resultados en data/
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)

    json_path = data_dir / "latest_run.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(evaluated_opportunities, f, ensure_ascii=False, indent=2)

    # Exportar a Excel y CSV para compartir
    try:
        import pandas as pd
        rows = []
        for p in evaluated_opportunities:
            a = p.get("analysis", {})
            c = a.get("category_c", {})
            b = p.get("category_b_metrics", {})
            nego = a.get("negotiation_analysis", {})
            rows.append({
                "Score (0-100)": a.get("opportunity_score", 0),
                "Zona": p.get("location_zone", ""),
                "Tipo": p.get("property_type", "").title(),
                "Precio USD": p.get("price_usd", 0),
                "Superficie m2": p.get("surface_m2") or "N/D",
                "USD/m2": b.get("price_per_m2") or "N/D",
                "Red de Gas": "Sí" if c.get("has_gas_network") else "No/Duda",
                "Cochera": "Sí" if c.get("has_parking") else "No",
                "2+ Baños": "Sí" if c.get("two_bathrooms") else "No",
                "Seguridad/Privado": "Sí" if c.get("has_security") else "No",
                "Último Piso": "Sí" if c.get("is_top_floor") else "No",
                "Potencial Negociación": nego.get("potential", ""),
                "Título": p.get("title", ""),
                "Link Publicación": p.get("url", ""),
                "Pros Detectados": " | ".join(a.get("pros", [])),
                "Observaciones": " | ".join(a.get("cons", []))
            })
        df = pd.DataFrame(rows)
        excel_path = data_dir / "oportunidades_mendoza.xlsx"
        csv_path = data_dir / "oportunidades_mendoza.csv"
        df.to_excel(excel_path, index=False)
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        logger.info(f"Planilla Excel generada en {excel_path}")
    except Exception as e:
        logger.warning(f"No se pudo generar Excel: {e}")

    # Generar y guardar vista previa HTML del reporte
    email_cfg = config.get("notifications", {}).get("email", {})
    app_url = email_cfg.get("app_url", "https://radar-inmobiliario-mendoza.streamlit.app")
    html_report = generate_email_html(
        opportunities=evaluated_opportunities,
        search_summary=search_cfg,
        app_url=app_url,
        total_found=len(evaluated_opportunities)
    )
    html_path = data_dir / "latest_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_report)

    logger.info(f"Resultados guardados en {json_path} y reporte HTML en {html_path}")

    # 4. Envío de Notificación por Email
    email_cfg = config.get("notifications", {}).get("email", {})
    if email_cfg.get("enabled", False):
        logger.info("Enviando reporte por email...")
        sent = send_email_report(evaluated_opportunities, email_cfg, search_cfg)
        if sent:
            logger.info("Email enviado exitosamente.")
    else:
        logger.info("Notificación por email desactivada en config.yaml. Puedes ver el reporte en data/latest_report.html")

    return evaluated_opportunities


if __name__ == "__main__":
    run_pipeline()
