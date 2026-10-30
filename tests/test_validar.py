"""Pruebas del validador y del escritor (ya implementados)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from med_nube import contrato as C
from med_nube.escribir import escribir_entrega
from med_nube.validar import validar
from tests import sinteticos as S

FECHA = datetime(2026, 11, 3, 14, 5, tzinfo=timezone(timedelta(hours=-5)))
COMMIT = "abcdef1"


def _alturas():
    return pd.DataFrame(
        [
            {
                "id_parte": "t:plana",
                "bloque": "A_9377",
                "n_puntos": 5000,
                "cobertura": 0.99,
                "z_p10": 1508.97,
                "z_p50": 1509.0,
                "z_p90": 1509.03,
                "z_p98": 1509.04,
                "z_max": 1509.08,
                "n_puntos_suelo": 900,
                "z_suelo": 1499.99,
                "h_p50": 9.01,
                "h_p98": 9.05,
            },
            {
                "id_parte": "t:torre",
                "bloque": "A_9377",
                "n_puntos": 30,
                "cobertura": 0.4,
                "z_p10": 1529.9,
                "z_p50": 1530.0,
                "z_p90": 1530.1,
                "z_p98": 1530.1,
                "z_max": 1530.2,
                "n_puntos_suelo": 0,
                "z_suelo": None,
                "h_p50": None,
                "h_p98": None,
            },
        ]
    )


def _techos():
    return pd.DataFrame(
        [
            {
                "id_parte": "t:plana",
                "forma": "plano",
                "n_planos": 1,
                "pendiente_deg": 0.3,
                "azimut_caida_deg": None,
                "azimut_cumbrera_deg": None,
                "frac_inliers": 0.99,
                "rmse_m": 0.02,
            }
        ]
    )


@pytest.fixture
def escenario(tmp_path):
    huellas, _ = S.construir(tmp_path)
    return tmp_path, huellas


def _escribir(carpeta, huellas, alturas=None, techos=None, **kw):
    args = {
        "bloques": ["A_9377"],
        "bloques_omitidos": {"C_sin_crs": "sin CRS"},
        "bloques_advertencias": {},
    } | kw
    return escribir_entrega(
        _alturas() if alturas is None else alturas,
        _techos() if techos is None else techos,
        huellas,
        carpeta=carpeta / "salida",
        fecha=FECHA,
        commit=COMMIT,
        **args,
    )


def _sql(ruta, sentencia):
    con = sqlite3.connect(ruta)
    con.execute(sentencia)
    con.commit()
    con.close()


def test_entrega_valida(escenario):
    carpeta, huellas = escenario
    ruta = _escribir(carpeta, huellas)
    assert ruta.name == "med_nube_entrega_20261103.gpkg"
    r = validar(ruta, huellas, oficial=False)
    assert r.ok, r.errores
    assert r.resumen["partes_alturas"] == 2
    assert any("Coltejer" in a for a in r.advertencias)


def test_oficial_exige_huellas_oficiales(escenario):
    carpeta, huellas = escenario
    r = validar(_escribir(carpeta, huellas), huellas, oficial=True)
    assert any("oficial" in e for e in r.errores)


def test_escritor_rechaza_columnas_extra(escenario):
    carpeta, huellas = escenario
    with pytest.raises(ValueError, match="sobran"):
        _escribir(carpeta, huellas, alturas=_alturas().assign(extra=1))


@pytest.mark.parametrize(
    ("sentencia", "fragmento"),
    [
        ("UPDATE alturas SET z_p50 = 1600 WHERE id_parte = 't:plana'", "percentiles"),
        ("UPDATE alturas SET h_p98 = 3 WHERE id_parte = 't:plana'", "h_p50/h_p98"),
        ("UPDATE alturas SET id_parte = 'x:no' WHERE id_parte = 't:plana'", "no existe"),
        ("UPDATE alturas SET n_puntos = 5 WHERE id_parte = 't:plana'", "n_puntos"),
        ("UPDATE alturas SET bloque = 'Z' WHERE id_parte = 't:plana'", "bloque"),
        ("UPDATE techos SET forma = 'cupula'", "forma no permitida"),
        ("UPDATE techos SET azimut_cumbrera_deg = 10", "azimut_cumbrera"),
        ("UPDATE techos SET pendiente_deg = 20", "plano exige"),
        ("DELETE FROM techos", "faltan en techos"),
        ("UPDATE metadatos SET valor = '0.9' WHERE clave = 'version_contrato'", "version"),
        ("UPDATE metadatos SET valor = 'abc' WHERE clave = 'huellas_sha256'", "huellas_sha256"),
        ("ALTER TABLE alturas ADD COLUMN extra REAL", "columnas"),
    ],
)
def test_detecta_errores(escenario, sentencia, fragmento):
    carpeta, huellas = escenario
    ruta = _escribir(carpeta, huellas)
    _sql(ruta, sentencia)
    r = validar(ruta, huellas, oficial=False)
    assert not r.ok
    assert any(fragmento in e for e in r.errores), r.errores


def test_coltejer_fuera_de_rango(escenario):
    carpeta, huellas = escenario
    ruta = _escribir(carpeta, huellas)
    _sql(ruta, f"UPDATE alturas SET id_parte = '{C.COLTEJER_ID}' WHERE id_parte = 't:plana'")
    r = validar(ruta, huellas, oficial=False)
    # (el id no existe en las huellas sintéticas: eso es error aparte; aquí solo
    # se comprueba que el rango del Coltejer es advertencia y no error)
    assert not any("Coltejer" in e for e in r.errores)
    assert any(a.startswith("REVISAR") and "Coltejer" in a for a in r.advertencias)


def test_nombre_invalido(escenario):
    carpeta, huellas = escenario
    ruta = _escribir(carpeta, huellas)
    otra = ruta.with_name("entrega.gpkg")
    ruta.rename(otra)
    assert any("Nombre" in e for e in validar(otra, huellas, oficial=False).errores)
