import random
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import config


def generate_project_data():
    # 1. Productos
    productos_data = {
        'id_producto': range(1, 9),
        'nombre': [
            '  Procesador AMD Ryzen 7 7800X3D  ',
            'Procesador AMD Ryzen 5 7600X',
            'Gabinete Mid-Tower Blanco (Sin RGB)',
            'teclado magnético irok mercury68',
            'Monitor 240Hz 1ms 24"',
            'Mouse Ultraligero 50g',
            'Auriculares In-Ear KZ EDX Pro',
            'Memoria RAM 32GB DDR5 6000MHz'
        ],
        'categoria': ['Componentes', 'Componentes', 'Gabinetes', 'Periféricos', 'Monitores', 'Periféricos', 'Audio', 'Componentes'],
        'precio_unitario': [450.0, 230.0, 90.0, 110.0, 280.0, 75.0, 20.0, 120.0]
    }
    df_productos = pd.DataFrame(productos_data)
    df_productos.loc[2, 'precio_unitario'] = np.nan

    # 2. Clientes
    df_clientes = pd.DataFrame({
        'id_cliente': range(100, 150),
        'perfil_comprador': np.random.choice(['Gamer', 'Workstation', 'Casual'], size=50)
    })

    # 3. Ventas (con duplicados simulados para que el pipeline los detecte)
    num_ventas = 3000
    df_ventas = pd.DataFrame({
        'id_venta': range(1000, 1000 + num_ventas),
        'fecha': [(datetime(2025, 1, 1) + timedelta(days=random.randint(0, 365), hours=random.randint(0, 23))).strftime('%Y-%m-%d %H:%M:%S') for _ in range(num_ventas)],
        'id_cliente': [random.choice(df_clientes['id_cliente']) for _ in range(num_ventas)],
        'id_producto': [random.choice(df_productos['id_producto']) for _ in range(num_ventas)],
        'cantidad': np.random.choice([1, 2, 3, -1, 0], p=[0.75, 0.15, 0.03, 0.05, 0.02], size=num_ventas),
        'metodo_pago': np.random.choice(['Tarjeta', 'Transferencia', 'Crypto', None], p=[0.5, 0.3, 0.15, 0.05], size=num_ventas)
    })
    df_ventas = pd.concat([df_ventas, df_ventas.sample(30, random_state=7)]).sample(frac=1, random_state=7).reset_index(drop=True)

    # 4. Limpieza
    df_productos['nombre'] = df_productos['nombre'].str.strip().str.title()
    df_productos['precio_unitario'] = df_productos['precio_unitario'].fillna(90.0)

    duplicados_removidos = len(df_ventas) - len(df_ventas.drop_duplicates())
    df_ventas = df_ventas.drop_duplicates()
    print(f'Duplicados detectados y removidos: {duplicados_removidos}')
    df_ventas = df_ventas[df_ventas['cantidad'] > 0]
    df_ventas['metodo_pago'] = df_ventas['metodo_pago'].fillna('No Especificado')
    df_ventas['fecha'] = pd.to_datetime(df_ventas['fecha'])

    df_master = df_ventas.merge(df_productos, on='id_producto', how='inner')
    df_master = df_master.merge(df_clientes, on='id_cliente', how='inner')
    df_master['ingreso_total'] = df_master['cantidad'] * df_master['precio_unitario']
    df_master['mes'] = df_master['fecha'].dt.month
    df_master['dia_semana'] = df_master['fecha'].dt.day_name()
    return df_master, df_productos, df_ventas


