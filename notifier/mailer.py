"""
Módulo de Notificación por Email (SMTP de Gmail o cualquier proveedor estándar).
Envía un resumen visual en HTML con las mejores oportunidades del día.
"""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def generate_email_html(opportunities: List[Dict[str, Any]], search_summary: Dict[str, Any]) -> str:
    """Genera la plantilla HTML responsive para el correo."""
    date_str = datetime.now().strftime("%d/%m/%Y")
    
    items_html = ""
    for op in opportunities:
        analysis = op.get("analysis", {})
        score = analysis.get("opportunity_score", 0)
        eval_src = analysis.get("evaluation_source", "algoritmo")
        cat_c = analysis.get("category_c", {})
        nego = analysis.get("negotiation_analysis", {})

        # Color según score
        if score >= 85:
            badge_color = "#10b981"  # verde esmeralda
            badge_text = "Oportunidad Destacada"
        elif score >= 70:
            badge_color = "#3b82f6"  # azul
            badge_text = "Muy Buena Opción"
        else:
            badge_color = "#f59e0b"  # ámbar
            badge_text = "Opción Aceptable"

        # Badges Categoría C
        tags_html = ""
        if cat_c.get("has_gas_network"):
            tags_html += '<span style="background:#e0f2fe;color:#0369a1;padding:3px 8px;border-radius:12px;font-size:12px;margin-right:5px;">🔥 Red de Gas</span>'
        if cat_c.get("has_parking"):
            tags_html += '<span style="background:#fef3c7;color:#b45309;padding:3px 8px;border-radius:12px;font-size:12px;margin-right:5px;">🚗 Cochera</span>'
        if cat_c.get("two_bathrooms"):
            tags_html += '<span style="background:#ede9fe;color:#6d28d9;padding:3px 8px;border-radius:12px;font-size:12px;margin-right:5px;">🚿 2 Baños</span>'
        if cat_c.get("has_security"):
            tags_html += '<span style="background:#dcfce7;color:#15803d;padding:3px 8px;border-radius:12px;font-size:12px;margin-right:5px;">🛡️ Seguridad / Privado</span>'
        if cat_c.get("is_top_floor"):
            tags_html += '<span style="background:#fae8ff;color:#86198f;padding:3px 8px;border-radius:12px;font-size:12px;margin-right:5px;">🏢 Último Piso</span>'

        pros_html = "".join([f"<li style='color:#166534;margin-bottom:4px;'>✓ {p}</li>" for p in analysis.get("pros", [])])
        cons_html = "".join([f"<li style='color:#991b1b;margin-bottom:4px;'>! {c}</li>" for c in analysis.get("cons", [])])

        price = op.get("price_usd", 0)
        surface = op.get("surface_m2")
        surface_txt = f"{surface:.0f} m²" if surface else "A consultar"

        items_html += f"""
        <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:20px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;">
                <div>
                    <span style="background:{badge_color};color:#ffffff;padding:4px 10px;border-radius:20px;font-weight:bold;font-size:13px;">
                        Score: {score}/100 — {badge_text}
                    </span>
                    <h2 style="margin:10px 0 5px 0;font-size:18px;color:#111827;">{op.get('title')}</h2>
                    <p style="margin:0 0 10px 0;color:#6b7280;font-size:14px;">📍 {op.get('location_zone')} • {op.get('property_type').title()} • {surface_txt}</p>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:22px;font-weight:bold;color:#1f2937;">USD {price:,.0f}</div>
                    <div style="font-size:12px;color:#6b7280;">Portal: {op.get('portal')}</div>
                </div>
            </div>

            <div style="margin:12px 0;">{tags_html}</div>

            <div style="background:#f9fafb;border-left:4px solid #6366f1;padding:10px 15px;margin:12px 0;border-radius:0 6px 6px 0;font-size:14px;color:#374151;">
                <strong>Análisis ({eval_src.upper()}):</strong> {analysis.get('ai_summary', '')}
                {f"<br><strong style='color:#b45309;'>Margen Negociación:</strong> {nego.get('summary')}" if nego.get('summary') else ""}
            </div>

            <div style="display:flex;gap:20px;margin:10px 0;font-size:13px;flex-wrap:wrap;">
                {f"<div style='flex:1;min-width:200px;'><ul style='padding-left:18px;margin:0;'>{pros_html}</ul></div>" if pros_html else ""}
                {f"<div style='flex:1;min-width:200px;'><ul style='padding-left:18px;margin:0;'>{cons_html}</ul></div>" if cons_html else ""}
            </div>

            <div style="margin-top:15px;text-align:right;">
                <a href="{op.get('url')}" target="_blank" style="background:#2563eb;color:#ffffff;text-decoration:none;padding:8px 18px;border-radius:6px;font-weight:bold;font-size:14px;display:inline-block;">
                    Ver Publicación en {op.get('portal')} →
                </a>
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;background:#f3f4f6;padding:20px;margin:0;">
        <div style="max-width:700px;margin:0 auto;">
            <div style="background:#1e293b;color:#ffffff;padding:24px;border-radius:10px 10px 0 0;text-align:center;">
                <h1 style="margin:0 0 8px 0;font-size:24px;">🏡 Radar Inmobiliario Mendoza</h1>
                <p style="margin:0;opacity:0.8;font-size:14px;">Reporte diario de oportunidades detectadas — {date_str}</p>
            </div>
            
            <div style="background:#ffffff;padding:15px 20px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#4b5563;">
                <strong>Resumen de búsqueda:</strong> Mendoza Capital, Godoy Cruz, Guaymallén, Las Heras • Presupuesto objetivo: USD 120.000 • Metros: desde 50 m² • {len(opportunities)} oportunidades seleccionadas hoy.
            </div>

            <div style="padding:20px 0;">
                {items_html if items_html else "<p style='text-align:center;color:#6b7280;'>No se detectaron nuevas publicaciones que superen el score mínimo hoy.</p>"}
            </div>

            <div style="text-align:center;color:#9ca3af;font-size:12px;padding:20px 0;">
                Generado automáticamente por tu Agente Inmobiliario • Mendoza, Argentina
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
    """Envía el email vía SMTP."""
    sender = smtp_config.get("sender_email")
    password = smtp_config.get("sender_app_password")
    recipient = smtp_config.get("recipient_email")
    smtp_server = smtp_config.get("smtp_server", "smtp.gmail.com")
    smtp_port = int(smtp_config.get("smtp_port", 587))

    if not sender or not password or not recipient:
        logger.warning("Credenciales SMTP no completas. El reporte se guardará localmente.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🏡 Radar Inmobiliario Mendoza: {len(opportunities)} Oportunidades ({datetime.now().strftime('%d/%m')})"
        msg["From"] = f"Radar Inmobiliario <{sender}>"
        msg["To"] = recipient

        html_body = generate_email_html(opportunities, search_summary)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)

        logger.info(f"Reporte enviado con éxito a {recipient}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar correo por SMTP: {e}")
        return False
