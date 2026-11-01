"""Pruebas propias de geometrías por parte, asignación de puntos y cobertura."""

from __future__ import annotations

import numpy as np
import pytest
import shapely
from shapely.geometry import box

from med_nube.proc_geometria import areas_y_anillos, asignar, cobertura


def _tarea(geoms, pisos):
    geoms = np.array(geoms, dtype=object)
    idx = np.arange(len(geoms))
    return {
        "partes": idx,
        "vecinos": idx,
        "vecinos_wkb": shapely.to_wkb(geoms),
        "vecinos_pisos": np.asarray(pisos),
    }


def test_asignar_igual_a_contains_xy_punto_por_punto():
    rng = np.random.default_rng(5)
    geoms = np.array(
        [
            shapely.Point(10, 10).buffer(4),
            box(0, 0, 6, 3),
            box(14, 2, 30, 9).difference(box(18, 4, 22, 6)),
            shapely.Point(25, 25).buffer(6).difference(shapely.Point(25, 25).buffer(2)),
        ],
        dtype=object,
    )
    partes = np.array([7, 3, 11, 2])
    x = np.concatenate([rng.uniform(-5, 40, 20000), [0.0, 3.0, 6.0]])  # incluye bordes
    y = np.concatenate([rng.uniform(-5, 40, 20000), [1.0, 0.0, 2.0]])
    p, i = asignar(x, y, geoms, partes, celda=3.0)
    esperado = sorted(
        (int(pp), int(k))
        for g, pp in zip(geoms, partes, strict=True)
        for k in np.flatnonzero(shapely.contains_xy(g, x, y))
    )
    assert sorted(zip(p.tolist(), i.tolist(), strict=True)) == esperado
    assert list(zip(p, i, strict=True)) == sorted(zip(p, i, strict=True))  # ordenados


def test_punto_en_el_borde_no_cuenta():
    p, _ = asignar(
        np.array([0.0, 1.0]), np.array([1.0, 1.0]), np.array([box(0, 0, 2, 2)]), np.array([0])
    )
    assert len(p) == 1  # solo el interior (1, 1)


def test_cobertura():
    a = box(0, 0, 10, 10)
    x, y = np.meshgrid(np.arange(0.1, 5, 0.5), np.arange(0.1, 10, 0.5))
    assert cobertura(a, x.ravel(), y.ravel()) == pytest.approx(0.5)
    # sin ningún centro de celda dentro de A
    assert cobertura(box(0.3, 0.3, 0.45, 0.45), np.array([0.4]), np.array([0.4])) == 0.0


def test_area_efectiva_y_anillo():
    podio, torre, vecina = box(0, 0, 20, 20), box(7, 7, 13, 13), box(26, 0, 40, 20)
    diminuta = box(50, 50, 51.8, 51.8)
    res = {
        g: (a, r)
        for g, a, r in areas_y_anillos(_tarea([podio, torre, vecina, diminuta], [1, 10, 2, 1]))
    }
    a_podio = shapely.from_wkb(res[0][0])
    # la torre (más alta y solapada) sale del área efectiva del podio, con su buffer de 0,30
    assert not shapely.intersects(a_podio, torre.buffer(0.29))
    # la diminuta queda por debajo de 4 m² de área efectiva: no aparece
    assert res[3] == (None, None)
    # el anillo del podio no entra en la vecina (ni a 0,20 m de ella) ni en el propio podio
    anillo = shapely.from_wkb(res[0][1])
    assert not shapely.intersects(anillo, vecina.buffer(0.19))
    assert not shapely.intersects(anillo, podio.buffer(0.99))
    # el anillo de la torre cae entero dentro del podio: vacío
    assert shapely.is_empty(shapely.from_wkb(res[1][1]))
