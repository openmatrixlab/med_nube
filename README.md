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
| [`AGENTS.md`](AGENTS.md) | Alcance, qué se puede tocar, definición de terminado. |
| [`PREGUNTAS.md`](PREGUNTAS.md) | Dudas abiertas sobre el contrato. |

## Uso

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                                   # validador + aceptación

python -m med_nube procesar --huellas huellas.gpkg --nubes /ruta/bloques --salida salida/
python -m med_nube validar salida/med_nube_entrega_AAAAMMDD.gpkg --huellas huellas.gpkg
```

Prueba rápida con el recorte del Coltejer:

```bash
python -m med_nube validar <entrega> --huellas huellas_coltejer.gpkg --prueba
```

## Datos

Los datos **no** van en git.

- `huellas.gpkg`: SHA-256 `dc50e37f…4f12`. Lo entrega Luis. Si llega por partes:
  ```bash
  cat huellas.gpkg.gz.part_* | gunzip > huellas.gpkg
  shasum -a 256 huellas.gpkg
  ```
- Bloques de nube: los tiene Óscar.

## Estado

- Listo: `procesar()` por implementar (ver `AGENTS.md`). El validador, el escritor y las pruebas ya están.
- CI:
  - el job **validador** debe estar siempre en verde;
  - el job **aceptación** queda en rojo hasta que `procesar()` esté implementado.

## Bitácora

<!-- Notas de corrida: fecha, máquina, bloques, tiempos, incidencias. -->
