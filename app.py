"""
Panel Visual Interactivo (Streamlit) - Radar Inmobiliario Mendoza
- Filtros dinámicos por zona, tipo, precio y características
- Botón de descarga Excel
- Botón "No me interesa" para descartar publicaciones permanentemente
- Botón "Actualizar Búsqueda" que relanza el scraper en tiempo real
"""

import json
from pathlib import Path
import streamlit as st
import yaml

st.set_page_config(
    page_title="Radar Inmobiliario Mendoza",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏡 Radar Inmobiliario Mendoza")
st.caption("Detección inteligente de oportunidades en Capital, Godoy Cruz y Barrio Dorrego (Guaymallén).")

base_dir = Path(__file__).parent
data_file = base_dir / "data" / "latest_run.json"
excel_file = base_dir / "data" / "oportunidades_mendoza.xlsx"
config_file = base_dir / "config.yaml"
dismissed_file = base_dir / "data" / "dismissed.json"


def load_dismissed() -> set:
    """Carga el conjunto de IDs de propiedades descartadas por el usuario."""
    if dismissed_file.exists():
        with open(dismissed_file, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_dismissed(dismissed: set):
    """Guarda el conjunto de IDs descartados."""
    dismissed_file.parent.mkdir(exist_ok=True)
    with open(dismissed_file, "w", encoding="utf-8") as f:
        json.dump(list(dismissed), f)


# Inicializar sesión de descartados
if "dismissed" not in st.session_state:
    st.session_state.dismissed = load_dismissed()

# Sidebar
st.sidebar.header("⚙️ Búsqueda y Filtros")

if config_file.exists():
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    budget = config.get("search", {}).get("budget", {}).get("total_available_usd", 140000)
    st.sidebar.metric("Presupuesto Objetivo", f"USD {budget:,.0f}")
    st.sidebar.caption("Tope evaluable (margen 8,5%): USD 152.000")

# Botón de actualización
if st.sidebar.button("🔄 Actualizar Búsqueda", help="Relanza el scraper y analiza nuevas publicaciones", use_container_width=True):
    with st.spinner("Rastreando portales de Mendoza... (aprox. 1-2 minutos)"):
        try:
            from main import run_pipeline
            run_pipeline()
            st.success("¡Búsqueda actualizada con éxito!")
            st.rerun()
        except Exception as e:
            st.error(f"Error al actualizar: {e}")

# Botón de descarga Excel
if excel_file.exists():
    with open(excel_file, "rb") as f:
        st.sidebar.download_button(
            label="📥 Descargar Excel (.xlsx)",
            data=f.read(),
            file_name="oportunidades_mendoza.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# Mostrar / ocultar descartados
show_dismissed = st.sidebar.checkbox("🗑️ Mostrar descartadas", value=False)
if st.sidebar.button("↩️ Restaurar todas las descartadas", use_container_width=True):
    st.session_state.dismissed = set()
    save_dismissed(st.session_state.dismissed)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Filtros")

# Cargar datos
if not data_file.exists():
    st.warning("Aún no se ha realizado ninguna búsqueda.")
    if st.button("🚀 Ejecutar Primera Búsqueda"):
        with st.spinner("Rastreando portales de Mendoza..."):
            from main import run_pipeline
            run_pipeline()
            st.rerun()
    st.stop()

with open(data_file, "r", encoding="utf-8") as f:
    properties = json.load(f)

# Filtros dinámicos
score_filter = st.sidebar.slider("Score mínimo", min_value=30, max_value=100, value=65)
available_zones = sorted({p.get("location_zone", "") for p in properties if p.get("location_zone")})
selected_zones = st.sidebar.multiselect("Zonas", available_zones, default=available_zones)
available_types = sorted({p.get("property_type", "").title() for p in properties if p.get("property_type")})
selected_types = st.sidebar.multiselect("Tipo", available_types, default=available_types)
max_price_filter = st.sidebar.slider("Precio máximo (USD)", min_value=50000, max_value=155000, value=152000, step=5000)

st.sidebar.markdown("**Características:**")
gas_filter = st.sidebar.checkbox("🔥 Solo con Red de Gas", value=False)
parking_filter = st.sidebar.checkbox("🚗 Solo con Cochera", value=False)
security_filter = st.sidebar.checkbox("🛡️ Solo con Seguridad 24hs", value=False)
elevator_filter = st.sidebar.checkbox("🛗 Solo con Ascensor", value=False)

# Aplicar filtros
filtered = []
for p in properties:
    pid = p.get("id", "")
    score = p.get("analysis", {}).get("opportunity_score", 0)
    ptype = p.get("property_type", "").title()
    pzone = p.get("location_zone", "")
    price = p.get("price_usd", 0)
    cat_c = p.get("analysis", {}).get("category_c", {})

    is_dismissed = pid in st.session_state.dismissed

    # Ocultar descartadas (a menos que se pida mostrarlas)
    if is_dismissed and not show_dismissed:
        continue

    if score < score_filter:
        continue
    if ptype not in selected_types:
        continue
    if pzone not in selected_zones:
        continue
    if price > max_price_filter:
        continue
    if gas_filter and not cat_c.get("has_gas_network"):
        continue
    if parking_filter and not cat_c.get("has_parking"):
        continue
    if security_filter and not cat_c.get("has_security"):
        continue
    if elevator_filter and not cat_c.get("has_elevator"):
        continue

    filtered.append(p)

dismissed_count = len(st.session_state.dismissed)
st.info(
    f"Mostrando **{len(filtered)}** oportunidades de **{len(properties)}** analizadas "
    f"{'(incluye descartadas)' if show_dismissed else f'— {dismissed_count} descartada(s) oculta(s)'}"
)

# Renderizar tarjetas
for p in filtered:
    pid = p.get("id", "")
    analysis = p.get("analysis", {})
    score = analysis.get("opportunity_score", 0)
    cat_c = analysis.get("category_c", {})
    nego = analysis.get("negotiation_analysis", {})
    price = p.get("price_usd", 0)
    m2 = p.get("surface_m2")
    m2_str = f"{m2:.0f} m²" if m2 else "A consultar"
    is_dismissed = pid in st.session_state.dismissed

    if score >= 85:
        score_color = "green"
        score_label = "Oportunidad Destacada"
    elif score >= 70:
        score_color = "blue"
        score_label = "Muy Buena Opción"
    else:
        score_color = "orange"
        score_label = "Aceptable"

    # Contenedor con borde gris si está descartada
    with st.container(border=True):
        if is_dismissed:
            st.warning("🗑️ *Publicación descartada por el usuario*")

        col_img, col_info, col_score = st.columns([3, 6, 3])

        with col_img:
            img = p.get("image_url")
            if img and "http" in img and "empty-photo" not in img:
                st.image(img, use_container_width=True)
            else:
                st.markdown("🖼️ *Foto disponible en la ficha*")

        with col_info:
            st.markdown(f"#### {p.get('title')}")
            st.markdown(f"📍 **{p.get('location_zone')}** • 🏠 **{p.get('property_type','').title()}** • 📐 **{m2_str}**")

            # Badges Categoría C
            badges = []
            if cat_c.get("has_security"):
                badges.append("🛡️ Seguridad 24hs")
            if cat_c.get("has_gas_network"):
                badges.append("🔥 Red de Gas")
            if cat_c.get("has_parking"):
                badges.append("🚗 Cochera")
            if cat_c.get("has_elevator"):
                badges.append("🛗 Ascensor")
            if cat_c.get("two_bathrooms"):
                badges.append("🚿 2 Baños")
            if not cat_c.get("has_security"):
                badges.append("⚠️ Sin seguridad 24hs")

            if badges:
                st.markdown(" ".join([f"`{b}`" for b in badges]))

            pros = analysis.get("pros", [])
            if pros:
                st.markdown("**A favor:** " + " • ".join([f"*{pr}*" for pr in pros[:3]]))

            cons = analysis.get("cons", [])
            if cons:
                st.markdown("**Atención:** " + " • ".join([f"*{co}*" for co in cons[:2]]))

            if nego.get("summary"):
                st.caption(f"💡 {nego.get('summary')}")

        with col_score:
            st.markdown(f"### USD {price:,.0f}")
            st.markdown(f":{score_color}[**{score}/100**]  \n{score_label}")
            if p.get("url"):
                st.link_button(f"Ver en {p.get('portal')} ↗", p.get("url"), use_container_width=True)

            # Botón de descarte / restaurar
            if not is_dismissed:
                if st.button("🗑️ No me interesa", key=f"dismiss_{pid}", use_container_width=True):
                    st.session_state.dismissed.add(pid)
                    save_dismissed(st.session_state.dismissed)
                    st.rerun()
            else:
                if st.button("↩️ Restaurar", key=f"restore_{pid}", use_container_width=True):
                    st.session_state.dismissed.discard(pid)
                    save_dismissed(st.session_state.dismissed)
                    st.rerun()
