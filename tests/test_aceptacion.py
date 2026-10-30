"""Pruebas de aceptación de procesar() sobre el escenario sintético.

Definen "terminado": cuando todas pasan (y la entrega real pasa el validador),
el trabajo está listo. NO MODIFICAR estas pruebas ni sinteticos.py.
"""

from __future__ import annotations

import json
import sqlite3

import numpy as np
import pytest

from med_nube.procesar import procesar
from med_nube.validar import validar
from tests import sinteticos as S

COMMIT = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture(scope="module")
def entrega(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("escenario")
    huellas, nubes = S.construir(carpeta)
    ruta = procesar(huellas, nubes, carpeta / "salida", commit=COMMIT)
    return ruta, huellas


def _tabla(ruta, nombre):
    con = sqlite3.connect(ruta)
    try:
        cur = con.execute(f"SELECT * FROM [{nombre}]")
        cols = [d[0] for d in cur.description]
        filas = [dict(zip(cols, f, strict=True)) for f in cur.fetchall()]
    finally:
        con.close()
    return filas


@pytest.fixture(scope="module")
def alturas(entrega):
    return {f["id_parte"]: f for f in _tabla(entrega[0], "alturas")}


@pytest.fixture(scope="module")
def techos(entrega):
    return {f["id_parte"]: f for f in _tabla(entrega[0], "techos")}


@pytest.fixture(scope="module")
def metadatos(entrega):
    return {f["clave"]: f["valor"] for f in _tabla(entrega[0], "metadatos")}


def test_pasa_el_validador(entrega):
    ruta, huellas = entrega
    r = validar(ruta, huellas, oficial=False)
    assert r.ok, r.errores


def test_nombre_del_archivo(entrega):
    assert entrega[0].name.startswith("med_nube_entrega_") and entrega[0].suffix == ".gpkg"


def test_bloques(metadatos):
    assert json.loads(metadatos["bloques"]) == ["A_9377", "B_utm"]
    assert list(json.loads(metadatos["bloques_omitidos"])) == ["C_sin_crs"]
    assert metadatos["commit"] == COMMIT


def test_partes_presentes(alturas):
    esperadas = {"t:plana", "t:dos_aguas", "t:podio", "t:torre", "t:arbol", "t:utm"}
    assert set(alturas) == esperadas  # sin_puntos y diminuta no aparecen


def test_techo_plano(alturas, techos):
    a = alturas["t:plana"]
    assert a["bloque"] == "A_9377"
    assert a["z_p50"] == pytest.approx(1509.0, abs=0.05)
    assert a["z_max"] < 1509.2  # el ruido clase 7 (z = 1600) se descarta
    assert a["z_suelo"] == pytest.approx(1500.0, abs=0.05)
    assert a["h_p98"] == pytest.approx(9.0, abs=0.15)
    assert a["cobertura"] >= 0.95
    t = techos["t:plana"]
    assert t["forma"] == "plano" and t["pendiente_deg"] < 2.0
    assert t["azimut_caida_deg"] is None and t["azimut_cumbrera_deg"] is None


def test_dos_aguas(alturas, techos):
    a = alturas["t:dos_aguas"]
    assert 8.5 <= a["h_p98"] <= 9.6
    t = techos["t:dos_aguas"]
    assert t["forma"] == "dos_aguas" and t["n_planos"] == 2
    assert t["pendiente_deg"] == pytest.approx(30.0, abs=2.0)
    caida = t["azimut_caida_deg"]
    assert min(abs(caida - 90.0), abs(caida - 270.0)) <= 3.0
    cumbrera = t["azimut_cumbrera_deg"]
    assert min(cumbrera, 180.0 - cumbrera) <= 3.0  # cumbrera N–S
    assert t["frac_inliers"] >= 0.9


def test_podio_excluye_la_torre(alturas):
    assert alturas["t:podio"]["z_p98"] <= 1503.2
    assert alturas["t:torre"]["z_p50"] == pytest.approx(1530.0, abs=0.05)


def test_torre_sin_anillo_de_suelo(alturas):
    # el anillo de la torre cae dentro del podio: no hay puntos de suelo
    t = alturas["t:torre"]
    assert t["n_puntos_suelo"] < 10
    assert t["z_suelo"] is None and t["h_p98"] is None


def test_vegetacion_filtrada(alturas, techos):
    a = alturas["t:arbol"]
    assert a["z_p98"] <= 1506.2  # la copa verde (1510–1514) no cuenta
    assert 0.6 <= a["cobertura"] <= 0.8
    assert techos["t:arbol"]["forma"] == "plano"


def test_bloque_utm(alturas):
    a = alturas["t:utm"]
    assert a["bloque"] == "B_utm"
    assert a["z_p50"] == pytest.approx(1504.0, abs=0.05)
    assert a["h_p98"] == pytest.approx(4.0, abs=0.15)


def test_determinista(tmp_path, entrega):
    huellas, nubes = S.construir(tmp_path)
    otra = procesar(huellas, nubes, tmp_path / "salida", commit=COMMIT)
    for tabla in ("alturas", "techos"):
        a = sorted(_tabla(entrega[0], tabla), key=lambda f: f["id_parte"])
        b = sorted(_tabla(otra, tabla), key=lambda f: f["id_parte"])
        assert len(a) == len(b)
        for fa, fb in zip(a, b, strict=True):
            for k, va in fa.items():
                if k == "fid":
                    continue
                vb = fb[k]
                if isinstance(va, float) and vb is not None:
                    assert np.isclose(va, vb, atol=1e-9), (tabla, fa["id_parte"], k)
                else:
                    assert va == vb, (tabla, fa["id_parte"], k)
