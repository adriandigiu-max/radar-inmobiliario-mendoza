"""
Módulo de Notificaciones por WhatsApp (Meta WhatsApp Cloud API).
Envía alertas únicamente para propiedades NOVEDOSAS con score >= 80%.
Registra en base de datos local (sent_whatsapp.json) para garantizar que jamás se reenvíe un aviso.
"""

import os
import json
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("WhatsAppNotifier")

DEFAULT_API_VERSION = "v20.0"


def normalize_phone(phone: str) -> str:
    """
    Normaliza el número para Meta Cloud API en Argentina.
    Para +54 9 261 383-6576 (13 dígitos con prefijo internacional + celular):
    Meta Cloud API requiere el formato 542613836576 (12 dígitos, sin el '9' móvil).
    """
    cleaned = "".join(c for c in phone if c.isdigit())
    if cleaned.startswith("549") and len(cleaned) == 13:
        return "54" + cleaned[3:]
    return cleaned


def send_whatsapp_message(
    to: str,
    message: str,
    token: str,
    phone_number_id: str,
    api_version: str = DEFAULT_API_VERSION
) -> Dict[str, Any]:
    """Envía un mensaje de texto vía WhatsApp Cloud API."""
    if not token or not phone_number_id:
        logger.error("Credenciales de WhatsApp incompletas (falta token o phone_number_id).")
        return {"success": False, "error": "missing_credentials"}

    base_url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    target_to = normalize_phone(to)
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": target_to,
        "type": "text",
        "text": {
            "body": message
        }
    }

    try:
        resp = requests.post(base_url, json=payload, headers=headers, timeout=15)
        res_data = resp.json()

        if resp.status_code >= 400:
            err = res_data.get("error", {})
            err_code = err.get("code")
            err_msg = err.get("message", "")

            # Si falló porque no estaba en la whitelist o por formato, reintentar con el formato con 9 si aplica
            if target_to != to and err_code != 131030:
                logger.warning(f"Reintentando envío a {to} con formato original...")
                payload["to"] = "".join(c for c in to if c.isdigit())
                retry_resp = requests.post(base_url, json=payload, headers=headers, timeout=15)
                if retry_resp.status_code < 400:
                    logger.info(f"Mensaje WhatsApp enviado exitosamente a {to} (reintento)")
                    return {"success": True, "data": retry_resp.json(), "recipient": to}

            if err_code == 131030:
                logger.error(
                    f"Número {to} no está en la lista de destinatarios autorizados en Meta Developers "
                    f"(Modo Sandbox/Desarrollo). Debe agregarse en el panel de Meta WhatsApp."
                )
            else:
                logger.error(f"Error {resp.status_code} enviando WhatsApp a {to}: {res_data}")

            return {"success": False, "error": res_data, "recipient": to}

        logger.info(f"Mensaje WhatsApp enviado exitosamente a {to} (destinatario API: {target_to})")
        return {"success": True, "data": res_data, "recipient": to}

    except Exception as e:
        logger.error(f"Excepción al enviar WhatsApp a {to}: {e}")
        return {"success": False, "error": str(e), "recipient": to}


def get_sent_database_path(data_dir: Path) -> Path:
    return data_dir / "sent_whatsapp.json"


def load_sent_database(data_dir: Path) -> Dict[str, Any]:
    db_path = get_sent_database_path(data_dir)
    if db_path.exists():
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error al leer {db_path}: {e}")
            return {}
    return {}


def save_sent_database(db: Dict[str, Any], data_dir: Path):
    db_path = get_sent_database_path(data_dir)
    try:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error guardando {db_path}: {e}")


def seed_existing_properties(data_dir: Path):
    """
    Registra todas las propiedades actualmente conocidas como 'ya procesadas / descartadas para whatsapp'.
    Esto asegura que NINGÚN aviso ya encontrado previamente sea reenviado jamás.
    """
    db = load_sent_database(data_dir)
    existing_count = 0

    # 1. Cargar desde seen_properties.json
    seen_path = data_dir / "seen_properties.json"
    if seen_path.exists():
        try:
            with open(seen_path, "r", encoding="utf-8") as f:
                seen_dict = json.load(f)
                for pkey, date_seen in seen_dict.items():
                    if pkey not in db:
                        db[pkey] = {
                            "status": "pre_existing",
                            "first_seen": date_seen,
                            "note": "Descartado por histórico previo (inicio WhatsApp 2026-10-04)"
                        }
                        existing_count += 1
        except Exception as e:
            logger.warning(f"Error leyendo seen_properties.json para seed: {e}")

    # 2. Cargar desde latest_run.json
    latest_path = data_dir / "latest_run.json"
    if latest_path.exists():
        try:
            with open(latest_path, "r", encoding="utf-8") as f:
                latest_list = json.load(f)
                for prop in latest_list:
                    pkey = prop.get("id") or prop.get("url")
                    if pkey and pkey not in db:
                        db[pkey] = {
                            "status": "pre_existing",
                            "title": prop.get("title"),
                            "score": prop.get("analysis", {}).get("opportunity_score"),
                            "note": "Descartado por histórico previo (inicio WhatsApp 2026-10-04)"
                        }
                        existing_count += 1
        except Exception as e:
            logger.warning(f"Error leyendo latest_run.json para seed: {e}")

    save_sent_database(db, data_dir)
    if existing_count > 0:
        logger.info(f"Base de datos WhatsApp inicializada: {existing_count} propiedades históricas bloqueadas.")


