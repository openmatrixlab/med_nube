"""El resultado no depende del tamaño de trozo, del número de procesos ni de reanudar
desde la caché (AGENTS.md › Libertad de implementación)."""

from __future__ import annotations

import json
import sqlite3

import pytest

from med_nube.procesar import Opciones, ejecutar
from tests import sinteticos as S

COMMIT = "fedcba9876543210fedcba9876543210fedcba98"


def _tablas(ruta):
    con = sqlite3.connect(ruta)
    try:
        salida = {}
        for tabla in ("alturas", "techos", "metadatos"):
            cur = con.execute(f"SELECT * FROM [{tabla}]")
            cols = [d[0] for d in cur.description if d[0] != "fid"]
            filas = [
                {c: v for c, v in zip([d[0] for d in cur.description], f, strict=True) if c in cols}
                for f in cur.fetchall()
            ]
            if tabla == "metadatos":
                filas = [f for f in filas if f["clave"] != "fecha_proceso"]
            salida[tabla] = sorted(filas, key=lambda f: json.dumps(f, sort_keys=True))
        return salida
    finally:
        con.close()


@pytest.fixture(scope="module")
def escenario(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("trozos")
    return carpeta, *S.construir(carpeta)


def test_identico_con_trozos_y_procesos_distintos(escenario):
    carpeta, huellas, nubes = escenario
    a = ejecutar(huellas, nubes, carpeta / "a", COMMIT, Opciones(puntos_por_trozo=997, procesos=1))
    b = ejecutar(
        huellas, nubes, carpeta / "b", COMMIT, Opciones(puntos_por_trozo=5_000_000, procesos=3)
    )
    assert _tablas(a) == _tablas(b)


def test_reanudar_desde_cache_da_lo_mismo(escenario):
    carpeta, huellas, nubes = escenario
    primera = _tablas(ejecutar(huellas, nubes, carpeta / "c", COMMIT, Opciones(procesos=1)))
    segunda = ejecutar(huellas, nubes, carpeta / "c", COMMIT, Opciones(procesos=1))
    assert _tablas(segunda) == primera
    corridas = sorted((carpeta / "c" / "intermedios").glob("*/corrida_*.json"))
    ultima = json.loads(corridas[-1].read_text(encoding="utf-8"))
    leidos = {b: e.get("desde_cache") for b, e in ultima["bloques"].items() if "omitido" not in e}
    assert leidos and all(leidos.values())  # la segunda corrida no volvió a leer los bloques
