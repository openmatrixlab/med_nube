"""Procesamiento: nubes de puntos + huellas → tablas `alturas` y `techos`.

>>> ESTE ES EL ÚNICO MÓDULO QUE HAY QUE IMPLEMENTAR. Puede apoyarse en módulos
>>> nuevos src/med_nube/proc_*.py (ver AGENTS.md). Reglas exactas: docs/contrato.md §3.

Interfaz obligatoria (las pruebas de tests/test_aceptacion.py la usan tal cual):

    procesar(huellas, nubes, salida, commit=None) -> Path

- `huellas`: GeoPackage con la capa `huellas` (oficial o huellas_coltejer.gpkg).
- `nubes`: carpeta con los bloques *.las / *.laz (no recursiva) o lista de rutas.
- `salida`: carpeta donde se escribe med_nube_entrega_<AAAAMMDD>.gpkg.
- `commit`: solo lo pasan las pruebas. Si es None, se obtiene con
  `escribir.commit_actual()` AL INICIO (antes de leer datos: falla rápido si src/ está
  sucio) y se pasa tal cual a `escribir_entrega`. Nunca se calcula de otra forma ni se
  inventa.

Debe terminar llamando a `escribir.escribir_entrega(...)` y devolver su ruta.
`src/` no importa nada de `tests/` ni contiene ids o nombres de bloque del escenario
sintético.
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
