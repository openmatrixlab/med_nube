#!/usr/bin/env bash
# Reconstruye insumos/huellas.gpkg a partir de las partes comprimidas y verifica el SHA-256.
# Uso: bash insumos/armar_huellas.sh
set -euo pipefail
cd "$(dirname "$0")"
ESPERADO_HUELLAS="dc50e37f65c4fa64715b37c3e8c7129216edaa3252cb3d8cd5e984beca3b4f12"
ESPERADO_COLTEJER="2ca846a759ead1ea4d2bd8dac5f5875a3da7d452d4e0ef66b5d7d984b343b138"
sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
cat huellas.gpkg.gz.part_* | gunzip > huellas.gpkg
[ "$(sha huellas.gpkg)" = "$ESPERADO_HUELLAS" ] || { echo "ERROR: SHA-256 de huellas.gpkg no coincide"; exit 1; }
[ "$(sha huellas_coltejer.gpkg)" = "$ESPERADO_COLTEJER" ] || { echo "ERROR: SHA-256 de huellas_coltejer.gpkg no coincide"; exit 1; }
echo "OK: insumos/huellas.gpkg y insumos/huellas_coltejer.gpkg verificados."
echo "No los modifique ni los abra/guarde en QGIS: trabaje sobre copias si hace falta."
