import logging
import random
import sqlite3
from contextlib import closing
from datetime import datetime

import pandas as pd

import config

# 1. CONFIGURACIÓN DEL LOG (Para registrar qué pasa cuando corre el script)
# encoding='utf-8' evita que las tildes/ñ queden corruptas (mojibake) al leer
# el log en sistemas donde el encoding por defecto no es UTF-8 (Linux/CI).
logging.basicConfig(
    filename=config.PIPELINE_LOG,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)


def generate_sample_data():
    """Genera datos de ejemplo cuando no existen los CSV del proyecto."""
    random.seed(42)
    productos = pd.DataFrame({
        'id_producto': [1, 2, 3, 4, 5],
        'nombre': [
            'Procesador AMD Ryzen 7 7800X3D',
            'Gabinete Mid-Tower Blanco',
            'Teclado Mecánico IROK Mercury68',
            'Monitor 240Hz 24"',
            'Memoria RAM 32GB DDR5 6000MHz'
        ],
        'categoria': ['Componentes', 'Gabinetes', 'Periféricos', 'Monitores', 'Componentes'],
        'precio_unitario': [450.0, 90.0, 110.0, 280.0, 120.0]
    })

    ventas = pd.DataFrame({
        'id_venta': list(range(1000, 1100)),
        'fecha': [datetime(2025, 1, 1) + pd.Timedelta(days=random.randint(0, 120), hours=random.randint(0, 23)) for _ in range(100)],
        'id_cliente': [random.randint(100, 149) for _ in range(100)],
        'id_producto': [random.choice(productos['id_producto']) for _ in range(100)],
        'cantidad': [random.choice([1, 2, 3]) for _ in range(100)],
        'metodo_pago': [random.choice(['Tarjeta', 'Transferencia', 'Crypto', 'No Especificado']) for _ in range(100)]
    })

    ventas['fecha'] = ventas['fecha'].dt.strftime('%Y-%m-%d %H:%M:%S')
    return ventas, productos


def extract_data(ventas_path=None, productos_path=None):
    """Fase 1: Extracción de datos crudos (simula lectura de APIs o carpetas compartidas).

    Si los CSV del proyecto no existen, genera datos de ejemplo y devuelve
    es_muestra=True. El orquestador usa esa bandera para NO persistir datos
    fabricados en la base de producción (fail-fast).
    """
    ventas_path = ventas_path or config.VENTAS_CSV
    productos_path = productos_path or config.PRODUCTOS_CSV
    logging.info("Iniciando Fase de Extracción...")
    try:
        if ventas_path.exists() and productos_path.exists():
            df_ventas_nuevas = pd.read_csv(ventas_path)
            df_productos = pd.read_csv(productos_path)
            logging.info("Se cargaron los archivos CSV del proyecto.")
            return df_ventas_nuevas, df_productos, False

        logging.warning("No se encontraron los CSV del proyecto. Se generarán datos de ejemplo (no se persistirán en la base).")
        ventas_muestra, productos_muestra = generate_sample_data()
        return ventas_muestra, productos_muestra, True
    except Exception:
        logging.exception("Error en extracción")
        raise


def transform_data(df_ventas, df_productos):
    """Fase 2: Limpieza y Transformación (Data Cleaning)."""
    logging.info("Iniciando Fase de Transformación...")
    try:
        # Eliminamos duplicados
        df_ventas = df_ventas.drop_duplicates()

        # Filtramos cantidades inválidas
        df_ventas = df_ventas[df_ventas['cantidad'] > 0]

        # Rellenamos nulos
        df_ventas['metodo_pago'] = df_ventas['metodo_pago'].fillna('No Especificado')
        df_productos['precio_unitario'] = df_productos['precio_unitario'].fillna(0)  # Evitamos nulls en precios

        # Cruzamos las tablas (MERGE)
        df_limpio = df_ventas.merge(df_productos, on='id_producto', how='inner')
        df_limpio['ingreso_total'] = df_limpio['cantidad'] * df_limpio['precio_unitario']

        # Agregamos la fecha de procesamiento (marca de agua del pipeline)
        df_limpio['fecha_procesamiento_etl'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return df_limpio
    except Exception:
        logging.exception("Error en transformación")
        raise


def load_data(df_limpio, db_name=str(config.DB_PATH)):
    """Fase 3: Carga en Base de Datos SQL (idempotente)

    Antes de insertar, chequea qué id_venta ya están cargados y descarta esos
    registros. Así, si el pipeline se corre varias veces sobre el mismo
    origen de datos (por ejemplo un cron diario que reprocesa por error),
    no duplica filas en 'ventas_diarias_automatizadas'.
    """
    logging.info("Iniciando Fase de Carga a SQL...")
    try:
        with closing(sqlite3.connect(db_name)) as conn:
            tabla_existe = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ventas_diarias_automatizadas'"
            ).fetchone()

            if tabla_existe:
                ids_existentes = pd.read_sql_query(
                    "SELECT DISTINCT id_venta FROM ventas_diarias_automatizadas", conn
                )['id_venta']
                antes = len(df_limpio)
                df_limpio = df_limpio[~df_limpio['id_venta'].isin(ids_existentes)]
                omitidos = antes - len(df_limpio)
                if omitidos:
                    logging.info(f"Se omitieron {omitidos} registros ya cargados previamente (id_venta duplicado).")

            if df_limpio.empty:
                logging.info("No hay registros nuevos para cargar.")
                return

            df_limpio.to_sql('ventas_diarias_automatizadas', conn, if_exists='append', index=False)
            conn.commit()
            logging.info(f"Carga exitosa: {len(df_limpio)} registros insertados.")
    except Exception:
        logging.exception("Error en carga SQL")
        raise


def run_pipeline(db_name=None):
    """Función orquestadora principal."""
    print("Iniciando ETL Pipeline...")
    logging.info("--- NUEVO CICLO DE ETL INICIADO ---")
    try:
        # Ejecutamos el ETL
        ventas_crudo, productos_crudo, es_muestra = extract_data()
        datos_transformados = transform_data(ventas_crudo, productos_crudo)

        if es_muestra:
            logging.warning("Modo muestra: los datos de ejemplo NO se persisten en la base.")
            print("No se encontraron ventas.csv/productos.csv. Se usó data de ejemplo y NO se cargó en la base.")
            return

        load_data(datos_transformados, db_name=db_name or str(config.DB_PATH))

        logging.info("--- CICLO ETL FINALIZADO CON ÉXITO ---")
        print("Pipeline ejecutado correctamente. Revisá el archivo pipeline_ejecucion.log")

    except Exception:
        logging.critical("EL PIPELINE ABORTÓ DEBIDO A UN ERROR CRÍTICO.", exc_info=True)
        print("El Pipeline falló. Revisá el Log para más detalles.")


# Bloque de ejecución principal
if __name__ == "__main__":
    run_pipeline()
