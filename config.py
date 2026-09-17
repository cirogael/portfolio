from pathlib import Path

ROOT = Path(__file__).resolve().parent

DB_PATH = ROOT / "ecommerce_portfolio.db"
POWER_BI_FILE = ROOT / "dataset_power_bi.csv"
VENTAS_CSV = ROOT / "ventas.csv"
PRODUCTOS_CSV = ROOT / "productos.csv"
PIPELINE_LOG = ROOT / "pipeline_ejecucion.log"
ETL_PIPELINE = ROOT / "03_etl_pipeline.py"

DONUT_COLORS = ["#22c55e", "#f59e0b", "#ef4444", "#38bdf8", "#a78bfa"]
COLOR_SECONDARY = "#3B82F6"
COLOR_ACCENT = "#D97706"
COLOR_DESTRUCTIVE = "#DC2626"

ESTADO_COLORS = {
    "Completado a Tiempo": "#22C55E",
    "Con Demora": "#F59E0B",
    "Cancelado - Falta Stock": "#EF4444",
    "Pendiente de Revisión": "#3B82F6",
    "Sin estado": "#94A3B8",
}
