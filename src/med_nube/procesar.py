"""Procesamiento: nubes de puntos + huellas → tablas `alturas` y `techos`.

>>> ESTE ES EL ÚNICO MÓDULO QUE HAY QUE IMPLEMENTAR. Puede apoyarse en módulos
>>> nuevos src/med_nube/proc_*.py (ver AGENTS.md). Reglas exactas: docs/contrato.md §3.

Interfaz obligatoria (las pruebas de tests/test_aceptacion.py la usan tal cual):

    procesar(huellas, nubes, salida, commit=None) -> Path

- `huellas`: GeoPackage con la capa `huellas` (oficial o huellas_coltejer.gpkg).
- `nubes`: carpeta con los bloques *.las / *.laz (no recursiva) o lista de rutas.
- `salida`: carpeta donde se escribe med_nube_entrega_<AAAAMMDD>.gpkg.
- `commit`: solo lo pasan las pruebas. Si es None, se obtiene con
  `escribir.commit_actual()` AL INICIO (antes de leer datos: falla rápido si src/ está
  sucio) y se pasa tal cual a `escribir_entrega`. Nunca se calcula de otra forma ni se
  inventa.

Debe terminar llamando a `escribir.escribir_entrega(...)` y devolver su ruta.
`src/` no importa nada de `tests/` ni contiene ids o nombres de bloque del escenario
sintético.

Implementación
--------------
1. Bloques: nombre, CRS y omisiones (``proc_lectura``, §3.1).
2. Huellas: se verifican las garantías del §2; para las partes cercanas a algún bloque se
   calculan el área efectiva A (§3.4) y el anillo de suelo R (§3.5) (``proc_geometria``).
3. Cada bloque se lee completo y sus puntos filtrados se asignan a los A y R
   (``proc_bloque.procesar_bloque``). Queda una caché por bloque en
   ``<salida>/intermedios/`` (fuera del repo si la salida lo está): la corrida se puede
   reanudar y los puntos de techo y suelo por parte quedan para la revisión del §5.6.
4. Cada parte toma el bloque con más puntos de techo; en empate, el de nombre menor
   (§3.2). Con los puntos de ese bloque se calculan ``alturas`` y ``techos``.
5. Una sola llamada a ``escribir_entrega``.

Rendimiento (no cambia el resultado): variables de entorno ``MED_NUBE_PUNTOS_POR_TROZO``
(puntos por lectura, 5 000 000 por defecto), ``MED_NUBE_PROCESOS`` (0 = automático) y
``MED_NUBE_MEMORIA_GB`` (memoria para los procesos de bloque; 0 = la disponible al empezar
la fase de bloques, menos un margen). Cada bloque reserva una estimación de su memoria según
el número de puntos de su cabecera, y solo se lanzan a la vez los que caben.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
import shapely

from . import contrato as C
from .escribir import commit_actual, escribir_entrega
from .proc_bloque import calcular_partes, procesar_bloque
from .proc_geometria import areas_y_anillos
from .proc_lectura import inspeccionar, listar_bloques
from .validar import sha256

log = logging.getLogger(__name__)

FORMATO_CACHE = 1
PARTES_POR_TAREA_GEOMETRIA = 1000
PUNTOS_POR_TAREA_PARTES = 2_000_000
PARTES_MAX_POR_TAREA = 500
# Memoria estimada de un proceso de bloque: base + bytes por punto de la cabecera. Es una
# cota superior medida en el peor caso urbano (ningún punto filtrado y el 86 % de los
# puntos dentro de algún A o R): 92-99 bytes por punto con 5, 20 y 40 millones de puntos.
GB_BASE_POR_BLOQUE = 1.0
BYTES_POR_PUNTO_DE_BLOQUE = 100
GB_MARGEN_MEMORIA = 4.0


@dataclass(frozen=True)
class Opciones:
    """Solo afectan el rendimiento, nunca el resultado."""

    puntos_por_trozo: int = 5_000_000
    procesos: int = 0  # 0 = automático
    memoria_gb: float = 0.0  # 0 = automático (memoria disponible menos un margen)

    @classmethod
    def del_entorno(cls) -> Opciones:
        return cls(
            puntos_por_trozo=int(os.environ.get("MED_NUBE_PUNTOS_POR_TROZO", 5_000_000)),
            procesos=int(os.environ.get("MED_NUBE_PROCESOS", 0)),
            memoria_gb=float(os.environ.get("MED_NUBE_MEMORIA_GB", 0)),
        )


def procesar(
    huellas: Path,
    nubes: Path | Sequence[Path],
    salida: Path,
    commit: str | None = None,
) -> Path:
    return ejecutar(huellas, nubes, salida, commit=commit, opciones=Opciones.del_entorno())


# ======================================================================================
# Utilidades
# ======================================================================================
def _estado_memoria_gb() -> tuple[float, float]:
    """(total, disponible) de memoria física en GB; (0, 0) si no se puede saber."""
    try:
        if os.name == "nt":
            import ctypes

            class _Estado(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            e = _Estado()
            e.dwLength = ctypes.sizeof(_Estado)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(e))
            return e.ullTotalPhys / 1024**3, e.ullAvailPhys / 1024**3
        pagina = os.sysconf("SC_PAGE_SIZE")
        return (
            pagina * os.sysconf("SC_PHYS_PAGES") / 1024**3,
            pagina * os.sysconf("SC_AVPHYS_PAGES") / 1024**3,
        )
    except Exception:
        return 0.0, 0.0


def _memoria_total_gb() -> float:
    return _estado_memoria_gb()[0]


def _procesos(opciones: Opciones) -> int:
    if opciones.procesos > 0:
        return opciones.procesos
    cpus = os.cpu_count() or 1
    return max(1, min(cpus - 1, 32))


def _memoria_bloque_gb(info) -> float:
    """Memoria estimada para leer y asignar un bloque (cota superior)."""
    return GB_BASE_POR_BLOQUE + BYTES_POR_PUNTO_DE_BLOQUE * info.n_puntos / 1024**3


def _capacidad_bloques_gb(opciones: Opciones) -> float | None:
    """Memoria para los procesos de bloque que corren a la vez. None si no se puede saber
    (entonces se limita a 2 procesos)."""
    if opciones.memoria_gb > 0:
        return opciones.memoria_gb
    _, disponible = _estado_memoria_gb()
    if disponible <= 0:
        return None
    return max(2.0, disponible - GB_MARGEN_MEMORIA)


def _en_paralelo(
    funcion: Callable,
    tareas: Iterable,
    procesos: int,
    pesos: Sequence[float] | None = None,
    capacidad: float | None = None,
    etiqueta: str | None = None,
) -> list:
    """Resultados en el orden de las tareas. Con 1 proceso, todo corre aquí mismo.

    Sin ``capacidad``, las tareas se envían en orden y de a pocas (2 por proceso) para no
    tener todas en memoria a la vez. Con ``capacidad``, cada tarea ocupa su ``peso`` (GB
    estimados) mientras corre y solo se lanza si cabe en lo que queda libre; si la siguiente
    no cabe, se prueba con las que vienen después. Siempre corre al menos una. El reparto no
    cambia ningún resultado: cada tarea es independiente y su resultado va en su lugar.
    Con ``etiqueta``, se informa el avance cada minuto.
    """
    tareas = list(tareas) if not isinstance(tareas, list) else tareas
    if procesos <= 1 or len(tareas) <= 1:
        return [funcion(t) for t in tareas]
    pesos = [0.0] * len(tareas) if pesos is None else [float(p) for p in pesos]
    tope = procesos if capacidad is not None else 2 * procesos
    resultados: list = [None] * len(tareas)
    with ProcessPoolExecutor(max_workers=min(procesos, len(tareas))) as pool:
        pendientes: dict = {}
        por_enviar = list(range(len(tareas)))
        en_uso = 0.0
        hechas_total, t_aviso = 0, time.perf_counter()
        while por_enviar or pendientes:
            j = 0
            while j < len(por_enviar) and len(pendientes) < tope:
                i = por_enviar[j]
                if capacidad is None or not pendientes or en_uso + pesos[i] <= capacidad:
                    pendientes[pool.submit(funcion, tareas[i])] = i
                    tareas[i] = None  # liberar la tarea ya enviada
                    en_uso += pesos[i]
                    por_enviar.pop(j)
                elif capacidad is None:
                    break
                else:
                    j += 1
            hechas, _ = wait(pendientes, return_when=FIRST_COMPLETED)
            for fut in hechas:
                i = pendientes.pop(fut)
                en_uso -= pesos[i]
                resultados[i] = fut.result()
            hechas_total += len(hechas)
            if etiqueta and time.perf_counter() - t_aviso >= 60:
                t_aviso = time.perf_counter()
                log.info(
                    "%s: %d de %d tareas (%.0f %%)",
                    etiqueta,
                    hechas_total,
                    len(tareas),
                    100 * hechas_total / len(tareas),
                )
    return resultados


def _leer_huellas(ruta: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """id_parte, pisos y geometrías. Verifica las garantías del contrato §2."""
    gdf = pyogrio.read_dataframe(ruta, layer=C.HUELLAS_CAPA, columns=["id_parte", "pisos"])
    if gdf.crs is None or gdf.crs.to_epsg() != C.CRS_EPSG:
        raise RuntimeError(f"La capa '{C.HUELLAS_CAPA}' no está en EPSG:{C.CRS_EPSG}.")
    ids = gdf["id_parte"].astype(str).to_numpy()
    if gdf["pisos"].isna().any():
        raise RuntimeError("huellas: 'pisos' tiene NULL; contradice el contrato §2.")
    pisos = gdf["pisos"].to_numpy().astype(np.int64)
    geoms = np.asarray(gdf.geometry.values, dtype=object)
    if len(set(ids)) != len(ids):
        raise RuntimeError("huellas: 'id_parte' repetido; contradice el contrato §2.")
    if shapely.is_missing(geoms).any() or shapely.is_empty(geoms).any():
        raise RuntimeError("huellas: hay geometrías vacías; contradice el contrato §2.")
    if not shapely.is_valid(geoms).all():
        raise RuntimeError("huellas: hay geometrías inválidas; contradice el contrato §2.")
    return ids, pisos, geoms


def _tareas_geometria(arbol, geoms, pisos, partes: np.ndarray) -> list[dict]:
    """Grupos de partes vecinas, cada uno con todas las huellas que pueden intervenir."""
    cajas = shapely.bounds(geoms[partes])
    centro = (cajas[:, :2] + cajas[:, 2:]) / 2
    celda = np.floor(centro / 250.0).astype(np.int64)
    partes = partes[np.lexsort((partes, celda[:, 1], celda[:, 0]))]
    margen = C.ANILLO_EXTERIOR_M + 1.0
    tareas = []
    for i in range(0, len(partes), PARTES_POR_TAREA_GEOMETRIA):
        grupo = partes[i : i + PARTES_POR_TAREA_GEOMETRIA]
        b = shapely.bounds(geoms[grupo])
        cajas_grupo = shapely.box(
            b[:, 0] - margen, b[:, 1] - margen, b[:, 2] + margen, b[:, 3] + margen
        )
        vecinos = np.unique(arbol.query(cajas_grupo)[1])
        tareas.append(
            {
                "partes": grupo,
                "vecinos": vecinos,
                "vecinos_wkb": shapely.to_wkb(geoms[vecinos]),
                "vecinos_pisos": pisos[vecinos],
            }
        )
    return tareas


# ======================================================================================
# Corrida
# ======================================================================================
def ejecutar(
    huellas: Path,
    nubes: Path | Sequence[Path],
    salida: Path,
    commit: str | None = None,
    opciones: Opciones | None = None,
) -> Path:
    if commit is None:
        commit = commit_actual()  # al inicio: falla rápido si src/ está sucio
    opciones = opciones or Opciones()
    t0 = time.perf_counter()
    huellas, salida = Path(huellas), Path(salida)
    tiempos: dict[str, float] = {}

    # --- 1. bloques ---------------------------------------------------------------------
    infos = [inspeccionar(r) for r in listar_bloques(nubes)]
    omitidos = {i.nombre: i.omision for i in infos if i.omision}
    validos = [i for i in infos if not i.omision]
    for nombre, motivo in sorted(omitidos.items()):
        log.info("Bloque %s omitido: %s", nombre, motivo)
    log.info("%d bloques a procesar, %d omitidos", len(validos), len(omitidos))

    # --- 2. huellas y geometrías por parte ----------------------------------------------
    t = time.perf_counter()
    ids, pisos, geoms = _leer_huellas(huellas)
    huellas_sha = sha256(huellas)
    arbol = shapely.STRtree(geoms)
    margen = C.ANILLO_EXTERIOR_M + 1.0
    cercanas: dict[str, np.ndarray] = {}
    partes_caja: dict[str, int] = {}
    for info in validos:
        x0, y0, x1, y1 = info.caja_9377
        cercanas[info.nombre] = np.sort(
            arbol.query(shapely.box(x0 - margen, y0 - margen, x1 + margen, y1 + margen))
        )
        partes_caja[info.nombre] = len(arbol.query(shapely.box(x0, y0, x1, y1)))
    candidatas = (
        np.unique(np.concatenate(list(cercanas.values()))) if cercanas else np.empty(0, int)
    )
    log.info("%d huellas; %d cerca de algún bloque", len(ids), len(candidatas))
    a_wkb: dict[int, bytes] = {}
    r_wkb: dict[int, bytes] = {}
    for lote in _en_paralelo(
        areas_y_anillos,
        _tareas_geometria(arbol, geoms, pisos, candidatas) if len(candidatas) else [],
        _procesos(opciones),
        etiqueta="Geometrías",
    ):
        for g, a, r in lote:
            if a is not None:
                a_wkb[g], r_wkb[g] = a, r
    tiempos["geometrias_s"] = round(time.perf_counter() - t, 1)
    log.info(
        "%d partes con área efectiva >= %s m² (%.0f s)",
        len(a_wkb),
        C.AREA_EFECTIVA_MIN_M2,
        tiempos["geometrias_s"],
    )

    # --- 3. bloques: lectura, filtros y asignación de puntos -----------------------------
    t = time.perf_counter()
    raiz = salida / "intermedios" / f"{commit[:12]}_{huellas_sha[:12]}"
    tareas_bloque = []
    for info in sorted(validos, key=lambda i: (-i.bytes, i.nombre)):  # el más grande primero
        partes = np.array([g for g in cercanas[info.nombre] if int(g) in a_wkb], dtype=np.int64)
        clave = {
            "formato_cache": FORMATO_CACHE,
            "version_contrato": C.VERSION_CONTRATO,
            "commit": commit,
            "huellas_sha256": huellas_sha,
            "archivo": Path(info.ruta).name,
            "bytes": info.bytes,
            "mtime_ns": info.mtime_ns,
            "partes_sha1": hashlib.sha1(partes.tobytes()).hexdigest(),
        }
        tareas_bloque.append(
            {
                "info": info,
                "carpeta": str(raiz / info.nombre),
                "clave": clave,
                "puntos_por_trozo": opciones.puntos_por_trozo,
                "partes": partes,
                "a_wkb": [a_wkb[int(g)] for g in partes],
                "r_wkb": [r_wkb[int(g)] for g in partes],
            }
        )
    procesos_bloque = _procesos(opciones)
    pesos = [_memoria_bloque_gb(tb["info"]) for tb in tareas_bloque]
    capacidad = _capacidad_bloques_gb(opciones)
    if capacidad is None:
        procesos_bloque = min(procesos_bloque, 2)
    tiempos["memoria_bloques_gb"] = round(capacidad, 1) if capacidad is not None else None
    log.info(
        "Bloques: hasta %d procesos, %s GB de memoria para bloques; el mayor estima %.1f GB",
        procesos_bloque,
        f"{capacidad:.1f}" if capacidad is not None else "?",
        max(pesos, default=0.0),
    )
    resultados = {}
    for res in _en_paralelo(
        procesar_bloque,
        tareas_bloque,
        procesos_bloque,
        pesos=pesos,
        capacidad=capacidad,
        etiqueta="Bloques",
    ):
        resultados[res["nombre"]] = res
        e = res["estad"]
        log.info(
            "Bloque %s: %s puntos, %s tras filtros, %s s%s",
            res["nombre"],
            e["puntos_archivo"],
            e["puntos_filtrados"],
            e.get("segundos_total", "?"),
            " (desde caché)" if e.get("desde_cache") else "",
        )
    tiempos["bloques_s"] = round(time.perf_counter() - t, 1)

    # --- 4. asignación de bloque por parte (§3.2) -------------------------------------------
    nombres = sorted(resultados)  # orden de Python: en empate gana el nombre menor
    mejor_n = np.zeros(len(ids), dtype=np.int64)
    mejor_b = np.full(len(ids), -1, dtype=np.int64)
    for k, nombre in enumerate(nombres):
        partes, n = resultados[nombre]["partes"], resultados[nombre]["n_techo"]
        mejora = n > mejor_n[partes]  # estricto: el empate lo conserva el nombre menor
        mejor_n[partes[mejora]] = n[mejora]
        mejor_b[partes[mejora]] = k

    t = time.perf_counter()
    tareas_partes = []
    for k, nombre in enumerate(nombres):
        asignadas = np.flatnonzero((mejor_b == k) & (mejor_n >= C.MIN_PUNTOS_TECHO))
        grupo, puntos = [], 0
        for g in asignadas:
            grupo.append(int(g))
            puntos += int(mejor_n[g])
            if puntos >= PUNTOS_POR_TAREA_PARTES or len(grupo) >= PARTES_MAX_POR_TAREA:
                tareas_partes.append((nombre, grupo))
                grupo, puntos = [], 0
        if grupo:
            tareas_partes.append((nombre, grupo))
    log.info(
        "Partes: %d con al menos %d puntos de techo, en %d tareas",
        sum(len(g) for _, g in tareas_partes),
        C.MIN_PUNTOS_TECHO,
        len(tareas_partes),
    )
    filas_a, filas_t = [], []
    for alt, tec in _en_paralelo(
        calcular_partes,
        [
            {
                "carpeta": str(raiz / nombre),
                "bloque": nombre,
                "partes": grupo,
                "ids": [str(ids[g]) for g in grupo],
                "a_wkb": [a_wkb[g] for g in grupo],
            }
            for nombre, grupo in tareas_partes
        ],
        _procesos(opciones),
        etiqueta="Partes",
    ):
        filas_a.extend(alt)
        filas_t.extend(tec)
    tiempos["partes_s"] = round(time.perf_counter() - t, 1)

    alturas = pd.DataFrame(filas_a, columns=list(C.COLUMNAS_ALTURAS))
    techos = pd.DataFrame(filas_t, columns=list(C.COLUMNAS_TECHOS))
    alturas = alturas.sort_values("id_parte", kind="stable").reset_index(drop=True)
    techos = techos.sort_values("id_parte", kind="stable").reset_index(drop=True)

    # --- 5. entrega ---------------------------------------------------------------------
    ruta = escribir_entrega(
        alturas,
        techos,
        huellas,
        bloques=[i.nombre for i in validos],
        bloques_omitidos=omitidos,
        bloques_advertencias={},
        carpeta=salida,
        commit=commit,
    )
    tiempos["total_s"] = round(time.perf_counter() - t0, 1)
    _bitacora(
        raiz, ruta, commit, opciones, infos, resultados, partes_caja, alturas, techos, tiempos
    )
    log.info(
        "Entrega: %s (%d partes en alturas, %d en techos, %.0f s)",
        ruta,
        len(alturas),
        len(techos),
        tiempos["total_s"],
    )
    return ruta


def _bitacora(
    raiz, ruta, commit, opciones, infos, resultados, partes_caja, alturas, techos, tiempos
) -> None:
    """Resumen de la corrida para la bitácora del README (no forma parte de la entrega)."""
    import laspy
    import pyproj

    asignadas = alturas["bloque"].value_counts().to_dict() if len(alturas) else {}
    datos = {
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "entrega": str(ruta),
        "commit": commit,
        "maquina": {
            "nombre": platform.node(),
            "cpu": platform.processor() or platform.machine(),
            "nucleos_logicos": os.cpu_count(),
            "memoria_gb": round(_memoria_total_gb(), 1),
            "sistema": platform.platform(),
        },
        "versiones": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pyproj": pyproj.__version__,
            "laspy": laspy.__version__,
            "shapely": shapely.__version__,
        },
        "opciones": asdict(opciones),
        "tiempos": tiempos,
        "bloques": {
            i.nombre: (
                {"omitido": i.omision}
                if i.omision
                else {
                    **resultados[i.nombre]["estad"],
                    "partes_bbox_intersecta": partes_caja[i.nombre],
                    "partes_asignadas_con_20_o_mas": int(asignadas.get(i.nombre, 0)),
                }
            )
            for i in infos
        },
        "partes_alturas": len(alturas),
        "partes_techos": len(techos),
    }
    raiz.mkdir(parents=True, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    (raiz / f"corrida_{sello}.json").write_text(
        json.dumps(datos, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
