"""
Panel Visual Interactivo (Streamlit) para el Buscador de Propiedades en Mendoza.
Permite visualizar oportunidades, ver el scoring, filtrar interactivamente y descargar en Excel.
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
st.caption("Detección inteligente de oportunidades en Capital, Godoy Cruz, Guaymallén y Las Heras.")

base_dir = Path(__file__).parent
data_file = base_dir / "data" / "latest_run.json"
excel_file = base_dir / "data" / "oportunidades_mendoza.xlsx"
config_file = base_dir / "config.yaml"

# Sidebar: Configuración y Filtros
st.sidebar.header("⚙️ Criterios y Filtros")

if config_file.exists():
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    budget = config.get("search", {}).get("budget", {}).get("total_available_usd", 120000)
    st.sidebar.metric("Presupuesto Objetivo", f"USD {budget:,.0f}", help="Propiedades hasta 132k se analizan para contraoferta")

# Botón para descargar el Excel directamente desde la web
if excel_file.exists():
    with open(excel_file, "rb") as f:
        st.sidebar.download_button(
            label="📥 Descargar Planilla Excel (.xlsx)",
            data=f.read(),
            file_name="oportunidades_mendoza.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# Cargar datos
if not data_file.exists():
    st.warning("Aún no se ha realizado ninguna búsqueda.")
    if st.button("🚀 Ejecutar Primera Búsqueda"):
        with st.spinner("Rastreando y analizando propiedades en Mendoza..."):
            from main import run_pipeline
            run_pipeline()
            st.rerun()
else:
    with open(data_file, "r", encoding="utf-8") as f:
        properties = json.load(f)

    # Botón para refrescar búsqueda
    col_btn1, col_info_stats = st.columns([3, 7])
    with col_btn1:
        if st.button("🔄 Rastrear Nuevas Oportunidades"):
            with st.spinner("Rastreando portales de Mendoza..."):
                from main import run_pipeline
                run_pipeline()
                st.rerun()

    # Filtros en la barra lateral
    st.sidebar.subheader("Filtros Dinámicos")
    score_filter = st.sidebar.slider("Score mínimo de Oportunidad", min_value=50, max_value=100, value=75)
    
    # Filtro de Zonas
    available_zones = sorted(list({p.get("location_zone", "") for p in properties if p.get("location_zone")}))
    selected_zones = st.sidebar.multiselect("Zonas", available_zones, default=available_zones)

    # Filtro de Tipo de Propiedad
    available_types = sorted(list({p.get("property_type", "").title() for p in properties if p.get("property_type")}))
    selected_types = st.sidebar.multiselect("Tipo de Propiedad", available_types, default=available_types)

    # Filtro de Precio Máximo
    max_price_filter = st.sidebar.slider("Precio Máximo (USD)", min_value=30000, max_value=135000, value=132000, step=5000)

    # Filtros de Categoría C
    st.sidebar.markdown("**Características Deseables:**")
    gas_filter = st.sidebar.checkbox("🔥 Solo con Red de Gas confirmada", value=False)
    parking_filter = st.sidebar.checkbox("🚗 Solo con Cochera", value=False)
    bath_filter = st.sidebar.checkbox("🚿 Solo con 2 o más Baños", value=False)
    security_filter = st.sidebar.checkbox("🛡️ Solo con Seguridad / Barrio Privado", value=False)

    # Aplicar filtros
    filtered = []
    for p in properties:
        score = p.get("analysis", {}).get("opportunity_score", 0)
        ptype = p.get("property_type", "").title()
        pzone = p.get("location_zone", "")
        price = p.get("price_usd", 0)
        cat_c = p.get("analysis", {}).get("category_c", {})

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
        if bath_filter and not cat_c.get("two_bathrooms"):
            continue
        if security_filter and not cat_c.get("has_security"):
            continue

        filtered.append(p)

    with col_info_stats:
        st.info(f"Mostrando **{len(filtered)}** oportunidades destacadas de un total de **{len(properties)}** analizadas.")

    # Renderizar tarjetas
    for p in filtered:
        analysis = p.get("analysis", {})
        score = analysis.get("opportunity_score", 0)
        cat_c = analysis.get("category_c", {})
        nego = analysis.get("negotiation_analysis", {})
        price = p.get("price_usd", 0)
        m2 = p.get("surface_m2")
        m2_str = f"{m2:.0f} m²" if m2 else "A consultar"

        # Color del badge de score
        if score >= 88:
            score_color = "green"
            score_label = "Oportunidad Destacada"
        elif score >= 75:
            score_color = "blue"
            score_label = "Muy Buena Opción"
        else:
            score_color = "orange"
            score_label = "Aceptable"

        with st.container(border=True):
            col_img, col_info, col_score = st.columns([3, 6, 3])

            with col_img:
                img = p.get("image_url")
                if img and ("http" in img or "uploads" in img):
                    st.image(img, use_container_width=True)
                else:
                    st.markdown("🖼️ *Foto disponible en la ficha*")

            with col_info:
                st.markdown(f"#### {p.get('title')}")
                st.markdown(f"📍 **{p.get('location_zone')}** • 🏠 **{p.get('property_type').title()}** • 📐 **{m2_str}**")

                # Badges de Categoría C
                badges = []
                if cat_c.get("has_gas_network"):
                    badges.append("🔥 Red de Gas")
                if cat_c.get("has_parking"):
                    badges.append("🚗 Cochera")
                if cat_c.get("two_bathrooms"):
                    badges.append("🚿 2 Baños")
                if cat_c.get("has_security"):
                    badges.append("🛡️ Seguridad/Barrio Privado")
                if cat_c.get("is_top_floor"):
                    badges.append("🏢 Último Piso")

                if badges:
                    st.markdown(" ".join([f"`{b}`" for b in badges]))

                # Pros y Contras
                pros = analysis.get("pros", [])
                if pros:
                    st.markdown("**A favor:** " + " • ".join([f"*{pr}*" for pr in pros[:3]]))

                cons = analysis.get("cons", [])
                if cons:
                    st.markdown("**Atención:** " + " • ".join([f"*{co}*" for co in cons[:2]]))

                if nego.get("summary"):
                    st.caption(f"💡 **Negociación:** {nego.get('summary')}")

            with col_score:
                st.markdown(f"### USD {price:,.0f}")
                st.markdown(f":{score_color}[**Score: {score}/100**] ({score_label})")
                if p.get("url"):
                    st.link_button(f"Abrir en {p.get('portal')} ↗", p.get("url"), use_container_width=True)
