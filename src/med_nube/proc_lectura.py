"""Lectura de los bloques de nube de puntos (contrato §3.1 y §3.3).

- Nombre de bloque: ``Path(archivo).stem``; dos archivos con el mismo stem detienen la
  corrida.
- CRS: ``header.parse_crs()``; si devuelve None o lanza excepción, ``<stem>.crs`` junto al
  bloque; si tampoco hay, el bloque se omite con ``sin CRS``. CRS compuesto: su parte
  horizontal. Solo X e Y se llevan a EPSG:9377; Z nunca se toca.
- Formatos de punto sin RGB: el bloque se omite con ``sin RGB``.
- Ruido: se descartan las clases 7 y 18.
- RGB: se normaliza con el máximo de R, G y B de **todo** el archivo, antes de cualquier
  filtro (primera pasada); ExG > 0,10 es vegetación y se descarta.
- No se submuestrea: todos los demás puntos siguen.

Cualquier otra falla al leer un bloque se propaga y detiene la corrida (§3.1.4).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import laspy
import numpy as np
import pyproj

from . import contrato as C

log = logging.getLogger(__name__)

EXTENSIONES = (".las", ".laz")


@dataclass(frozen=True)
class InfoBloque:
    nombre: str
    ruta: str
    bytes: int
    mtime_ns: int
    formato: int
    n_puntos: int
    crs_wkt: str | None  # parte horizontal del CRS
    fuente_crs: str
    transformar: bool  # True si el CRS horizontal no es EPSG:9377
    caja_9377: tuple[float, float, float, float] | None  # caja de la cabecera en EPSG:9377
    omision: str | None  # "sin CRS", "sin RGB" o None


def listar_bloques(nubes: Path | str | Sequence[Path | str]) -> list[Path]:
    """Bloques *.las / *.laz de una carpeta (no recursiva) o de una lista de rutas."""
    if isinstance(nubes, (str, os.PathLike)):
        carpeta = Path(nubes)
        if not carpeta.is_dir():
            raise NotADirectoryError(f"'{carpeta}' no es una carpeta de bloques")
        rutas = [p for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES]
    else:
        rutas = [Path(p) for p in nubes]
    por_stem: dict[str, list[str]] = {}
    for r in rutas:
        por_stem.setdefault(r.stem, []).append(r.name)
    repetidos = {s: sorted(n) for s, n in por_stem.items() if len(n) > 1}
    if repetidos:
        raise RuntimeError(
            f"Bloques con el mismo nombre (stem): {repetidos}. El contrato (§3) pide parar y "
            "preguntar: escribirlo en PREGUNTAS.md."
        )
    return sorted(rutas, key=lambda r: r.stem)


def _crs_horizontal(crs: pyproj.CRS) -> pyproj.CRS:
    return crs.sub_crs_list[0] if crs.is_compound else crs


def inspeccionar(ruta: Path) -> InfoBloque:
    """Cabecera, CRS y motivo de omisión de un bloque (§3.1.1 y §3.1.3)."""
    ruta = Path(ruta)
    # Abrir la cabecera: si falla, el archivo no se puede leer y la corrida se detiene.
    with laspy.open(ruta) as f:
        h = f.header
        formato = int(h.point_format.id)
        n_puntos = int(h.point_count)
        mins, maxs = np.asarray(h.mins, dtype=float), np.asarray(h.maxs, dtype=float)
        try:
            crs = h.parse_crs()  # P2: solo una excepción de parse_crs() equivale a None
        except Exception:
            crs = None
    fuente = "cabecera LAS"
    if crs is None:
        archivo_crs = ruta.with_name(ruta.stem + ".crs")
        if archivo_crs.is_file():
            crs = pyproj.CRS.from_user_input(archivo_crs.read_text(encoding="utf-8").strip())
            fuente = archivo_crs.name
    st = ruta.stat()
    comunes = dict(
        nombre=ruta.stem,
        ruta=str(ruta),
        bytes=st.st_size,
        mtime_ns=st.st_mtime_ns,
        formato=formato,
        n_puntos=n_puntos,
    )
    if crs is None:
        return InfoBloque(
            **comunes,
            crs_wkt=None,
            fuente_crs="no encontrado",
            transformar=False,
            caja_9377=None,
            omision=C.MOTIVO_SIN_CRS,
        )
    crs_h = _crs_horizontal(crs)
    destino = pyproj.CRS.from_epsg(C.CRS_EPSG)
    transformar = not crs_h.equals(destino)
    if transformar:
        t = pyproj.Transformer.from_crs(crs_h, C.CRS_EPSG, always_xy=True)
        caja = t.transform_bounds(mins[0], mins[1], maxs[0], maxs[1], densify_pts=101)
    else:
        caja = (mins[0], mins[1], maxs[0], maxs[1])
    omision = C.MOTIVO_SIN_RGB if formato in C.FORMATOS_SIN_RGB else None
    return InfoBloque(
        **comunes,
        crs_wkt=crs_h.to_wkt(),
        fuente_crs=fuente,
        transformar=transformar,
        caja_9377=tuple(float(v) for v in caja),
        omision=omision,
    )


def maximo_rgb(ruta: str, puntos_por_trozo: int) -> int:
    """Máximo de R, G y B sobre todos los puntos del archivo, antes de cualquier filtro.

    P1: un solo máximo para los tres canales ("si ese máximo es mayor que 255").
    """
    maximo = 0
    with laspy.open(ruta) as f:
        for trozo in f.chunk_iterator(puntos_por_trozo):
            if len(trozo):
                maximo = max(  # P1: máximo común a R, G y B
                    maximo,
                    int(np.max(trozo.red)),
                    int(np.max(trozo.green)),
                    int(np.max(trozo.blue)),
                )
    return maximo


def leer_puntos_filtrados(
    info: InfoBloque, puntos_por_trozo: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """X, Y (EPSG:9377) y Z de los puntos que pasan los filtros §3.1 y §3.3, en el orden
    del archivo. El resultado no depende de ``puntos_por_trozo``."""
    maximo = maximo_rgb(info.ruta, puntos_por_trozo)
    divisor = 65535.0 if maximo > 255 else 255.0
    transformador = (
        pyproj.Transformer.from_crs(pyproj.CRS.from_wkt(info.crs_wkt), C.CRS_EPSG, always_xy=True)
        if info.transformar
        else None
    )
    xs, ys, zs = [], [], []
    n_total = n_ruido = n_vegetacion = 0
    with laspy.open(info.ruta) as f:
        for trozo in f.chunk_iterator(puntos_por_trozo):
            n = len(trozo)
            if not n:
                continue
            n_total += n
            clase = np.asarray(trozo.classification)
            sin_ruido = ~np.isin(clase, C.CLASES_RUIDO)
            n_ruido += int(n - np.count_nonzero(sin_ruido))
            r = np.asarray(trozo.red)[sin_ruido] / divisor
            g = np.asarray(trozo.green)[sin_ruido] / divisor
            b = np.asarray(trozo.blue)[sin_ruido] / divisor
            suma = r + g + b
            exg = np.zeros_like(suma)
            np.divide(2.0 * g - r - b, suma, out=exg, where=suma != 0)  # R+G+B = 0 → ExG = 0
            no_veg = ~(exg > C.EXG_UMBRAL)
            n_vegetacion += int(len(exg) - np.count_nonzero(no_veg))
            x = np.asarray(trozo.x, dtype=np.float64)[sin_ruido][no_veg]
            y = np.asarray(trozo.y, dtype=np.float64)[sin_ruido][no_veg]
            z = np.asarray(trozo.z, dtype=np.float64)[sin_ruido][no_veg]
            if transformador is not None:
                x, y = transformador.transform(x, y)  # solo X e Y; Z nunca se toca
            xs.append(np.asarray(x, dtype=np.float64))
            ys.append(np.asarray(y, dtype=np.float64))
            zs.append(z)
    vacio = np.empty(0, dtype=np.float64)
    x = np.concatenate(xs) if xs else vacio
    y = np.concatenate(ys) if ys else vacio
    z = np.concatenate(zs) if zs else vacio
    estad = {
        "puntos_archivo": n_total,
        "puntos_ruido": n_ruido,
        "puntos_vegetacion": n_vegetacion,
        "puntos_filtrados": len(x),
        "rgb_maximo": maximo,
        "rgb_divisor": int(divisor),
    }
    return x, y, z, estad
