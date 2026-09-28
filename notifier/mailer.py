"""
Módulo de Notificación por Email (SMTP de Gmail).
Envía el resumen diario a flordigiu@gmail.com desde adriandigiu@gmail.com
con el Top 3 de novedades y el enlace directo al panel web de Streamlit.
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def generate_email_html(
    opportunities: List[Dict[str, Any]],
    search_summary: Dict[str, Any],
    app_url: str = "https://radar-inmobiliario-mendoza.streamlit.app",
    total_found: int = 0
) -> str:
    """Genera la plantilla HTML responsive con el Top 3 y link a la app."""
    date_str = datetime.now().strftime("%d/%m/%Y")
    top_3 = opportunities[:3]
    total_count = total_found or len(opportunities)

    items_html = ""
    for idx, op in enumerate(top_3, 1):
        analysis = op.get("analysis", {})
        score = analysis.get("opportunity_score", 0)
        cat_c = analysis.get("category_c", {})
        nego = analysis.get("negotiation_analysis", {})
        geo = op.get("geo_verification", {})

        # Ubicación real comprobada por GPS
        city = geo.get("real_city") or op.get("location_zone")
        barrio = geo.get("real_neighborhood") or ""
        loc_str = f"{city} ({barrio})" if barrio else city

        # Color según score
        if score >= 85:
            badge_color = "#059669"  # verde esmeralda
            badge_text = "Oportunidad Destacada"
        elif score >= 70:
            badge_color = "#2563eb"  # azul
            badge_text = "Muy Buena Opción"
        else:
            badge_color = "#d97706"  # ámbar
            badge_text = "Opción Aceptable"

        # Badges Categoría C
        tags_html = ""
        if cat_c.get("has_security"):
            tags_html += '<span style="background:#dcfce7;color:#15803d;padding:4px 9px;border-radius:12px;font-size:12px;font-weight:600;margin-right:6px;display:inline-block;margin-bottom:4px;">🛡️ Seguridad 24hs</span>'
        else:
            tags_html += '<span style="background:#fee2e2;color:#991b1b;padding:4px 9px;border-radius:12px;font-size:12px;margin-right:6px;display:inline-block;margin-bottom:4px;">⚠️ Sin seg. 24hs</span>'

        if cat_c.get("has_gas_network"):
            tags_html += '<span style="background:#e0f2fe;color:#0369a1;padding:4px 9px;border-radius:12px;font-size:12px;margin-right:6px;display:inline-block;margin-bottom:4px;">🔥 Red de Gas</span>'
        if cat_c.get("has_parking"):
            tags_html += '<span style="background:#fef3c7;color:#b45309;padding:4px 9px;border-radius:12px;font-size:12px;margin-right:6px;display:inline-block;margin-bottom:4px;">🚗 Cochera</span>'
        if cat_c.get("has_elevator"):
            tags_html += '<span style="background:#fae8ff;color:#86198f;padding:4px 9px;border-radius:12px;font-size:12px;margin-right:6px;display:inline-block;margin-bottom:4px;">🛗 Ascensor</span>'
        tags_html += '<span style="background:#ede9fe;color:#6d28d9;padding:4px 9px;border-radius:12px;font-size:12px;margin-right:6px;display:inline-block;margin-bottom:4px;">🚿 2 Baños</span>'

        pros_html = "".join([f"<li style='color:#166534;margin-bottom:4px;'>✓ {p}</li>" for p in analysis.get("pros", [])])
        cons_html = "".join([f"<li style='color:#991b1b;margin-bottom:4px;'>! {c}</li>" for c in analysis.get("cons", [])])

        price = op.get("price_usd", 0)
        surface = op.get("surface_m2")
        surface_txt = f"{surface:.0f} m²" if surface else "A consultar"

        items_html += f"""
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;margin-bottom:20px;padding:22px;box-shadow:0 2px 4px rgba(0,0,0,0.04);">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;">
                <div style="flex:1;min-width:260px;">
                    <div style="margin-bottom:8px;">
                        <span style="background:#1e293b;color:#ffffff;padding:3px 9px;border-radius:12px;font-weight:bold;font-size:12px;margin-right:8px;">
                            TOP #{idx}
                        </span>
                        <span style="background:{badge_color};color:#ffffff;padding:3px 9px;border-radius:12px;font-weight:bold;font-size:12px;">
                            Score: {score}/100 — {badge_text}
                        </span>
                    </div>
                    <h2 style="margin:6px 0;font-size:17px;color:#0f172a;line-height:1.3;">{op.get('title')}</h2>
                    <p style="margin:0 0 10px 0;color:#64748b;font-size:14px;">📍 <strong>{loc_str}</strong> • 🏠 {op.get('property_type','').title()} • 📐 {surface_txt}</p>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:24px;font-weight:800;color:#0f172a;">USD {price:,.0f}</div>
                    <div style="font-size:12px;color:#94a3b8;">Portal: {op.get('portal')}</div>
                </div>
            </div>

            <div style="margin:12px 0 14px 0;">{tags_html}</div>

            <div style="background:#f8fafc;border-left:4px solid #3b82f6;padding:10px 14px;margin:12px 0;border-radius:0 8px 8px 0;font-size:13px;color:#334155;">
                {analysis.get('ai_summary', '')}
                {f"<br><strong style='color:#b45309;'>Negociación:</strong> {nego.get('summary')}" if nego.get('summary') else ""}
            </div>

            <div style="display:flex;gap:15px;margin:12px 0;font-size:13px;flex-wrap:wrap;">
                {f"<div style='flex:1;min-width:200px;'><ul style='padding-left:18px;margin:0;'>{pros_html}</ul></div>" if pros_html else ""}
                {f"<div style='flex:1;min-width:200px;'><ul style='padding-left:18px;margin:0;'>{cons_html}</ul></div>" if cons_html else ""}
            </div>

            <div style="margin-top:16px;text-align:right;">
                <a href="{op.get('url')}" target="_blank" style="background:#0284c7;color:#ffffff;text-decoration:none;padding:8px 18px;border-radius:6px;font-weight:600;font-size:13px;display:inline-block;">
                    Ver Publicación en {op.get('portal')} →
                </a>
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#f1f5f9;padding:20px;margin:0;">
        <div style="max-width:680px;margin:0 auto;">
            
            <!-- HEADER -->
            <div style="background:linear-gradient(135deg, #1e293b 0%, #0f172a 100%);color:#ffffff;padding:28px 24px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="margin:0 0 6px 0;font-size:24px;letter-spacing:-0.5px;">🏡 Radar Inmobiliario Mendoza</h1>
                <p style="margin:0;opacity:0.85;font-size:14px;">Actualización diaria del {date_str} • Capital, Godoy Cruz y Dorrego</p>
            </div>
            
            <!-- BOTON DESTACADO APP -->
            <div style="background:#ffffff;padding:18px 24px;border-bottom:1px solid #e2e8f0;text-align:center;">
                <p style="margin:0 0 12px 0;font-size:14px;color:#475569;">
                    El agente analizó las publicaciones de hoy y detectó <strong>{total_count} propiedades</strong> que cumplen todos los criterios.
                </p>
                <a href="{app_url}" target="_blank" style="background:#2563eb;color:#ffffff;text-decoration:none;padding:12px 26px;border-radius:8px;font-weight:700;font-size:15px;display:inline-block;box-shadow:0 2px 4px rgba(37,99,235,0.2);">
                    👉 Abrir Panel Web con todas las oportunidades
                </a>
            </div>

            <!-- TITULO TOP 3 -->
            <div style="padding:20px 6px 10px 6px;">
                <h3 style="margin:0;color:#1e293b;font-size:18px;">🏆 Top 3 Novedades de Hoy</h3>
                <p style="margin:4px 0 0 0;color:#64748b;font-size:13px;">Las 3 mejores opciones ponderadas por precio, superficie, seguridad 24hs y ubicación GPS.</p>
            </div>

            <!-- LISTADO TOP 3 -->
            <div>
                {items_html if items_html else "<p style='text-align:center;color:#64748b;padding:30px 0;'>No se encontraron nuevas propiedades hoy.</p>"}
            </div>

            <!-- FOOTER -->
            <div style="background:#ffffff;border-radius:10px;padding:16px 20px;margin-top:10px;text-align:center;font-size:13px;color:#64748b;">
                ¿Quieres ver todas las {total_count} propiedades o descargarlas en Excel?<br>
                <a href="{app_url}" style="color:#2563eb;font-weight:600;text-decoration:none;">Accede al Panel Interactivo aquí</a>
            </div>

            <div style="text-align:center;color:#94a3b8;font-size:12px;padding:20px 0;">
                Enviado automáticamente desde adriandigiu@gmail.com hacia flordigiu@gmail.com<br>
                Radar Inmobiliario Mendoza
            </div>
        </div>
    </body>
    </html>
    """
    return html


def send_email_report(
    opportunities: List[Dict[str, Any]],
    smtp_config: Dict[str, Any],
    search_summary: Dict[str, Any]
) -> bool:
    """Envía el email del Top 3 vía SMTP."""
    sender = smtp_config.get("sender_email", "adriandigiu@gmail.com")
    password = smtp_config.get("sender_app_password")
    recipient = smtp_config.get("recipient_email", "flordigiu@gmail.com")
    smtp_server = smtp_config.get("smtp_server", "smtp.gmail.com")
    smtp_port = int(smtp_config.get("smtp_port", 587))
    app_url = smtp_config.get("app_url", "https://radar-inmobiliario-mendoza.streamlit.app")

    if not sender or not password or not recipient:
        logger.warning("Falta configurar la contraseña de aplicación SMTP (sender_app_password). Reporte guardado localmente.")
        return False

    try:
        date_str = datetime.now().strftime("%d/%m")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🏡 Radar Inmobiliario Mendoza: Top 3 de hoy ({date_str})"
        msg["From"] = f"Radar Inmobiliario <{sender}>"
        msg["To"] = recipient

        html_body = generate_email_html(
            opportunities=opportunities,
            search_summary=search_summary,
            app_url=app_url,
            total_found=len(opportunities)
        )
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)

        logger.info(f"Reporte enviado con éxito a {recipient} desde {sender}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar correo por SMTP: {e}")
        return False
