"""Ajuste de planos de techo y forma (contrato §3.7).

RANSAC secuencial y determinístico, tal como lo describe el contrato:

- orden canónico ``numpy.lexsort((z, y, x))`` y centrado restando la media;
- ``numpy.random.default_rng(42)`` nuevo por parte;
- 500 iteraciones por plano, cada una con exactamente una llamada
  ``rng.choice(len(restantes), 3, replace=False)``;
- reajuste por SVD, recálculo de inliers, descarte de paredes (> 70°) y tope de 4 planos.

Las 500 tríadas de cada ronda se sacan primero, en orden, con sus 500 llamadas a
``rng.choice``; después se evalúan juntas con numpy. El resultado es el mismo que
evaluarlas una por una: el ganador es el primero con más inliers (comparación estricta).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import contrato as C

# Elementos (puntos × candidatos) por lote al contar inliers: acota la memoria.
_ELEMENTOS_POR_LOTE = 4_000_000


@dataclass
class Plano:
    normal: np.ndarray  # unitaria, con nz >= 0
    n_inliers: int
    distancias: np.ndarray  # distancia de cada inlier a este plano


def _modulo(valor: float, m: float) -> float:
    """``valor mod m`` en [0, m). Evita que el redondeo de ``-1e-17 % 360`` dé 360."""
    r = valor % m
    return 0.0 if r >= m else r


def pendiente_deg(n: np.ndarray) -> float:
    return math.degrees(math.acos(min(1.0, max(-1.0, float(n[2])))))


def azimut_caida_deg(n: np.ndarray) -> float:
    return _modulo(math.degrees(math.atan2(float(n[0]), float(n[1]))), 360.0)


def azimut_interseccion_deg(n1: np.ndarray, n2: np.ndarray) -> float:
    d = np.cross(n1, n2)
    return _modulo(math.degrees(math.atan2(float(d[0]), float(d[1]))), 180.0)


def _opuestos(a: float, b: float) -> bool:
    """Diferencia angular de dos azimuts de caída dentro de [150°, 210°]."""
    return C.OPUESTOS_MIN_DEG <= abs(a - b) <= C.OPUESTOS_MAX_DEG


def _contar_inliers(q: np.ndarray, a: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Para cada candidato k: puntos de q con |(p − a_k)·u_k| ≤ tolerancia."""
    m, k = len(q), len(a)
    conteos = np.empty(k, dtype=np.int64)
    paso = max(1, _ELEMENTOS_POR_LOTE // max(m, 1))
    qx, qy, qz = q[:, 0:1], q[:, 1:2], q[:, 2:3]
    for i in range(0, k, paso):
        s = slice(i, i + paso)
        d = (qx - a[s, 0]) * u[s, 0] + (qy - a[s, 1]) * u[s, 1] + (qz - a[s, 2]) * u[s, 2]
        conteos[s] = np.count_nonzero(np.abs(d) <= C.RANSAC_TOLERANCIA_M, axis=0)
    return conteos


def ajustar_planos(xyz: np.ndarray) -> tuple[list[Plano], int]:
    """Planos aceptados (ordenados por inliers, de mayor a menor) y total de puntos T."""
    xyz = np.asarray(xyz, dtype=np.float64)
    orden = np.lexsort((xyz[:, 2], xyz[:, 1], xyz[:, 0]))
    p = xyz[orden]
    p = p - p.mean(axis=0)
    total = len(p)
    minimo = max(C.RANSAC_MIN_INLIERS_ABS, C.RANSAC_MIN_INLIERS_FRAC * total)
    restantes = np.arange(total)
    rng = np.random.default_rng(C.RANSAC_SEMILLA)
    aceptados: list[Plano] = []

    while len(aceptados) < C.RANSAC_MAX_PLANOS and len(restantes) >= C.RANSAC_MIN_INLIERS_ABS:
        q = p[restantes]
        # 1. 500 iteraciones, cada una con exactamente una llamada a rng.choice
        triadas = np.empty((C.RANSAC_ITERACIONES, 3), dtype=np.int64)
        for it in range(C.RANSAC_ITERACIONES):
            triadas[it] = rng.choice(len(restantes), 3, replace=False)
        a, b, c = q[triadas[:, 0]], q[triadas[:, 1]], q[triadas[:, 2]]
        n = np.cross(b - a, c - a)
        norma = np.linalg.norm(n, axis=1)
        validas = norma >= 1e-9  # ‖n‖ < 1e-9: tríada degenerada, sin candidato
        if not validas.any():
            break
        conteos = np.full(C.RANSAC_ITERACIONES, -1, dtype=np.int64)
        iv = np.flatnonzero(validas)
        u = n[iv] / norma[iv, None]
        conteos[iv] = _contar_inliers(q, a[iv], u)
        ganador = int(np.argmax(conteos))  # el primero con más inliers (estricto >)
        k = int(np.searchsorted(iv, ganador))
        d_ganador = (
            (q[:, 0] - a[ganador, 0]) * u[k, 0]
            + (q[:, 1] - a[ganador, 1]) * u[k, 1]
            + (q[:, 2] - a[ganador, 2]) * u[k, 2]
        )
        inliers = q[np.abs(d_ganador) <= C.RANSAC_TOLERANCIA_M]

        # 2. reajuste por SVD
        c0 = inliers.mean(axis=0)
        _, _, vt = np.linalg.svd(inliers - c0, full_matrices=False)
        normal = vt[-1].copy()
        if normal[2] < 0:
            normal = -normal

        # 3. recálculo de inliers sobre restantes
        dist = np.abs(
            (q[:, 0] - c0[0]) * normal[0]
            + (q[:, 1] - c0[1]) * normal[1]
            + (q[:, 2] - c0[2]) * normal[2]
        )
        mascara = dist <= C.RANSAC_TOLERANCIA_M
        n_in = int(np.count_nonzero(mascara))

        # 4. menos que el mínimo: termina
        if n_in < minimo:
            break
        # 5. pared o ruido: se retiran sus inliers y no cuenta para el tope
        if pendiente_deg(normal) > C.RANSAC_PENDIENTE_MAX_DEG:
            restantes = restantes[~mascara]
            continue
        # 6. plano aceptado
        aceptados.append(Plano(normal=normal, n_inliers=n_in, distancias=dist[mascara]))
        restantes = restantes[~mascara]

    # orden final: por inliers, de mayor a menor; sorted es estable (empate: el primero)
    aceptados = sorted(aceptados, key=lambda pl: -pl.n_inliers)
    return aceptados, total


def describir_techo(planos: list[Plano], total: int) -> dict:
    """Columnas de la tabla ``techos`` (salvo id_parte) a partir de los planos."""
    if not planos:
        return {
            "forma": "otro",
            "n_planos": 0,
            "pendiente_deg": None,
            "azimut_caida_deg": None,
            "azimut_cumbrera_deg": None,
            "frac_inliers": 0.0,
            "rmse_m": None,
        }
    pend = [pendiente_deg(pl.normal) for pl in planos]
    caida = [azimut_caida_deg(pl.normal) for pl in planos]
    inclinado = [s >= C.PENDIENTE_PLANO_DEG for s in pend]
    n = len(planos)

    if not inclinado[0] and planos[0].n_inliers / total >= C.FRAC_PLANO_DOMINANTE:
        forma = "plano"
    elif n == 1 and inclinado[0]:
        forma = "una_agua"
    elif n == 2 and all(inclinado) and _opuestos(caida[0], caida[1]):
        forma = "dos_aguas"
    elif n in (3, 4) and all(inclinado):
        forma = "cuatro_aguas"
    else:
        forma = "otro"

    cumbrera = None
    if forma == "dos_aguas":
        cumbrera = azimut_interseccion_deg(planos[0].normal, planos[1].normal)
    elif forma == "cuatro_aguas":
        for i in range(n):
            for j in range(i + 1, n):
                if cumbrera is None and _opuestos(caida[i], caida[j]):
                    cumbrera = azimut_interseccion_deg(planos[i].normal, planos[j].normal)

    distancias = np.concatenate([pl.distancias for pl in planos])
    return {
        "forma": forma,
        "n_planos": n,
        "pendiente_deg": pend[0],
        "azimut_caida_deg": caida[0] if inclinado[0] else None,
        "azimut_cumbrera_deg": cumbrera,
        "frac_inliers": sum(pl.n_inliers for pl in planos) / total,
        "rmse_m": float(np.sqrt(np.mean(distancias**2))),
    }