def generate_logistics(df_master):
    operarios_data = {
        'id_operario': ['OP-01', 'OP-02', 'OP-03', 'OP-04', 'OP-05'],
        'nombre': ['Marcos', 'Lucia', 'Diego', 'Ana', 'Carlos'],
        'turno': ['Mañana', 'Mañana', 'Tarde', 'Tarde', 'Noche']
    }
    df_operarios = pd.DataFrame(operarios_data)

    num_ventas = len(df_master)
    df_logistica = pd.DataFrame({
        'id_ticket': [f'TK-{i:05d}' for i in range(1, num_ventas + 1)],
        'id_venta': list(df_master['id_venta']),
        'id_operario': [random.choice(df_operarios['id_operario']) for _ in range(num_ventas)],
        'tiempo_preparacion_min': np.random.normal(loc=25.0, scale=8.0, size=num_ventas).round(1),
        'estado_despacho': np.random.choice(
            ['Completado a Tiempo', 'Con Demora', 'Cancelado - Falta Stock', None],
            p=[0.75, 0.15, 0.05, 0.05],
            size=num_ventas
        )
    })

    df_logistica.loc[random.sample(range(num_ventas), 20), 'tiempo_preparacion_min'] = -15.0
    df_logistica.loc[random.sample(range(num_ventas), 30), 'tiempo_preparacion_min'] = np.nan
    df_logistica = df_logistica.dropna(subset=['tiempo_preparacion_min'])
    df_logistica = df_logistica[df_logistica['tiempo_preparacion_min'] > 0]
    df_logistica['estado_despacho'] = df_logistica['estado_despacho'].fillna('Pendiente de Revisión')

    def calcular_sla(tiempo):
        if tiempo <= 30:
            return 'Verde (Óptimo)'
        elif tiempo <= 45:
            return 'Amarillo (Alerta)'
        return 'Rojo (Crítico)'

    df_ops_master = df_logistica.merge(df_operarios, on='id_operario', how='left')
    df_ops_master['kpi_semaforo_sla'] = df_ops_master['tiempo_preparacion_min'].apply(calcular_sla)
    return df_ops_master


def export_to_sql(df_master, df_ops_master):
    with closing(sqlite3.connect(config.DB_PATH)) as conn:
        df_master.to_sql('ventas_limpias', conn, if_exists='replace', index=False)
        df_ops_master.to_sql('logistica_operaciones', conn, if_exists='replace', index=False)
        conn.commit()
    print(f'Base SQL creada en: {config.DB_PATH}')


def export_power_bi_dataset():
    query = """
        SELECT
            v.id_venta,
            v.fecha,
            v.nombre AS producto,
            v.categoria,
            v.cantidad,
            v.ingreso_total,
            v.metodo_pago,
            l.id_operario,
            l.turno,
            l.tiempo_preparacion_min,
            l.estado_despacho
        FROM ventas_limpias v
        LEFT JOIN logistica_operaciones l ON v.id_venta = l.id_venta;
    """
    with closing(sqlite3.connect(config.DB_PATH)) as conn:
        df_export = pd.read_sql_query(query, conn)
    df_export.to_csv(config.POWER_BI_FILE, index=False, encoding='utf-8')
    print(f'Archivo Power BI exportado en: {config.POWER_BI_FILE}')


def export_raw_csvs_for_etl(df_ventas, df_productos):
    """Deja 'ventas.csv' y 'productos.csv' en disco para que 03_etl_pipeline.py
    tenga datos reales que extraer, en vez de caer siempre en su rama de
    datos de ejemplo (fallback). Simula el archivo que dejaría, por ejemplo,
    un sistema de ventas al final del día."""
    df_ventas.to_csv(config.VENTAS_CSV, index=False, encoding='utf-8')
    df_productos.to_csv(config.PRODUCTOS_CSV, index=False, encoding='utf-8')
    print(f'CSV de origen para el ETL generados: {config.VENTAS_CSV.name}, {config.PRODUCTOS_CSV.name}')


def run_etl_pipeline():
    subprocess.run([sys.executable, str(config.ETL_PIPELINE)], cwd=str(config.ROOT), check=True)
    print('ETL pipeline ejecutado correctamente.')


def main():
    print('Generando dataset principal...')
    random.seed(42)
    np.random.seed(42)
    df_master, df_productos, df_ventas = generate_project_data()
    df_ops_master = generate_logistics(df_master)
    export_to_sql(df_master, df_ops_master)
    export_power_bi_dataset()
    export_raw_csvs_for_etl(df_ventas, df_productos)
    run_etl_pipeline()
    print('Proyecto portfolio ejecutado correctamente.')


if __name__ == '__main__':
    main()
