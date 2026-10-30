"""CLI: python -m med_nube {procesar,validar} ..."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .validar import reporte, validar


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="med_nube")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("procesar", help="Nubes + huellas → entrega GeoPackage")
    p.add_argument("--huellas", type=Path, required=True)
    p.add_argument("--nubes", type=Path, required=True, help="Carpeta con *.las / *.laz")
    p.add_argument("--salida", type=Path, required=True, help="Carpeta de salida")

    v = sub.add_parser("validar", help="Valida una entrega contra el contrato")
    v.add_argument("entrega", type=Path)
    v.add_argument("--huellas", type=Path, required=True)
    v.add_argument(
        "--prueba",
        action="store_true",
        help="Acepta huellas no oficiales (p. ej. huellas_coltejer.gpkg). No vale como entrega.",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.comando == "procesar":
        from .procesar import procesar

        ruta = procesar(args.huellas, args.nubes, args.salida)
        print(ruta)
        return 0
    resultado = validar(args.entrega, args.huellas, oficial=not args.prueba)
    print(reporte(resultado))
    return 0 if resultado.ok else 1


if __name__ == "__main__":
    sys.exit(main())