def format_whatsapp_property_message(prop: Dict[str, Any]) -> str:
    """Formatea la propiedad con emojis y markdown para WhatsApp."""
    analysis = prop.get("analysis", {})
    score = analysis.get("opportunity_score", 0)
    cat_b = prop.get("category_b_metrics", {})
    cat_c = analysis.get("category_c", {})
    nego = analysis.get("negotiation_analysis", {})

    price = prop.get("price_usd", 0)
    surface = prop.get("surface_m2") or "N/D"
    price_m2 = cat_b.get("price_per_m2")
    price_m2_str = f" (${price_m2:,.0f} USD/m²)" if price_m2 else ""

    zone = prop.get("location_zone", "Mendoza")
    prop_type = prop.get("property_type", "Propiedad").title()

    bedrooms = prop.get("bedrooms")
    rooms = prop.get("rooms")
    bathrooms = prop.get("bathrooms") or 2

    distrib = []
    if rooms:
        distrib.append(f"{rooms} amb.")
    if bedrooms:
        distrib.append(f"{bedrooms} dorm.")
    distrib.append(f"{bathrooms} baños")
    distrib_str = " | ".join(distrib)

    # Pros
    pros = analysis.get("pros", [])
    pros_text = ""
    if pros:
        pros_bullets = "\n".join(f"  • {p}" for p in pros[:4])
        pros_text = f"\n\n✨ *Puntos destacados:*\n{pros_bullets}"

    # Advertencias / Cons
    cons = analysis.get("cons", [])
    cons_text = ""
    if cons:
        cons_bullets = "\n".join(f"  • {c}" for c in cons[:2])
        cons_text = f"\n\n⚠️ *A tener en cuenta:*\n{cons_bullets}"

    title = prop.get("title", "").strip()
    url = prop.get("url", "")

    msg = (
        f"🏠 *¡NUEVA OPORTUNIDAD INMOBILIARIA!*\n"
        f"⭐ *Score:* *{score}/100*\n\n"
        f"📍 *Zona:* {zone} ({prop_type})\n"
        f"💵 *Precio:* *USD {price:,.0f}*\n"
        f"📐 *Superficie:* {surface} m² cubiertos{price_m2_str}\n"
        f"🚪 *Distribución:* {distrib_str}"
        f"{pros_text}"
        f"{cons_text}\n\n"
        f"📝 *Título:* _{title}_\n\n"
        f"🔗 *Ver publicación:*\n{url}"
    )

    return msg


def process_whatsapp_notifications(
    evaluated_opportunities: List[Dict[str, Any]],
    config: Dict[str, Any],
    data_dir: Path
) -> int:
    """
    Evalúa y envía por WhatsApp únicamente los avisos NOVEDOSOS con score >= 80%.
    Garantiza que no se reenvíen propiedades ya enviadas o preexistentes.
    Retorna la cantidad de avisos enviados.
    """
    whatsapp_cfg = config.get("notifications", {}).get("whatsapp", {})
    if not whatsapp_cfg.get("enabled", False):
        logger.info("Notificaciones por WhatsApp desactivadas en la configuración.")
        return 0

    token = os.getenv("WHATSAPP_TOKEN") or whatsapp_cfg.get("token")
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or whatsapp_cfg.get("phone_number_id")
    api_version = whatsapp_cfg.get("api_version", DEFAULT_API_VERSION)
    recipients = whatsapp_cfg.get("recipients", [])
    min_score = whatsapp_cfg.get("min_score", 80)

    if not token or not phone_number_id:
        logger.warning("Credenciales de WhatsApp no encontradas. Saltando notificación WhatsApp.")
        return 0

    if not recipients:
        logger.warning("No hay destinatarios de WhatsApp configurados.")
        return 0

    # Asegurar que la base de datos de envíos exista y tenga el histórico previo bloqueado
    db = load_sent_database(data_dir)
    if not db:
        seed_existing_properties(data_dir)
        db = load_sent_database(data_dir)

    sent_count = 0
    now_str = datetime.now().isoformat()

    logger.info(f"Evaluando propiedades para WhatsApp (Filtros: Novedad + Score >= {min_score})...")

    for prop in evaluated_opportunities:
        pkey = prop.get("id") or prop.get("url")
        if not pkey:
            continue

        score = prop.get("analysis", {}).get("opportunity_score", 0)
        is_new = prop.get("is_new", False)

        # 1. Verificar si ya fue procesada/enviada históricamente
        if pkey in db:
            continue

        # 2. Requisito estricto: Debe ser novedad de hoy
        if not is_new:
            continue

        # 3. Requisito estricto: Score >= min_score (80)
        if score < min_score:
            continue

        # Cumple todos los requisitos -> Enviar
        logger.info(f"¡Oportunidad calificada encontrada! {pkey} (Score: {score}) -> Enviando WhatsApp...")
        msg_text = format_whatsapp_property_message(prop)

        sent_recipients = []
        failed_recipients = []

        for rec in recipients:
            res = send_whatsapp_message(
                to=rec,
                message=msg_text,
                token=token,
                phone_number_id=phone_number_id,
                api_version=api_version
            )
            if res.get("success"):
                sent_recipients.append(rec)
            else:
                failed_recipients.append(rec)

        # Registrar en la base de datos para NUNCA reenviar
        db[pkey] = {
            "status": "sent" if sent_recipients else "failed",
            "score": score,
            "title": prop.get("title"),
            "price_usd": prop.get("price_usd"),
            "url": prop.get("url"),
            "sent_at": now_str,
            "sent_recipients": sent_recipients,
            "failed_recipients": failed_recipients
        }
        save_sent_database(db, data_dir)

        if sent_recipients:
            sent_count += 1

    logger.info(f"Notificaciones WhatsApp finalizadas: {sent_count} avisos nuevos enviados.")
    return sent_count
