import importlib.util
import sqlite3
from pathlib import Path

import pandas as pd


def load_module():
    module_path = Path(__file__).with_name('03_etl_pipeline.py')
    spec = importlib.util.spec_from_file_location('etl_pipeline', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_data_generates_fallback_when_csvs_are_missing(tmp_path):
    module = load_module()

    ventas, productos, es_muestra = module.extract_data(
        ventas_path=tmp_path / 'ventas.csv',
        productos_path=tmp_path / 'productos.csv',
    )

    assert es_muestra is True
    assert not ventas.empty
    assert not productos.empty
    assert {'id_producto', 'cantidad', 'metodo_pago'}.issubset(ventas.columns)
    assert {'id_producto', 'precio_unitario'}.issubset(productos.columns)
    assert (ventas['cantidad'] > 0).all()


def test_extract_data_loads_real_csvs(tmp_path):
    module = load_module()
    ventas_path = tmp_path / 'ventas.csv'
    productos_path = tmp_path / 'productos.csv'
    pd.DataFrame({'id_venta': [1], 'id_producto': [1], 'cantidad': [2], 'metodo_pago': ['Tarjeta']}).to_csv(
        ventas_path, index=False
    )
    pd.DataFrame({'id_producto': [1], 'precio_unitario': [10.0]}).to_csv(productos_path, index=False)

    ventas, productos, es_muestra = module.extract_data(ventas_path=ventas_path, productos_path=productos_path)

    assert es_muestra is False
    assert len(ventas) == 1
    assert len(productos) == 1


def test_transform_data_computes_ingreso_total():
    module = load_module()
    ventas = pd.DataFrame({'id_venta': [1], 'id_producto': [1], 'cantidad': [3], 'metodo_pago': [None]})
    productos = pd.DataFrame({'id_producto': [1], 'precio_unitario': [50.0]})

    resultado = module.transform_data(ventas, productos)

    assert resultado['ingreso_total'].iloc[0] == 150.0
    assert 'fecha_procesamiento_etl' in resultado.columns


def test_load_data_is_idempotent(tmp_path):
    module = load_module()
    db_path = tmp_path / 'idempotencia.db'
    df = pd.DataFrame({'id_venta': [1, 2, 3], 'monto': [10.0, 20.0, 30.0]})

    module.load_data(df, db_name=str(db_path))
    module.load_data(df, db_name=str(db_path))

    with sqlite3.connect(db_path) as conn:
        total = conn.execute('SELECT COUNT(*) FROM ventas_diarias_automatizadas').fetchone()[0]
    assert total == 3


def test_run_pipeline_in_sample_mode_does_not_persist(monkeypatch, tmp_path):
    module = load_module()
    monkeypatch.setattr(module.config, 'VENTAS_CSV', tmp_path / 'ventas.csv')
    monkeypatch.setattr(module.config, 'PRODUCTOS_CSV', tmp_path / 'productos.csv')
    db_path = tmp_path / 'muestra.db'

    module.run_pipeline(db_name=str(db_path))

    with sqlite3.connect(db_path) as conn:
        tablas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ventas_diarias_automatizadas'"
        ).fetchall()
    assert tablas == []
