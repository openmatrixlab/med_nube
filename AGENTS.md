# AGENTS.md — instrucciones para el agente (Astra / ChatGPT) y para Óscar

Lee este archivo completo antes de tocar cualquier cosa. Es corto a propósito.

## Misión (única)

1. Implementar `procesar()` en `src/med_nube/procesar.py` siguiendo **exactamente** `docs/contrato.md` §3.
2. Correrlo sobre **todos** los bloques de nube de puntos, con el `huellas.gpkg` oficial.
3. Entregar **un** archivo `med_nube_entrega_AAAAMMDD.gpkg` que pase el validador.

Eso es todo. No hay segunda fase en este repo.

## Quién hace qué

- **El agente**: escribe el código y las pruebas propias, en la rama `implementacion`. No tiene los datos reales ni necesita red.
- **Óscar**:
  - prepara el entorno antes de lanzar el agente;
  - corre el proceso real en su máquina;
  - llena la bitácora;
  - envía la entrega.
- **Luis**: revisa el PR, corre él mismo `pytest` y el validador con el código de `main`, y acepta o rechaza.

## Definición de terminado

- [ ] CI en verde en el PR: los jobs `validador`, `aceptacion` y `alcance`.
- [ ] `python -m med_nube validar <entrega> --huellas insumos/huellas.gpkg` imprime `RESULTADO: APROBADA`:
  - sobre la corrida completa;
  - con el `huellas.gpkg` oficial;
  - **sin** `--prueba`.
- [ ] Bitácora llena (ver abajo) y mensaje de entrega con la plantilla del final.

## Lista blanca: lo ÚNICO que se puede crear o modificar

- `src/med_nube/procesar.py`.
- Módulos nuevos `src/med_nube/proc_*.py`, por ejemplo `proc_lectura.py` o `proc_ransac.py`.
- Pruebas nuevas `tests/test_proc_*.py`.
  - No pueden usar `monkeypatch` ni reemplazar nada de `med_nube.validar`, `med_nube.escribir`, `med_nube.contrato` ni de las pruebas existentes.
- `PREGUNTAS.md`.
- La sección "Bitácora" de `README.md`.

**Todo lo demás está prohibido**, y el job `alcance` de CI lo verifica en cada PR. Eso incluye, entre otros:

- `docs/`, `insumos/`, `AGENTS.md`, `.github/`, `.gitignore`;
- `pyproject.toml` **completo**: dependencias, configuración de pytest y de ruff;
- cualquier `conftest.py` o `__init__.py`;
- `contrato.py`, `validar.py`, `escribir.py`, `__main__.py`;
- `tests/sinteticos.py`, `tests/test_aceptacion.py`, `tests/test_validar.py`.

Si algo de esto parece necesario, se escribe en `PREGUNTAS.md` y se espera.

Además:

- `src/` **no importa nada de `tests/`**.
- `src/` **no contiene** ids ni nombres de bloque del escenario sintético (`t:…`, `A_9377`, …). CI también lo busca.
- **No se detecta** si se está corriendo una prueba: el mismo código procesa datos sintéticos y reales.

## Fuera de alcance

Que no se haga, aunque parezca buena idea:

- **Otros datos:** árboles, fachadas, colores, materiales, vegetación como producto, terreno o DTM, curvas de nivel.
- **Modelos:** clasificación o segmentación con ML, entrenar modelos.
- **Productos 3D:** mallas, 3D Tiles, CityGML, cualquier modelo 3D.
- **Visualización:** visores, mapas, notebooks como entregable, dashboards.
- **Cambios al algoritmo:**
  - "Mejorarlo": otro RANSAC, umbrales adaptativos, filtros extra, suavizados.
  - Afinar parámetros. Los parámetros son las constantes de `contrato.py` y se usan siempre desde ahí, nunca como números escritos a mano.
  - **Submuestrear puntos** o limitar el número de puntos por parte, por trozo o por bloque, aunque sea por rendimiento.
- **Cambios a los datos de entrada o salida:**
  - Corregir el datum vertical o transformar Z.
  - Columnas, tablas o capas extra.
  - Cambiar nombres o unidades.
  - Modificar, filtrar o "limpiar" `huellas.gpkg`. Se trabaja sobre una copia y no se abre en QGIS.
