# med_nube

Alturas y techos de las construcciones de Medellín a partir de las nubes de puntos de dron (fotogrametría). El resultado alimenta a [med_texture](https://github.com/openmatrixlab/med_texture), el instrumento de texturizado isométrico.

- **Entra:** `huellas.gpkg`, con las construcciones del catastro (976 829 partes, EPSG:9377), y los bloques `*.las` / `*.laz`.
- **Sale:** `med_nube_entrega_AAAAMMDD.gpkg`, con tres tablas:
  - `alturas`: percentiles de cota del techo, cota del suelo alrededor y altura;
  - `techos`: forma, pendiente y orientación;
  - `metadatos`.

| Documento | Para qué |
|---|---|
| [`docs/contrato.md`](docs/contrato.md) | Reglas exactas del cálculo y del formato. Es normativo. |
| [`AGENTS.md`](AGENTS.md) | Alcance, lista blanca de archivos, definición de terminado, plantilla de entrega. |
| [`PREGUNTAS.md`](PREGUNTAS.md) | Dudas abiertas sobre el contrato. |

## Estado

| Componente | Estado |
|---|---|
| Contrato, validador, escritor, escenario sintético y pruebas | Hechos |
| `procesar()` | **Por implementar** (Óscar, ver `AGENTS.md`) |
| CI · job `validador` | Siempre en verde |
| CI · job `aceptacion` | En rojo hasta que `procesar()` esté implementado |
| CI · job `alcance` | Corre en los PR y revisa que solo se toquen archivos permitidos |

## Uso

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest

python -m med_nube procesar --huellas huellas.gpkg --nubes /ruta/bloques --salida salida/
python -m med_nube validar salida/med_nube_entrega_AAAAMMDD.gpkg --huellas huellas.gpkg
```

Prueba rápida con el recorte del Coltejer (no vale como entrega):

```bash
python -m med_nube validar <entrega> --huellas huellas_coltejer.gpkg --prueba
```

## Datos

Los datos **no** van en git. Los entrega Luis por disco o enlace de nube.

| Archivo | SHA-256 |
|---|---|
| `huellas.gpkg` | `dc50e37f65c4fa64715b37c3e8c7129216edaa3252cb3d8cd5e984beca3b4f12` |
| `huellas_coltejer.gpkg` | `2ca846a759ead1ea4d2bd8dac5f5875a3da7d452d4e0ef66b5d7d984b343b138` |

- Para comprobar el hash: `shasum -a 256 huellas.gpkg`.
- Si `huellas.gpkg` llega por partes: `cat huellas.gpkg.gz.part_* | gunzip > huellas.gpkg`.
- Hay que trabajar sobre una copia: abrirlo en QGIS y guardar cambia el hash.

Bloques de nube: los tiene Óscar. Si un bloque tiene el CRS como "user-defined", se agrega a su lado `<bloque>.crs` con `EPSG:xxxx` (ver contrato §3.1).

## Recepción (Luis)

1. Revisar el PR. CI en verde, incluido `alcance`.
2. Hacer merge a `main`.
3. Con el código de `main`, correr `pytest` y `python -m med_nube validar <entrega> --huellas huellas.gpkg`, sin `--prueba`.
4. Comparar el `ls -l` de la carpeta de bloques con `bloques` y `bloques_omitidos`.
5. Revisar las advertencias: Coltejer, `h_p98` negativas, metros por piso.
6. Pedir partes al azar si hace falta.

## Bitácora

<!-- Notas de corrida (ver AGENTS.md): fecha, máquina, versiones, por bloque (tiempo, partes intersectadas, partes asignadas), incidencias. -->
