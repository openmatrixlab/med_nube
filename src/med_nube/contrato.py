"""Constantes del contrato de entrega (fuente única de verdad).

Ver docs/contrato.md. Si este archivo y el documento difieren, manda este archivo.
NO MODIFICAR sin aprobación de Luis (cambiar el contrato rompe med_texture).
"""

from __future__ import annotations

VERSION_CONTRATO = "1.0"

CRS_EPSG = 9377
HUELLAS_CAPA = "huellas"
HUELLAS_SHA256 = "dc50e37f65c4fa64715b37c3e8c7129216edaa3252cb3d8cd5e984beca3b4f12"

# --- 3.1 lectura -------------------------------------------------------------
CLASES_RUIDO = (7, 18)

# --- 3.3 vegetación ----------------------------------------------------------
EXG_UMBRAL = 0.10

# --- 3.4 área efectiva -------------------------------------------------------
EROSION_M = 0.30
BUFFER_PARTE_ALTA_M = 0.30
SOLAPE_MIN_M2 = 1.0
AREA_EROSION_MIN_M2 = 1.0
AREA_EFECTIVA_MIN_M2 = 4.0

# --- 3.5 anillo de suelo -----------------------------------------------------
ANILLO_INTERIOR_M = 1.0
ANILLO_EXTERIOR_M = 5.0
BUFFER_HUELLAS_ANILLO_M = 0.20
PERCENTIL_SUELO = 25
MIN_PUNTOS_SUELO = 10

# --- 3.6 alturas -------------------------------------------------------------
MIN_PUNTOS_TECHO = 20
CELDA_COBERTURA_M = 0.5

# --- 3.7 techos --------------------------------------------------------------
MIN_PUNTOS_TECHOS = 50
MIN_COBERTURA_TECHOS = 0.5
RANSAC_SEMILLA = 42
RANSAC_ITERACIONES = 500
RANSAC_TOLERANCIA_M = 0.10
RANSAC_PENDIENTE_MAX_DEG = 70.0
RANSAC_MIN_INLIERS_ABS = 15
RANSAC_MIN_INLIERS_FRAC = 0.10
RANSAC_MAX_PLANOS = 4
PENDIENTE_PLANO_DEG = 5.0
FRAC_PLANO_DOMINANTE = 0.60
OPUESTOS_MIN_DEG = 150.0
OPUESTOS_MAX_DEG = 210.0

FORMAS = ("plano", "una_agua", "dos_aguas", "cuatro_aguas", "otro")

# --- 3.8 / 4 formato ---------------------------------------------------------
# columna -> (tipo SQLite, admite NULL)
COLUMNAS_ALTURAS: dict[str, tuple[str, bool]] = {
    "id_parte": ("TEXT", False),
    "bloque": ("TEXT", False),
    "n_puntos": ("INTEGER", False),
    "cobertura": ("REAL", False),
    "z_p10": ("REAL", False),
    "z_p50": ("REAL", False),
    "z_p90": ("REAL", False),
    "z_p98": ("REAL", False),
    "z_max": ("REAL", False),
    "n_puntos_suelo": ("INTEGER", False),
    "z_suelo": ("REAL", True),
    "h_p50": ("REAL", True),
    "h_p98": ("REAL", True),
}

COLUMNAS_TECHOS: dict[str, tuple[str, bool]] = {
    "id_parte": ("TEXT", False),
    "forma": ("TEXT", False),
    "n_planos": ("INTEGER", False),
    "pendiente_deg": ("REAL", True),
    "azimut_caida_deg": ("REAL", True),
    "azimut_cumbrera_deg": ("REAL", True),
    "frac_inliers": ("REAL", False),
    "rmse_m": ("REAL", True),
}

COLUMNAS_METADATOS: dict[str, tuple[str, bool]] = {
    "clave": ("TEXT", False),
    "valor": ("TEXT", False),
}

TABLAS = {
    "alturas": COLUMNAS_ALTURAS,
    "techos": COLUMNAS_TECHOS,
    "metadatos": COLUMNAS_METADATOS,
}

CLAVES_METADATOS = (
    "version_contrato",
    "fecha_proceso",
    "commit",
    "huellas_sha256",
    "bloques",
    "bloques_omitidos",
    "bloques_advertencias",
)

# --- 5 aceptación ------------------------------------------------------------
COLTEJER_ID = "cat20250121:1466693"
COLTEJER_H_P98_MIN = 120.0
COLTEJER_H_P98_MAX = 190.0
