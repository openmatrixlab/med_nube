"""Pruebas propias del ajuste de planos y la forma del techo (contrato §3.7)."""

from __future__ import annotations

import numpy as np
import pytest

from med_nube.proc_ransac import (
    _modulo,
    ajustar_planos,
    azimut_interseccion_deg,
    describir_techo,
)

TAN30 = np.tan(np.radians(30.0))


def _malla(x0, x1, y0, y1, paso=0.25):
    xs, ys = np.meshgrid(np.arange(x0, x1, paso), np.arange(y0, y1, paso))
    return xs.ravel(), ys.ravel()


def _ruido(n, semilla=1, sigma=0.01):
    return np.random.default_rng(semilla).normal(0, sigma, n)


def _techo(xyz):
    planos, total = ajustar_planos(xyz)
    return describir_techo(planos, total)


def test_plano_horizontal():
    x, y = _malla(0, 10, 0, 10)
    z = 1500 + _ruido(len(x))
    t = _techo(np.column_stack([x, y, z]))
    assert t["forma"] == "plano" and t["n_planos"] == 1
    assert t["pendiente_deg"] < 1.0
    assert t["azimut_caida_deg"] is None and t["azimut_cumbrera_deg"] is None
    assert t["frac_inliers"] == pytest.approx(1.0)
    assert 0 <= t["rmse_m"] <= 0.10


def test_una_agua_cae_al_norte():
    x, y = _malla(0, 10, 0, 8)
    z = 1500 + (8 - y) * np.tan(np.radians(20)) + _ruido(len(x))  # baja hacia +y (norte)
    t = _techo(np.column_stack([x, y, z]))
    assert t["forma"] == "una_agua"
    assert t["pendiente_deg"] == pytest.approx(20.0, abs=1.0)
    assert min(t["azimut_caida_deg"], 360 - t["azimut_caida_deg"]) <= 2.0


def test_dos_aguas_cumbrera_este_oeste():
    x, y = _malla(0, 12, 0, 8)
    z = 1500 + (4 - np.abs(y - 4)) * TAN30 + _ruido(len(x))  # cumbrera en y = 4
    t = _techo(np.column_stack([x, y, z]))
    assert t["forma"] == "dos_aguas" and t["n_planos"] == 2
    assert t["pendiente_deg"] == pytest.approx(30.0, abs=1.5)
    assert t["azimut_cumbrera_deg"] == pytest.approx(90.0, abs=2.0)  # E–O


def test_cuatro_aguas():
    x, y = _malla(0, 12, 0, 12)
    z = 1500 + (6 - np.maximum(np.abs(x - 6), np.abs(y - 6))) * TAN30 + _ruido(len(x))
    t = _techo(np.column_stack([x, y, z]))
    assert t["forma"] == "cuatro_aguas" and t["n_planos"] == 4
    assert t["azimut_cumbrera_deg"] is not None


def test_pared_no_cuenta_como_plano():
    x, y = _malla(0, 10, 0, 10)
    techo = np.column_stack([x, y, 1500 + _ruido(len(x))])
    # pared con el 20 % de los puntos: suficientes para un candidato (≥ mínimo), y > 70°
    zp, yp = np.meshgrid(np.arange(1490, 1500, 0.5), np.arange(0, 10, 0.5))
    pared = np.column_stack([np.full(zp.size, 5.0), yp.ravel(), zp.ravel()])
    t = _techo(np.vstack([techo, pared]))
    assert t["n_planos"] == 1 and t["forma"] == "plano"
    assert t["pendiente_deg"] < 1.0
    assert t["frac_inliers"] == pytest.approx(len(techo) / (len(techo) + len(pared)), abs=0.01)


def test_plano_dominante_exige_60_por_ciento():
    # techo horizontal con solo el 14 % de los puntos: regla 2 no aplica → "otro" (regla 6)
    x, y = _malla(0, 10, 0, 10)
    techo = np.column_stack([x, y, 1500 + _ruido(len(x))])
    zp, yp = np.meshgrid(np.arange(1490, 1500, 0.1), np.arange(0, 10, 0.1))
    pared = np.column_stack([np.full(zp.size, 5.0), yp.ravel(), zp.ravel()])
    t = _techo(np.vstack([techo, pared]))
    assert t["n_planos"] == 1 and t["forma"] == "otro" and t["pendiente_deg"] < 1.0


def test_sin_planos():
    xyz = np.random.default_rng(3).uniform(0, 10, (60, 3))  # nube sin estructura
    t = _techo(xyz)
    assert t["n_planos"] == 0 and t["forma"] == "otro"
    assert t["frac_inliers"] == 0.0 and t["rmse_m"] is None and t["pendiente_deg"] is None


def test_no_depende_del_orden_de_los_puntos():
    x, y = _malla(0, 12, 0, 8)
    xyz = np.column_stack([x, y, 1500 + (4 - np.abs(y - 4)) * TAN30 + _ruido(len(x))])
    permutado = xyz[np.random.default_rng(9).permutation(len(xyz))]
    assert _techo(xyz) == _techo(permutado)


def test_azimuts_en_rango():
    assert _modulo(-1e-17, 360.0) == 0.0
    assert 0.0 <= _modulo(-1e-17, 180.0) < 180.0
    n1 = np.array([0.5, 0.0, np.sqrt(0.75)])
    n2 = np.array([-0.5, 0.0, np.sqrt(0.75)])
    assert azimut_interseccion_deg(n1, n2) == pytest.approx(0.0, abs=1e-9)
