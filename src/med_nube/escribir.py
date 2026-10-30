"""Escritura de la entrega en el formato exacto del contrato (§3.8 y §4).

Usar SIEMPRE esta función para escribir la entrega; no escribir el GeoPackage a mano.
NO MODIFICAR sin aprobación de Luis.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio

from . import contrato as C
from .validar import sha256

_DTYPES = {"TEXT": "object", "INTEGER": "int64", "REAL": "float64"}


def _tabla(df: pd.DataFrame, columnas: dict[str, tuple[str, bool]], nombre: str) -> pd.DataFrame:
    faltan = [c for c in columnas if c not in df.columns]
    sobran = [c for c in df.columns if c not in columnas]
    if faltan or sobran:
        raise ValueError(f"'{nombre}': faltan {faltan}, sobran {sobran}")
    salida = pd.DataFrame(index=range(len(df)))
    for col, (tipo, nulo) in columnas.items():
        serie = df[col].reset_index(drop=True)
        if tipo == "INTEGER":
            if serie.isna().any():
                raise ValueError(f"'{nombre}.{col}': INTEGER no admite NULL")
            serie = serie.astype("int64")
        elif tipo == "REAL":
            serie = pd.to_numeric(serie, errors="raise").astype("float64")
            if not nulo and serie.isna().any():
                raise ValueError(f"'{nombre}.{col}': no admite NULL")
            if np.isinf(serie).any():
                raise ValueError(f"'{nombre}.{col}': valores infinitos")
        else:
            if not nulo and serie.isna().any():
                raise ValueError(f"'{nombre}.{col}': no admite NULL")
            serie = serie.astype("object")
        salida[col] = serie
    return salida


def commit_actual(repo: Path | None = None) -> str:
    """Hash del commit de med_nube; falla si hay cambios sin commit en src/."""
    repo = repo or Path(__file__).resolve().parents[2]
    sucio = subprocess.run(
        ["git", "status", "--porcelain", "--", "src"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if sucio:
        raise RuntimeError("Hay cambios sin commit en src/: haga commit antes de procesar.")
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def escribir_entrega(
    alturas: pd.DataFrame,
    techos: pd.DataFrame,
    huellas: Path,
    bloques: list[str],
    bloques_omitidos: dict[str, str],
    bloques_advertencias: dict[str, list[str]],
    carpeta: Path,
    fecha: datetime | None = None,
    commit: str | None = None,
) -> Path:
    """Escribe med_nube_entrega_<AAAAMMDD>.gpkg en `carpeta` y devuelve su ruta."""
    fecha = (fecha or datetime.now().astimezone()).replace(microsecond=0)
    if fecha.tzinfo is None:
        raise ValueError("fecha debe tener zona horaria")
    metadatos = {
        "version_contrato": C.VERSION_CONTRATO,
        "fecha_proceso": fecha.isoformat(),
        "commit": commit or commit_actual(),
        "huellas_sha256": sha256(Path(huellas)),
        "bloques": json.dumps(sorted(bloques), ensure_ascii=False),
        "bloques_omitidos": json.dumps(bloques_omitidos, ensure_ascii=False, sort_keys=True),
        "bloques_advertencias": json.dumps(
            bloques_advertencias, ensure_ascii=False, sort_keys=True
        ),
    }
    tablas = {
        "alturas": _tabla(alturas, C.COLUMNAS_ALTURAS, "alturas"),
        "techos": _tabla(techos, C.COLUMNAS_TECHOS, "techos"),
        "metadatos": pd.DataFrame(
            {"clave": list(metadatos), "valor": list(metadatos.values())}, dtype="object"
        ),
    }
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"med_nube_entrega_{fecha:%Y%m%d}.gpkg"
    if ruta.exists():
        ruta.unlink()
    for nombre, df in tablas.items():
        pyogrio.write_dataframe(df, ruta, layer=nombre, driver="GPKG")
    return ruta
