"""Búsqueda del tramo de cada parte en la caché: mismo resultado sin copiar el arreglo.

Con una clave int64 sobre un arreglo int32, NumPy convierte el arreglo completo en cada
búsqueda; en un bloque de cientos de millones de pares eso agota la memoria."""

from __future__ import annotations

import tracemalloc

import numpy as np

from med_nube.proc_bloque import _tramo


def test_tramo_correcto_y_sin_copiar(tmp_path):
    rng = np.random.default_rng(7)
    partes = np.sort(rng.integers(0, 50_000, 2_000_000)).astype(np.int32)
    np.save(tmp_path / "p.npy", partes)
    mapa = np.load(tmp_path / "p.npy", mmap_mode="r")
    for parte in (np.int64(0), np.int64(12_345), 49_999, np.int64(60_000)):
        esperado = np.flatnonzero(partes == int(parte))
        tramo = _tramo(mapa, parte)
        if len(esperado):
            assert (tramo.start, tramo.stop) == (esperado[0], esperado[-1] + 1)
        else:
            assert tramo.start == tramo.stop
    tracemalloc.start()
    try:
        _tramo(mapa, np.int64(12_345))
        pico = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert pico < partes.nbytes // 10  # una copia int64 serían 16 MB
