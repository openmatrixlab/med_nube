"""Geometrías por parte y asignación de puntos (contrato §3, §3.4, §3.5 y §3.6).

- Buffers con ``quad_segs=C.BUFFER_QUAD_SEGS`` (16) y unión redonda. Se pasa siempre de
  forma explícita: ``shapely.buffer`` vectorizado usa 8 por defecto.
- "Dentro de" es ``shapely.contains_xy``: un punto sobre la frontera no cuenta.
- Las uniones se hacen siempre con los vecinos en el mismo orden (índice de la parte en
  ``huellas.gpkg``), para que el resultado no dependa de cómo se reparte el trabajo.
"""

from __future__ import annotations

import math

import numpy as np
import shapely

from . import contrato as C


def _buffer(geom, distancia: float):
    return shapely.buffer(geom, distancia, quad_segs=C.BUFFER_QUAD_SEGS)


def areas_y_anillos(tarea: dict) -> list[tuple[int, bytes | None, bytes | None]]:
    """Área efectiva A (§3.4) y anillo de suelo R (§3.5) de cada parte de la tarea.

    ``tarea``: ``partes`` (índices globales a calcular), ``vecinos`` (índices globales,
    ordenados, de todas las huellas que pueden intervenir), ``vecinos_wkb`` y
    ``vecinos_pisos``. Devuelve (índice, WKB de A, WKB de R); A y R son None si el área
    efectiva es menor de 4 m² (la parte no aparece en ninguna tabla).
    """
    vecinos = np.asarray(tarea["vecinos"])
    geoms = shapely.from_wkb(tarea["vecinos_wkb"])
    pisos = np.asarray(tarea["vecinos_pisos"])
    posicion = {int(g): i for i, g in enumerate(vecinos)}
    arbol = shapely.STRtree(geoms)
    salida = []
    for g in tarea["partes"]:
        i = posicion[int(g)]
        p = geoms[i]
        # 1. erosión
        e = _buffer(p, -C.EROSION_M)
        if shapely.is_empty(e) or shapely.area(e) < C.AREA_EROSION_MIN_M2:
            e = p
        # 2. partes más altas que se solapan más de 1 m²
        cand = arbol.query(p)
        cand = cand[pisos[cand] > pisos[i]]
        if len(cand):
            solape = shapely.area(shapely.intersection(geoms[cand], p))
            cand = cand[solape > C.SOLAPE_MIN_M2]
        if len(cand):
            altas = shapely.union_all(_buffer(geoms[np.sort(cand)], C.BUFFER_PARTE_ALTA_M))
            a = shapely.difference(e, altas)
        else:
            a = e
        # 3. mínimo
        if shapely.area(a) < C.AREA_EFECTIVA_MIN_M2:
            salida.append((int(g), None, None))
            continue
        # anillo de suelo
        exterior = _buffer(p, C.ANILLO_EXTERIOR_M)
        r = shapely.difference(exterior, _buffer(p, C.ANILLO_INTERIOR_M))
        cercanas = np.sort(arbol.query(exterior, predicate="intersects"))  # incluye a P
        r = shapely.difference(
            r, _buffer(shapely.union_all(geoms[cercanas]), C.BUFFER_HUELLAS_ANILLO_M)
        )
        salida.append((int(g), shapely.to_wkb(a), shapely.to_wkb(r)))
    return salida


def asignar(
    x: np.ndarray, y: np.ndarray, geoms: np.ndarray, partes: np.ndarray, celda: float = 10.0
) -> tuple[np.ndarray, np.ndarray]:
    """Pares (parte, índice de punto) con ``shapely.contains_xy(geom, x, y)``.

    Una rejilla preselecciona los puntos de la caja de cada geometría; la decisión final es
    siempre ``contains_xy``. Los pares salen ordenados por (parte, índice de punto).
    """
    vacio = (np.empty(0, np.int32), np.empty(0, np.int64))
    if len(x) == 0 or len(geoms) == 0:
        return vacio
    x0, y0 = float(x.min()), float(y.min())
    ix = np.floor((x - x0) / celda).astype(np.int64)
    iy = np.floor((y - y0) / celda).astype(np.int64)
    nx, ny = int(ix.max()) + 1, int(iy.max()) + 1
    clave = ix * ny + iy
    del ix, iy
    orden = np.argsort(clave, kind="stable")
    clave = clave[orden]
    shapely.prepare(geoms)
    cajas = shapely.bounds(geoms)
    res_p, res_i = [], []
    for geom, parte, (gx0, gy0, gx1, gy1) in zip(geoms, partes, cajas, strict=True):
        if shapely.is_empty(geom):
            continue
        c0 = max(math.floor((gx0 - x0) / celda), 0)
        c1 = min(math.floor((gx1 - x0) / celda), nx - 1)
        f0 = max(math.floor((gy0 - y0) / celda), 0)
        f1 = min(math.floor((gy1 - y0) / celda), ny - 1)
        if c0 > c1 or f0 > f1:
            continue
        columnas = np.arange(c0, c1 + 1, dtype=np.int64) * ny
        lo = np.searchsorted(clave, columnas + f0, side="left")
        hi = np.searchsorted(clave, columnas + f1, side="right")
        trozos = [orden[a:b] for a, b in zip(lo, hi, strict=True) if b > a]
        if not trozos:
            continue
        cand = np.concatenate(trozos)
        cx, cy = x[cand], y[cand]
        en_caja = (cx >= gx0) & (cx <= gx1) & (cy >= gy0) & (cy <= gy1)
        cand = cand[en_caja]
        dentro = shapely.contains_xy(geom, x[cand], y[cand])
        sel = cand[dentro]
        if len(sel):
            res_p.append(np.full(len(sel), parte, dtype=np.int32))
            res_i.append(sel.astype(np.int64))
    if not res_p:
        return vacio
    p = np.concatenate(res_p)
    i = np.concatenate(res_i)
    o = np.lexsort((i, p))
    return p[o], i[o]


def cobertura(area_efectiva, x: np.ndarray, y: np.ndarray) -> float:
    """Fracción de celdas de 0,5 m con centro dentro de A que tienen al menos un punto de
    techo (§3.6). La celda (i, j) cubre [0,5·i, 0,5·(i+1)) × [0,5·j, 0,5·(j+1))."""
    c = C.CELDA_COBERTURA_M
    gx0, gy0, gx1, gy1 = shapely.bounds(area_efectiva)
    i0, i1 = math.floor(gx0 / c), math.floor(gx1 / c)
    j0, j1 = math.floor(gy0 / c), math.floor(gy1 / c)
    ci = np.arange(i0, i1 + 1, dtype=np.float64) * c + c / 2
    cj = np.arange(j0, j1 + 1, dtype=np.float64) * c + c / 2
    cx, cy = np.meshgrid(ci, cj, indexing="ij")
    shapely.prepare(area_efectiva)
    centro_dentro = shapely.contains_xy(area_efectiva, cx.ravel(), cy.ravel()).reshape(cx.shape)
    total = int(np.count_nonzero(centro_dentro))
    if total == 0:
        return 0.0
    pi = np.floor(np.asarray(x) / c).astype(np.int64) - i0
    pj = np.floor(np.asarray(y) / c).astype(np.int64) - j0
    ok = (pi >= 0) & (pi < cx.shape[0]) & (pj >= 0) & (pj < cx.shape[1])
    ocupada = np.zeros(cx.shape, dtype=bool)
    ocupada[pi[ok], pj[ok]] = True
    return int(np.count_nonzero(ocupada & centro_dentro)) / total
