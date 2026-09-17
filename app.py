import pandas as pd
import plotly.express as px
import streamlit as st

import config

st.set_page_config(
    page_title="E-commerce & Logistics Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fira+Sans:wght@300;400;500;600;700&family=Fira+Code:wght@400;500;600;700&display=swap');

    html, body, .stApp {
        font-family: 'Fira Sans', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Fira Code', monospace;
    }
    .main {
        background: linear-gradient(135deg, #0f172a 0%, #111827 35%, #1e293b 100%);
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.9);
    }
    .stMetric > div {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(148,163,184,0.2);
        border-radius: 14px;
        padding: 0.8rem;
        transition: border-color 200ms ease, box-shadow 200ms ease;
    }
    .stMetric > div:hover {
        border-color: rgba(59,130,246,0.6);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    button, a {
        cursor: pointer;
    }
    @media (prefers-reduced-motion: reduce) {
        * {
            transition: none !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

COLUMNAS_FILTRO = ["turno", "estado_despacho", "categoria"]


@st.cache_data(show_spinner=False)
def load_data():
    df = pd.read_csv(config.POWER_BI_FILE)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    for columna, reemplazo in (
        ("turno", "Sin turno"),
        ("estado_despacho", "Sin estado"),
        ("categoria", "Sin categoría"),
        ("producto", "Sin producto"),
    ):
        if columna in df.columns:
            df[columna] = df[columna].fillna(reemplazo)
    return df


def _estilizar_figura(fig, **kwargs):
    estilos = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": "#E2E8F0"},
        "margin": dict(l=10, r=10, t=20, b=10),
    }
    estilos.update(kwargs)
    fig.update_layout(**estilos)
    return fig


df = load_data()

columnas_faltantes = [c for c in COLUMNAS_FILTRO + ["ingreso_total"] if c not in df.columns]
if columnas_faltantes:
    st.error(f"Faltan columnas requeridas en {config.POWER_BI_FILE.name}: {', '.join(columnas_faltantes)}")
    st.stop()

st.sidebar.header("Panel de control")
st.sidebar.caption("Filtrá la operación para analizar el rendimiento")

turnos = sorted(df["turno"].dropna().unique().tolist())
estados = sorted(df["estado_despacho"].dropna().unique().tolist())
categorias = sorted(df["categoria"].dropna().unique().tolist())

turno_seleccionado = st.sidebar.multiselect("Turno", turnos, default=turnos)
estado_seleccionado = st.sidebar.multiselect("Estado de despacho", estados, default=estados)
categoria_seleccionada = st.sidebar.multiselect("Categoría", categorias, default=categorias)

mask = (
    df["turno"].isin(turno_seleccionado)
    & df["estado_despacho"].isin(estado_seleccionado)
    & df["categoria"].isin(categoria_seleccionada)
)
df_filtrado = df[mask].copy()

st.title("E-commerce Analytics & Logistics Dashboard")
st.caption("Monitoreo de ingresos, logística y desempeño operativo")

if df_filtrado.empty:
    st.warning("No hay datos para los filtros seleccionados. Ajustá los filtros del panel lateral.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
with col1:
    ingreso_total = float(df_filtrado["ingreso_total"].sum())
    st.metric("Ingresos totales", f"${ingreso_total:,.2f}")

with col2:
    volumen_tickets = len(df_filtrado)
    st.metric("Tickets", f"{volumen_tickets:,}")

with col3:
    ticket_promedio = float(df_filtrado["ingreso_total"].mean())
    st.metric("Ticket promedio", f"${ticket_promedio:,.2f}")

with col4:
    if "tiempo_preparacion_min" in df_filtrado.columns:
        tiempo_promedio = float(df_filtrado["tiempo_preparacion_min"].mean(skipna=True))
    else:
        tiempo_promedio = 0.0
    st.metric("Tiempo promedio", f"{tiempo_promedio:.1f} min")

st.markdown("---")

col_izq, col_der = st.columns(2)

with col_izq:
    st.header("Ingresos por categoría")
    df_cat = (
        df_filtrado.groupby("categoria", dropna=False)["ingreso_total"]
        .sum()
        .reset_index()
        .sort_values("ingreso_total", ascending=False)
    )
    fig_barras = _estilizar_figura(
        px.bar(
            df_cat,
            x="ingreso_total",
            y="categoria",
            orientation="h",
            color="ingreso_total",
            color_continuous_scale="Viridis",
            labels={"categoria": "Categoría", "ingreso_total": "Ingresos (USD)"},
        )
    )
    st.plotly_chart(fig_barras, width="stretch")

with col_der:
    st.header("Estado de despachos")
    df_estado = df_filtrado.groupby("estado_despacho", dropna=False).size().reset_index(name="cantidad")
    fig_donut = _estilizar_figura(
        px.pie(
            df_estado,
            names="estado_despacho",
            values="cantidad",
            hole=0.45,
            color_discrete_map=config.ESTADO_COLORS,
        ),
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig_donut, width="stretch")

st.markdown("---")

col_a, col_b = st.columns(2)

with col_a:
    st.header("Tendencia mensual de ingresos")
    if "fecha" in df_filtrado.columns:
        df_con_fecha = df_filtrado.dropna(subset=["fecha"])
        df_mensual = (
            df_con_fecha.assign(mes=df_con_fecha["fecha"].dt.to_period("M").astype(str))
            .groupby("mes", as_index=False)["ingreso_total"]
            .sum()
        )
        fig_line = _estilizar_figura(
            px.line(
                df_mensual,
                x="mes",
                y="ingreso_total",
                markers=True,
                line_shape="spline",
                color_discrete_sequence=[config.COLOR_SECONDARY],
            )
        )
        st.plotly_chart(fig_line, width="stretch")

with col_b:
    st.header("Top 5 productos por ingreso")
    df_top = (
        df_filtrado.groupby("producto", dropna=False)["ingreso_total"]
        .sum()
        .reset_index()
        .sort_values("ingreso_total", ascending=False)
        .head(5)
    )
    fig_top = _estilizar_figura(
        px.bar(
            df_top,
            x="producto",
            y="ingreso_total",
            color="ingreso_total",
            color_continuous_scale="Cividis",
        ),
        xaxis_tickangle=-25,
    )
    st.plotly_chart(fig_top, width="stretch")

st.markdown("---")
with st.expander("Vista de datos filtrados"):
    st.dataframe(df_filtrado.head(20), width="stretch")
    csv_filtrado = df_filtrado.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Descargar datos filtrados (CSV)",
        data=csv_filtrado,
        file_name="datos_filtrados.csv",
        mime="text/csv",
    )
