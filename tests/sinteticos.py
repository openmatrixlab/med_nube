"""Escenario sintético para las pruebas de aceptación.

Construye `huellas.gpkg` y tres bloques LAS con resultados conocidos de antemano.
NO MODIFICAR: es parte del contrato.

Partes (EPSG:9377, X0/Y0 = esquina del escenario, suelo a z = 1500):

| id_parte | huella | pisos | techo |
|---|---|---|---|
| t:plana | 10×10 m | 3 | plano a 1509 (+ ruido clase 7 a 1600) |
| t:dos_aguas | 12×8 m, cumbrera N–S | 2 | aleros 1506, pendiente 30° |
| t:podio | 20×20 m | 1 | plano a 1503, contiene a la torre |
| t:torre | 6×6 m dentro del podio | 10 | plano a 1530 |
| t:arbol | 10×10 m | 2 | plano a 1506, ~28 % tapado por copa verde |
| t:utm | 8×8 m | 2 | plano a 1504, solo en el bloque B (UTM 18N) |
| t:sin_puntos | 10×10 m fuera de toda nube | 2 | — |
| t:diminuta | 1,8×1,8 m | 1 | plano a 1503 (área efectiva < 4 m²) |

Bloques: A_9377 (EPSG:9377, RGB 16 bit), B_utm (EPSG:32618, RGB 8 bit),
C_sin_crs (sin CRS: debe omitirse).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import laspy
import numpy as np
import pyproj
import shapely
from shapely.geometry import MultiPolygon, box

X0, Y0 = 4716000.0, 2249000.0
Z_SUELO = 1500.0
DENS_TECHO = 50.0  # pts/m²
DENS_SUELO = 20.0
RUIDO = 0.02
TAN30 = np.tan(np.radians(30.0))

HUELLAS = {
    "t:plana": (box(X0 + 10, Y0 + 10, X0 + 20, Y0 + 20), 3),
    "t:dos_aguas": (box(X0 + 40, Y0 + 10, X0 + 52, Y0 + 18), 2),
    "t:podio": (box(X0 + 10, Y0 + 40, X0 + 30, Y0 + 60), 1),
    "t:torre": (box(X0 + 17, Y0 + 47, X0 + 23, Y0 + 53), 10),
    "t:arbol": (box(X0 + 60, Y0 + 40, X0 + 70, Y0 + 50), 2),
    "t:utm": (box(X0 + 40, Y0 + 30, X0 + 48, Y0 + 38), 2),
    "t:sin_puntos": (box(X0 + 200, Y0 + 200, X0 + 210, Y0 + 210), 2),
    "t:diminuta": (box(X0 + 70, Y0 + 10, X0 + 71.8, Y0 + 11.8), 1),
}
ARBOL_CENTRO, ARBOL_RADIO = (X0 + 63.0, Y0 + 43.0), 3.0
DOMINIO_A = box(X0, Y0, X0 + 80, Y0 + 70)
DOMINIO_B = box(X0 + 34, Y0 + 24, X0 + 54, Y0 + 44)

GRIS = (120, 120, 120)
TEJA = (170, 90, 70)
VERDE = (60, 140, 50)


def _muestrear(rng, geom, densidad):
    """Puntos uniformes dentro de geom (rechazo sobre el bbox)."""
    xmin, ymin, xmax, ymax = geom.bounds
    n = rng.poisson(densidad * (xmax - xmin) * (ymax - ymin))
    x = rng.uniform(xmin, xmax, n)
    y = rng.uniform(ymin, ymax, n)
    dentro = shapely.contains_xy(geom, x, y)
    return x[dentro], y[dentro]


def _techo(rng, geom, z_fn, rgb, excluir=None):
    if excluir is not None:
        geom = geom.difference(excluir)
    x, y = _muestrear(rng, geom, DENS_TECHO)
    z = z_fn(x, y) + rng.normal(0, RUIDO, len(x))
    return x, y, z, np.tile(rgb, (len(x), 1)), np.ones(len(x), "u1")


def _plano(cota):
    return lambda x, y: np.full(len(x), cota)


def _juntar(partes):
    return tuple(np.concatenate([p[i] for p in partes]) for i in range(5))


def puntos_bloque_a(rng):
    torre = HUELLAS["t:torre"][0]
    copa = shapely.Point(ARBOL_CENTRO).buffer(ARBOL_RADIO, 64)
    huellas_a = [g for k, (g, _) in HUELLAS.items() if k not in ("t:utm", "t:sin_puntos")]
    partes = [
        _techo(rng, HUELLAS["t:plana"][0], _plano(Z_SUELO + 9.0), GRIS),
        _techo(
            rng,
            HUELLAS["t:dos_aguas"][0],
            lambda x, y: Z_SUELO + 6.0 + (6.0 - np.abs(x - (X0 + 46.0))) * TAN30,
            TEJA,
        ),
        _techo(rng, HUELLAS["t:podio"][0], _plano(Z_SUELO + 3.0), GRIS, excluir=torre),
        _techo(rng, torre, _plano(Z_SUELO + 30.0), GRIS),
        _techo(rng, HUELLAS["t:arbol"][0], _plano(Z_SUELO + 6.0), GRIS, excluir=copa),
        _techo(rng, HUELLAS["t:diminuta"][0], _plano(Z_SUELO + 3.0), GRIS),
    ]
    # copa del árbol (verde, por encima del techo)
    xc, yc = _muestrear(rng, copa, DENS_TECHO)
    zc = rng.uniform(Z_SUELO + 10.0, Z_SUELO + 14.0, len(xc))
    partes.append((xc, yc, zc, np.tile(VERDE, (len(xc), 1)), np.ones(len(xc), "u1")))
    # ruido clase 7 sobre t:plana
    xr, yr = _muestrear(rng, HUELLAS["t:plana"][0].buffer(-1), 0.5)
    partes.append(
        (xr, yr, np.full(len(xr), 1600.0), np.tile(GRIS, (len(xr), 1)), np.full(len(xr), 7, "u1"))
    )
    # suelo
    suelo = DOMINIO_A.difference(shapely.union_all([*huellas_a, HUELLAS["t:utm"][0]]))
    xs, ys = _muestrear(rng, suelo, DENS_SUELO)
    zs = Z_SUELO + rng.normal(0, RUIDO, len(xs))
    partes.append((xs, ys, zs, np.tile(GRIS, (len(xs), 1)), np.full(len(xs), 2, "u1")))
    return _juntar(partes)


def puntos_bloque_b(rng):
    utm = HUELLAS["t:utm"][0]
    techo = _techo(rng, utm, _plano(Z_SUELO + 4.0), TEJA)
    suelo = DOMINIO_B.difference(
        shapely.union_all([utm, HUELLAS["t:dos_aguas"][0], HUELLAS["t:podio"][0]])
    )
    xs, ys = _muestrear(rng, suelo, DENS_SUELO)
    zs = Z_SUELO + rng.normal(0, RUIDO, len(xs))
    return _juntar([techo, (xs, ys, zs, np.tile(GRIS, (len(xs), 1)), np.full(len(xs), 2, "u1"))])


def _escribir_las(ruta: Path, x, y, z, rgb, clase, crs: pyproj.CRS | None, bits16: bool):
    cab = laspy.LasHeader(point_format=3, version="1.2")
    cab.scales = np.array([0.001, 0.001, 0.001])
    cab.offsets = np.array([np.floor(x.min()), np.floor(y.min()), np.floor(z.min())])
    if crs is not None:
        cab.add_crs(crs)
    las = laspy.LasData(cab)
    las.x, las.y, las.z = x, y, z
    escala = 256 if bits16 else 1
    las.red, las.green, las.blue = (rgb[:, i].astype("u2") * escala for i in range(3))
    las.classification = clase
    las.write(ruta)


def construir(carpeta: Path, semilla: int = 7) -> tuple[Path, Path]:
    """Escribe huellas.gpkg y la carpeta nubes/ con los tres bloques. Devuelve rutas."""
    carpeta = Path(carpeta)
    nubes = carpeta / "nubes"
    nubes.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(semilla)

    huellas = gpd.GeoDataFrame(
        {
            "id_parte": list(HUELLAS),
            "cbml": ["01010010001"] * len(HUELLAS),
            "tipo": ["N"] * len(HUELLAS),
            "pisos": [p for _, p in HUELLAS.values()],
        },
        geometry=[MultiPolygon([g]) for g, _ in HUELLAS.values()],
        crs=9377,
    )
    ruta_huellas = carpeta / "huellas.gpkg"
    huellas.to_file(ruta_huellas, layer="huellas", driver="GPKG")

    crs_9377 = pyproj.CRS.from_epsg(9377)
    _escribir_las(nubes / "A_9377.las", *puntos_bloque_a(rng), crs_9377, bits16=True)

    x, y, z, rgb, clase = puntos_bloque_b(rng)
    a_utm = pyproj.Transformer.from_crs(9377, 32618, always_xy=True)
    xu, yu = a_utm.transform(x, y)
    _escribir_las(nubes / "B_utm.las", xu, yu, z, rgb, clase, pyproj.CRS.from_epsg(32618), False)

    # bloque sin CRS: un techo cualquiera; debe omitirse
    xs, ys = _muestrear(rng, HUELLAS["t:plana"][0], 5.0)
    _escribir_las(
        nubes / "C_sin_crs.las",
        xs,
        ys,
        np.full(len(xs), 2000.0),
        np.tile(GRIS, (len(xs), 1)),
        np.ones(len(xs), "u1"),
        None,
        False,
    )
    return ruta_huellas, nubes
