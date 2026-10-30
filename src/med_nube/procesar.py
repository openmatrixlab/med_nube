"""Procesamiento: nubes de puntos + huellas → tablas `alturas` y `techos`.

>>> ESTE ES EL ÚNICO MÓDULO QUE HAY QUE IMPLEMENTAR (puede dividirse en módulos
>>> auxiliares dentro de src/med_nube/). Reglas exactas en docs/contrato.md §3.

Interfaz obligatoria (las pruebas de tests/test_aceptacion.py la usan tal cual):

    procesar(huellas, nubes, salida, commit=None) -> Path

- `huellas`: GeoPackage con la capa `huellas` (oficial o huellas_coltejer.gpkg).
- `nubes`: carpeta con los bloques *.las / *.laz (no recursiva) o lista de rutas.
- `salida`: carpeta donde se escribe med_nube_entrega_<AAAAMMDD>.gpkg.
- `commit`: solo para pruebas; en producción se toma de git (escribir.commit_actual).

Debe terminar llamando a `escribir.escribir_entrega(...)` y devolver su ruta.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path


def procesar(
    huellas: Path,
    nubes: Path | Sequence[Path],
    salida: Path,
    commit: str | None = None,
) -> Path:
    raise NotImplementedError("Implementar según docs/contrato.md §3")
