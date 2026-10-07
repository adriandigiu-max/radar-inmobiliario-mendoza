"""
Servidor y Bot Interactivo de WhatsApp para Radar Inmobiliario Mendoza.

Funcionalidades:
1. Webhook de WhatsApp:
   - GET /webhook: Verificación con Meta Cloud API.
   - POST /webhook: Recepción de mensajes en tiempo real.
     * Si el usuario envía un número del 1 al 5:
       Envía los N avisos en orden decreciente de score.
       Prioriza novedades y, si se acaban, continúa con los ya mandados.
     * Si envía cualquier otro texto:
       Responde: "Por favor enviá un número del 1 al 5 con los avisos que quieras ver."
2. Scheduler Diario Automático:
   - Corre la búsqueda todos los días a las 08:00 AM en la PC.
   - Si alguna novedad supera score 80, la envía proactivamente.
3. POST /run-scan:
   - Endpoint manual para disparar la búsqueda en cualquier momento.
"""

import os
import sys
import json
import time
import logging
import re
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, BackgroundTasks, Query
import uvicorn
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

from main import run_pipeline, load_configuration
from notifier.whatsapp_notifier import (
    send_whatsapp_message,
    format_whatsapp_property_message,
    load_sent_database,
    save_sent_database,
    DEFAULT_API_VERSION
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("RadarBot")


def get_properties_for_user(from_phone: str, count: int) -> List[Dict[str, Any]]:
    """
    Retorna 'count' propiedades en orden decreciente de score.
    Prioriza novedades (aún no entregadas a este usuario) y, si se acaban las novedades,
    continúa con los avisos ya mandados con mayor puntaje.
    """
    data_dir = BASE_DIR / "data"
    latest_path = data_dir / "latest_run.json"
    if not latest_path.exists():
        logger.warning(f"No se encontró {latest_path}")
        return []

    try:
        with open(latest_path, "r", encoding="utf-8") as f:
            all_props = json.load(f)
    except Exception as e:
        logger.error(f"Error leyendo {latest_path}: {e}")
        return []

    if not all_props:
        return []

    # Ordenar por opportunity_score descendente
    all_props.sort(
        key=lambda x: x.get("analysis", {}).get("opportunity_score", 0),
        reverse=True
    )

    db = load_sent_database(data_dir)
    user_deliveries = db.setdefault("_user_deliveries", {}).get(from_phone, [])

    # Separar en novedades y ya mandadas para este usuario
    novedades = []
    ya_mandadas = []

    for prop in all_props:
        pkey = prop.get("id") or prop.get("url")
        if pkey in user_deliveries:
            ya_mandadas.append(prop)
        else:
            novedades.append(prop)

    # 1. Seleccionar novedades primero
    selected = []
    selected.extend(novedades[:count])

    # 2. Si se acaban las novedades, seguir con los avisos ya mandados de mayor score
    if len(selected) < count:
        needed = count - len(selected)
        selected.extend(ya_mandadas[:needed])

    return selected[:count]


def mark_properties_sent_to_user(from_phone: str, props: List[Dict[str, Any]]):
    """Registra en sent_whatsapp.json las propiedades entregadas a este usuario."""
    data_dir = BASE_DIR / "data"
    db = load_sent_database(data_dir)
    user_deliveries = db.setdefault("_user_deliveries", {}).setdefault(from_phone, [])

    for prop in props:
        pkey = prop.get("id") or prop.get("url")
        if pkey and pkey not in user_deliveries:
            user_deliveries.append(pkey)

    save_sent_database(db, data_dir)


def handle_incoming_text(from_phone: str, text: str):
    """Procesa el mensaje recibido según las reglas solicitadas."""
    logger.info(f"Mensaje entrante de {from_phone}: '{text}'")
    token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if not token or not phone_id:
        logger.error("Credenciales de WhatsApp no configuradas en el entorno.")
        return

    cleaned = text.strip()

    # Comprobar si el mensaje es un número del 1 al 5
    match = re.search(r"^[^\d]*([1-5])[^\d]*$", cleaned)
    if not match:
        # Leyenda requerida si no se recibe un número del 1 al 5
        prompt_text = "Por favor enviá un número del 1 al 5 con los avisos que quieras ver."
        send_whatsapp_message(
            to=from_phone,
            message=prompt_text,
            token=token,
            phone_number_id=phone_id
        )
        return

    count = int(match.group(1))
    logger.info(f"Usuario {from_phone} solicitó {count} avisos.")

    props = get_properties_for_user(from_phone, count)
    if not props:
        send_whatsapp_message(
            to=from_phone,
            message="🔎 Por el momento no encontré avisos disponibles que cumplan los filtros.",
            token=token,
            phone_number_id=phone_id
        )
        return

    # Mensaje de cabecera
    intro = f"📋 Te comparto los *{len(props)}* avisos seleccionados (ordenados por score de mayor a menor):"
    send_whatsapp_message(to=from_phone, message=intro, token=token, phone_number_id=phone_id)
    time.sleep(1.0)

    # Envío de fichas individuales
    for prop in props:
        card = format_whatsapp_property_message(prop)
        send_whatsapp_message(to=from_phone, message=card, token=token, phone_number_id=phone_id)
        time.sleep(1.2)

    mark_properties_sent_to_user(from_phone, props)
    logger.info(f"Se entregaron {len(props)} avisos a {from_phone}.")


def process_webhook_payload(body: Dict[str, Any]):
    """Parsea el payload de Meta WhatsApp Cloud API y extrae los mensajes de texto."""
    entry_list = body.get("entry", [])
    for entry in entry_list:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                from_phone = msg.get("from")
                msg_type = msg.get("type")
                if msg_type == "text":
                    body_text = msg.get("text", {}).get("body", "")
                    if from_phone and body_text:
                        handle_incoming_text(from_phone, body_text)


async def daily_scheduler_loop():
    """Ciclo en segundo plano para escaneo diario automático (08:00 AM hora local)."""
    logger.info("Scheduler diario de búsqueda inmobiliaria iniciado.")
    last_run_day = None
    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # Ejecutar a partir de las 08:00 AM si no se ha ejecutado hoy
            if now.hour >= 8 and last_run_day != today_str:
                logger.info(f"Iniciando escaneo diario automático ({today_str})...")
                last_run_day = today_str
                # Ejecutar pipeline en un thread para no bloquear el servidor FastAPI
                await asyncio.to_thread(run_pipeline)
                logger.info("Escaneo diario finalizado exitosamente.")
        except Exception as e:
            logger.error(f"Error en scheduler diario: {e}")

        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Iniciar scheduler al encender la app
    scheduler_task = asyncio.create_task(daily_scheduler_loop())
    yield
    scheduler_task.cancel()


app = FastAPI(
    title="Radar Inmobiliario Mendoza - Bot de WhatsApp",
    description="Bot interactivo y notificador proactivo para WhatsApp",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "service": "Radar Inmobiliario Mendoza Bot",
        "version": "1.0.0"
    }


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """Endpoint de verificación requerido por Meta WhatsApp Cloud API."""
    expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "secretaria_verify_2026")
    logger.info(f"Verificación de Webhook: mode={hub_mode}, token={hub_verify_token}")
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("Webhook verificado exitosamente.")
        return Response(content=hub_challenge, media_type="text/plain", status_code=200)

    logger.warning("Fallo en verificación de Webhook.")
    return Response(content="Verification failed", status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recepción de eventos de WhatsApp desde Meta."""
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"Error parseando JSON de webhook: {e}")
        return Response(status_code=400)

    # Procesar en background para responder 200 OK inmediatamente a Meta
    background_tasks.add_task(process_webhook_payload, body)
    return Response(content="EVENT_RECEIVED", status_code=200)


@app.post("/run-scan")
async def trigger_scan(background_tasks: BackgroundTasks):
    """Permite disparar la búsqueda manualmente vía API."""
    logger.info("Disparando búsqueda manual vía endpoint /run-scan...")
    background_tasks.add_task(run_pipeline)
    return {"status": "scan_started", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    uvicorn.run(
        "bot_service:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
