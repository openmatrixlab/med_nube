"""Trabajo por bloque y por parte, pensado para correr en procesos separados.

Por bloque (``procesar_bloque``): lee los puntos filtrados (§3.1, §3.3), los asigna a las
áreas efectivas A (techo) y a los anillos R (suelo) de las partes cercanas, y guarda una
caché en disco, fuera del repositorio:

    <carpeta>/puntos.npy        X, Y (EPSG:9377), Z de los puntos que caen en algún A o R
    <carpeta>/techo_parte.npy   parte de cada par de techo (índice en huellas.gpkg)
    <carpeta>/techo_idx.npy     punto (fila de puntos.npy) de cada par de techo
    <carpeta>/suelo_parte.npy   ídem para el suelo
    <carpeta>/suelo_idx.npy
    <carpeta>/manifiesto.json   clave de la caché y resumen; se escribe al final

Los pares están ordenados por (parte, punto), así que la caché no depende del tamaño de
trozo ni del número de procesos. Si la corrida se cae, el bloque con manifiesto válido no
se vuelve a leer. Estos archivos son también el detalle de puntos de techo y suelo por
parte que pide el contrato §5.6.

Por parte (``calcular_partes``): con los puntos del bloque asignado, filas de ``alturas``
(§3.6) y, si cumple los umbrales, de ``techos`` (§3.7).
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import numpy as np
import shapely

from . import contrato as C
from .proc_geometria import asignar, cobertura
from .proc_lectura import InfoBloque, leer_puntos_filtrados
from .proc_ransac import ajustar_planos, describir_techo

ARCHIVOS = ("puntos", "techo_parte", "techo_idx", "suelo_parte", "suelo_idx")
TOLERANCIA_CAJA_M = 0.5


def cache_valida(carpeta: Path, clave: dict) -> dict | None:
    manifiesto = carpeta / "manifiesto.json"
    if not manifiesto.is_file():
        return None
    try:
        datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if datos.get("clave") != clave:
        return None
    if not all((carpeta / f"{n}.npy").is_file() for n in ARCHIVOS):
        return None
    return datos


def _conteos(carpeta: Path) -> tuple[np.ndarray, np.ndarray]:
    partes = np.load(carpeta / "techo_parte.npy", mmap_mode="r")
    unicas, n = np.unique(np.asarray(partes), return_counts=True)
    return unicas.astype(np.int64), n.astype(np.int64)


def procesar_bloque(tarea: dict) -> dict:
    """Lee un bloque, asigna sus puntos y deja la caché. Devuelve conteos de techo por
    parte y estadísticas para la bitácora."""
    info: InfoBloque = tarea["info"]
    carpeta = Path(tarea["carpeta"])
    clave = tarea["clave"]
    datos = cache_valida(carpeta, clave)
    if datos is not None:
        partes, n = _conteos(carpeta)
        return {
            "nombre": info.nombre,
            "partes": partes,
            "n_techo": n,
            "estad": {**datos["estad"], "desde_cache": True},
        }

    t0 = time.perf_counter()
    x, y, z, estad = leer_puntos_filtrados(info, tarea["puntos_por_trozo"])
    t_lectura = time.perf_counter() - t0

    # Las partes se eligieron con la caja de la cabecera; ningún punto puede quedar fuera.
    if len(x):
        cx0, cy0, cx1, cy1 = info.caja_9377
        fuera = (
            x.min() < cx0 - TOLERANCIA_CAJA_M
            or x.max() > cx1 + TOLERANCIA_CAJA_M
            or y.min() < cy0 - TOLERANCIA_CAJA_M
            or y.max() > cy1 + TOLERANCIA_CAJA_M
        )
        if fuera:
            raise RuntimeError(
                f"Bloque {info.nombre}: hay puntos fuera de la caja de su cabecera. "
                "Archivo inconsistente: la corrida se detiene (contrato §3.1.4)."
            )

    partes = np.asarray(tarea["partes"], dtype=np.int64)
    geom_a = shapely.from_wkb(tarea["a_wkb"])
    geom_r = shapely.from_wkb(tarea["r_wkb"])
    t1 = time.perf_counter()
    tp, ti = asignar(x, y, geom_a, partes)
    sp, si = asignar(x, y, geom_r, partes)
    t_asignacion = time.perf_counter() - t1

    usados = np.union1d(ti, si)
    puntos = np.column_stack([x[usados], y[usados], z[usados]])
    del x, y, z
    techo_idx = np.searchsorted(usados, ti).astype(np.int64)
    suelo_idx = np.searchsorted(usados, si).astype(np.int64)

    temporal = carpeta.with_name(carpeta.name + ".tmp")
    if temporal.exists():
        shutil.rmtree(temporal)  # restos de una corrida interrumpida de este mismo bloque
    temporal.mkdir(parents=True)
    for nombre, arr in (
        ("puntos", puntos),
        ("techo_parte", tp),
        ("techo_idx", techo_idx),
        ("suelo_parte", sp),
        ("suelo_idx", suelo_idx),
    ):
        np.save(temporal / f"{nombre}.npy", arr)
    estad.update(
        {
            "segundos_lectura": round(t_lectura, 1),
            "segundos_asignacion": round(t_asignacion, 1),
            "segundos_total": round(time.perf_counter() - t0, 1),
            "partes_candidatas": len(partes),
            "pares_techo": len(tp),
            "pares_suelo": len(sp),
            "puntos_en_cache": len(puntos),
        }
    )
    (temporal / "manifiesto.json").write_text(
        json.dumps({"clave": clave, "estad": estad}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if carpeta.exists():
        shutil.rmtree(carpeta)  # caché incompleta o de otra clave para este mismo bloque
    for intento in range(10):  # en Windows el antivirus puede retener la carpeta un momento
        try:
            temporal.rename(carpeta)
            break
        except PermissionError:
            if intento == 9:
                raise
            time.sleep(1 + intento)
    unicas, n = _conteos(carpeta)
    return {
        "nombre": info.nombre,
        "partes": unicas,
        "n_techo": n,
        "estad": {**estad, "desde_cache": False},
    }


def _tramo(partes_ordenadas: np.ndarray, parte: int) -> slice:
    # La clave va con el mismo tipo del arreglo: si no, NumPy convierte el arreglo entero
    # (cientos de millones de pares en un bloque grande) a int64 en cada búsqueda.
    clave = partes_ordenadas.dtype.type(parte)
    lo = int(np.searchsorted(partes_ordenadas, clave, side="left"))
    hi = int(np.searchsorted(partes_ordenadas, clave, side="right"))
    return slice(lo, hi)


def calcular_partes(tarea: dict) -> tuple[list[dict], list[dict]]:
    """Filas de ``alturas`` y ``techos`` de las partes asignadas a un bloque."""
    carpeta = Path(tarea["carpeta"])
    bloque = tarea["bloque"]
    puntos = np.load(carpeta / "puntos.npy", mmap_mode="r")
    tparte = np.load(carpeta / "techo_parte.npy", mmap_mode="r")
    tidx = np.load(carpeta / "techo_idx.npy", mmap_mode="r")
    sparte = np.load(carpeta / "suelo_parte.npy", mmap_mode="r")
    sidx = np.load(carpeta / "suelo_idx.npy", mmap_mode="r")
    areas = shapely.from_wkb(tarea["a_wkb"])
    alturas, techos = [], []
    for parte, id_parte, area in zip(tarea["partes"], tarea["ids"], areas, strict=True):
        techo = np.asarray(puntos[np.asarray(tidx[_tramo(tparte, parte)])])
        n = len(techo)
        if n < C.MIN_PUNTOS_TECHO:
            continue
        z = techo[:, 2]
        p10, p50, p90, p98 = np.percentile(z, [10, 50, 90, 98])
        z_suelo_pts = np.asarray(puntos[np.asarray(sidx[_tramo(sparte, parte)]), 2])
        n_suelo = len(z_suelo_pts)
        if n_suelo >= C.MIN_PUNTOS_SUELO:
            z_suelo = float(np.percentile(z_suelo_pts, C.PERCENTIL_SUELO))
            h50, h98 = float(p50) - z_suelo, float(p98) - z_suelo
        else:
            z_suelo = h50 = h98 = None
        cob = cobertura(area, techo[:, 0], techo[:, 1])
        alturas.append(
            {
                "id_parte": id_parte,
                "bloque": bloque,
                "n_puntos": n,
                "cobertura": cob,
                "z_p10": float(p10),
                "z_p50": float(p50),
                "z_p90": float(p90),
                "z_p98": float(p98),
                "z_max": float(z.max()),
                "n_puntos_suelo": n_suelo,
                "z_suelo": z_suelo,
                "h_p50": h50,
                "h_p98": h98,
            }
        )
        if n >= C.MIN_PUNTOS_TECHOS and cob >= C.MIN_COBERTURA_TECHOS:
            planos, total = ajustar_planos(techo)
            techos.append({"id_parte": id_parte, **describir_techo(planos, total)})
    return alturas, techos
