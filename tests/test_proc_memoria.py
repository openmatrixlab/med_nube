"""Reparto de los bloques entre procesos según la memoria estimada: solo cambia cuántos
corren a la vez, nunca el resultado (AGENTS.md › Libertad de implementación)."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

import pytest

from med_nube.procesar import Opciones, _en_paralelo, ejecutar
from tests import sinteticos as S

COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _tarea(t: dict) -> int:
    """Anota cuándo empieza y termina, para medir qué corrió a la vez."""
    inicio = time.perf_counter()
    time.sleep(t["espera"])
    fin = time.perf_counter()
    Path(t["carpeta"], f"{t['i']}.json").write_text(
        json.dumps({"i": t["i"], "inicio": inicio, "fin": fin, "pid": os.getpid()}),
        encoding="utf-8",
    )
    return t["i"] * 10


def _maximo_simultaneo(carpeta: Path, pesos: list[float]) -> tuple[float, int]:
    marcas = [json.loads(p.read_text(encoding="utf-8")) for p in carpeta.glob("*.json")]
    eventos = sorted(
        [(m["inicio"], 1, m["i"]) for m in marcas] + [(m["fin"], 0, m["i"]) for m in marcas]
    )  # en el mismo instante, primero los que terminan
    activos: set[int] = set()
    peso_max, n_max = 0.0, 0
    for _, empieza, i in eventos:
        if empieza:
            activos.add(i)
            if len(activos) > 1:  # una sola tarea puede pasar la capacidad
                peso_max = max(peso_max, sum(pesos[k] for k in activos))
            n_max = max(n_max, len(activos))
        else:
            activos.discard(i)
    return peso_max, n_max


def test_resultados_en_orden_y_capacidad_respetada(tmp_path):
    pesos = [6.0, 5.0, 4.0, 1.0, 1.0, 1.0, 9.0, 0.5]
    tareas = [{"i": i, "espera": 0.3, "carpeta": str(tmp_path)} for i in range(len(pesos))]
    salida = _en_paralelo(_tarea, tareas, procesos=4, pesos=pesos, capacidad=8.0)
    assert salida == [i * 10 for i in range(len(pesos))]
    peso_max, n_max = _maximo_simultaneo(tmp_path, pesos)
    assert peso_max <= 8.0  # la de 9 GB corrió sola: no cabe con ninguna otra
    assert 1 < n_max <= 4


def test_tarea_mayor_que_la_capacidad_corre_sola(tmp_path):
    pesos = [3.0, 3.0]
    tareas = [{"i": i, "espera": 0.2, "carpeta": str(tmp_path)} for i in range(2)]
    assert _en_paralelo(_tarea, tareas, procesos=2, pesos=pesos, capacidad=1.0) == [0, 10]
    _, n_max = _maximo_simultaneo(tmp_path, pesos)
    assert n_max == 1


def _tablas(ruta):
    con = sqlite3.connect(ruta)
    try:
        salida = {}
        for tabla in ("alturas", "techos", "metadatos"):
            cur = con.execute(f"SELECT * FROM [{tabla}]")
            nombres = [d[0] for d in cur.description]
            filas = [
                {c: v for c, v in zip(nombres, f, strict=True) if c != "fid"}
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
    carpeta = tmp_path_factory.mktemp("memoria")
    return carpeta, *S.construir(carpeta)


def test_identico_con_memoria_minima_y_un_proceso(escenario):
    carpeta, huellas, nubes = escenario
    uno = ejecutar(huellas, nubes, carpeta / "uno", COMMIT, Opciones(procesos=1))
    # capacidad mínima: los bloques corren de a uno aunque haya 3 procesos
    justo = ejecutar(
        huellas, nubes, carpeta / "justo", COMMIT, Opciones(procesos=3, memoria_gb=0.001)
    )
    # capacidad amplia: todos a la vez
    amplio = ejecutar(
        huellas, nubes, carpeta / "amplio", COMMIT, Opciones(procesos=3, memoria_gb=1000.0)
    )
    assert _tablas(uno) == _tablas(justo) == _tablas(amplio)