- **Omitir bloques** por motivos distintos de `sin CRS` o `sin RGB`. Cualquier otra falla **detiene** la corrida y va a `PREGUNTAS.md`.
- **El commit:** inventarlo, escribirlo a mano o pasarlo por fuera de `escribir.commit_actual()`.
- **Git:** subir datos (`.las`, `.laz`, `.gpkg`, `.tif`, `.zip`, `.crs`).

## Cómo trabajar

1. **Óscar prepara el entorno** antes de lanzar el agente:
   - `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`. `lazrs` necesita su wheel. Hay que usar `-e`, porque `commit_actual()` necesita el repo de git.
   - `bash insumos/armar_huellas.sh`, que deja `insumos/huellas.gpkg` verificado.
2. **Leer el contrato:** `docs/contrato.md` completo, y `src/med_nube/contrato.py`.
3. **Implementar:**
   - Escribir `procesar()` hasta que `pytest` pase completo.
   - La interfaz está en el docstring de `procesar.py` y no se cambia.
   - `commit_actual()` se llama **al inicio**.
   - Hay que terminar con una sola llamada a `escribir.escribir_entrega(...)`.
4. **Un bloque real, completo:** antes de la corrida total, Óscar corre un bloque y anota en la bitácora:
   - el tiempo y la memoria máxima;
   - la extrapolación al total;
   - una comparación sobre el Coltejer o el bloque de prueba con dos tamaños de trozo distintos: las tablas deben salir idénticas.
5. **Corrida completa:** con el `huellas.gpkg` oficial y todos los bloques. Validar **sin** `--prueba`.
6. **Git:** rama `implementacion` y PR a `main`. El commit con que se corrió debe estar en el PR. No se hace rebase ni squash después de la corrida.

### Libertad de implementación (solo rendimiento)

Se puede elegir **cómo** calcular, nunca **qué**. Se permite:

- leer por trozos (`laspy.open(...).chunk_iterator(...)`);
- índices espaciales;
- máscaras rasterizadas para preseleccionar puntos;
- multiprocesamiento;
- **caché por bloque fuera del repo**, reanudable si la corrida se cae: puntos de techo y de suelo por parte, o el mapa parte→bloque.

Condición: el resultado es **idéntico** sin importar el tamaño de trozo, el número de procesos o las reanudaciones. La entrega final sale de **una** llamada a `escribir_entrega` con todos los bloques.

Datos útiles:

- Un bloque típico pesa unos 9 GB y tiene unos 270 millones de puntos.
- Los puntos **no** vienen ordenados espacialmente.
- La normalización de RGB exige leer primero el máximo del archivo completo.
- Las huellas son 976 829.

Los archivos intermedios se **conservan** hasta que Luis apruebe la entrega.

## Si hay dudas

- **Contrato ambiguo, contradictorio o imposible:** se escribe en `PREGUNTAS.md` (sección, duda, opciones) y se sigue con lo demás.
- **Hay que elegir para avanzar** (por ejemplo, para que pase una prueba):
  - se toma la opción **más literal** del contrato;
  - se marca `elegida provisionalmente` en `PREGUNTAS.md`;
  - se deja un comentario `# P<n>` en el código.
  - Luis confirma o corrige.
- **Una prueba parece estar mal:** va a `PREGUNTAS.md`. La prueba **no** se modifica.
- **El Coltejer sale fuera de rango:** se reporta con sus valores. **No** se ajusta nada para corregirlo.

## Bitácora

Va en `README.md`, una entrada por corrida:

- fecha y máquina (CPU/RAM);
- versiones de Python, numpy, pyproj, laspy y shapely;
- por cada bloque:
  - tiempo;
  - partes cuyo bbox intersecta el bloque;
  - partes con ≥ 20 puntos de techo asignadas a ese bloque;
- incidencias.

## Plantilla del mensaje de entrega

```
Entrega med_nube — AAAA-MM-DD
Archivo: med_nube_entrega_AAAAMMDD.gpkg (N MB)
SHA-256 de la entrega: ...
Commit: ...  (PR #...)
Carpeta de bloques (ls -l): <pegar>
Bloques procesados: N  ·  omitidos: N (motivos)
Tiempo total: ...  ·  máquina: ...
Coltejer: bloque ..., n_puntos ..., cobertura ..., z_max ..., h_p98 ... m
          | o: "ningún bloque lo cubre"
Reporte del validador (sin --prueba):
<pegar>
Preguntas abiertas: (ver PREGUNTAS.md) / ninguna
```

El archivo se envía a Luis por disco o enlace de nube. **No** se sube a GitHub.
