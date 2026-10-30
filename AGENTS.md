# AGENTS.md — instrucciones para el agente (Astra / ChatGPT) y para Óscar

Lee este archivo completo antes de tocar cualquier cosa. Es corto a propósito.

## Misión (única)

1. Implementar `procesar()` en `src/med_nube/procesar.py` siguiendo **exactamente** `docs/contrato.md` §3.
2. Correrlo sobre **todos** los bloques de nube de puntos disponibles, con el `huellas.gpkg` oficial.
3. Entregar **un** archivo `med_nube_entrega_AAAAMMDD.gpkg` que pase el validador.

Eso es todo. No hay segunda fase en este repo.

## Definición de terminado

- [ ] `pytest` en verde: las pruebas de `tests/test_aceptacion.py` y `tests/test_validar.py` pasan sin modificarlas.
- [ ] `ruff check src tests` y `ruff format --check src tests` sin errores.
- [ ] `python -m med_nube validar <entrega> --huellas huellas.gpkg` imprime `RESULTADO: APROBADA`, sobre la corrida completa y con el `huellas.gpkg` oficial (sin `--prueba`).
- [ ] Mensaje de entrega a Luis con la plantilla del final de este archivo.

## Qué SÍ se puede tocar

- `src/med_nube/procesar.py`.
- Módulos nuevos dentro de `src/med_nube/` cuyo nombre empiece por `proc_`, por ejemplo `proc_lectura.py` o `proc_ransac.py`.
- Pruebas propias nuevas en `tests/test_proc_*.py`.
- `PREGUNTAS.md`, para dudas.
- La sección "Bitácora" al final de `README.md`, con notas de corrida (tiempos, bloques, problemas).

## Qué NO se puede tocar

Si algo de esto parece necesario, se escribe en `PREGUNTAS.md` y se espera.

- `docs/contrato.md`
- `src/med_nube/contrato.py`
- `src/med_nube/validar.py`
- `src/med_nube/escribir.py`
- `src/med_nube/__main__.py`
- `tests/sinteticos.py`
- `tests/test_aceptacion.py`
- `tests/test_validar.py`
- `.github/`
- `AGENTS.md`
- Las dependencias de `pyproject.toml`: no se agregan librerías nuevas. Las disponibles son numpy, pandas, shapely, geopandas, pyogrio, pyproj, laspy[lazrs], rasterio y scipy.

## Fuera de alcance

Que no se haga, aunque parezca buena idea:

- **Otros datos:** árboles, fachadas, colores, materiales, vegetación como producto, terreno o DTM, curvas de nivel.
- **Modelos:** clasificación o segmentación de la nube con ML, entrenar modelos, redes neuronales.
- **Productos 3D:** mallas, 3D Tiles, CityGML, modelos 3D de cualquier tipo.
- **Visualización:** visores web, mapas, notebooks como entregable, dashboards.
- **Cambios al algoritmo:**
  - "Mejorarlo": otro RANSAC, umbrales adaptativos, filtros adicionales, suavizados.
  - Afinar parámetros para que algo "se vea mejor". Los parámetros están fijos en `contrato.py`.
- **Cambios a los datos de entrada o salida:**
  - Corregir el datum vertical o transformar Z.
  - Columnas, tablas o capas extra en la entrega.
  - Cambiar nombres de columnas o unidades.
  - Modificar, filtrar o "limpiar" `huellas.gpkg`.
- **Git:** subir datos (`.las`, `.laz`, `.gpkg`, `.tif`, `.zip`). Ya están en `.gitignore`.
- **Otros alcances:** otras ciudades, otras capas del catastro, cruces con otras fuentes.

## Cómo trabajar

1. **Preparar el entorno:** `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`.
2. **Leer el contrato:** `docs/contrato.md` completo, y `src/med_nube/contrato.py` para las constantes. Usar **las constantes de `contrato.py`** en el código, no números escritos a mano.
3. **Implementar:**
   - Escribir `procesar()` hasta que `pytest tests/test_aceptacion.py` pase.
   - La interfaz está en el docstring de `procesar.py` y no se cambia.
   - Hay que terminar llamando a `escribir.escribir_entrega(...)`.
4. **Probar en chico:** con `huellas_coltejer.gpkg` y un bloque, validar con `--prueba`.
5. **Corrida completa:** con el `huellas.gpkg` oficial y todos los bloques. Validar **sin** `--prueba`.
6. **Git:** trabajar en la rama `implementacion` y abrir un PR a `main`. El commit con que se corre debe estar en ese PR, porque `escribir_entrega` exige el árbol `src/` limpio.

### Libertad de implementación (solo rendimiento)

Se puede elegir **cómo** calcular, nunca **qué** se calcula. Se permite:

- leer por trozos (`laspy.open(...).chunk_iterator(...)`);
- índices espaciales;
- rasterizar máscaras para preseleccionar puntos;
- multiprocesamiento;
- archivos temporales fuera del repo.

Condición: el resultado debe ser **idéntico** al de una implementación directa del contrato, sin importar el tamaño de trozo ni el número de procesos. Por eso el contrato fija el orden canónico de los puntos antes de RANSAC.

Datos útiles:

- Un bloque típico pesa unos 9 GB y tiene unos 270 millones de puntos.
- Los puntos **no** vienen ordenados espacialmente.
- Las huellas son 976 829 polígonos.

## Si hay dudas

- Si algo del contrato es ambiguo, contradictorio o parece imposible, se escribe en `PREGUNTAS.md`: qué sección, qué duda, qué opciones hay. Se sigue con lo demás, sin elegir una opción por cuenta propia.
- Si una prueba de aceptación parece estar mal, también va a `PREGUNTAS.md`. La prueba **no** se modifica.
- Si el Coltejer sale fuera de rango, se reporta. **No** se ajusta nada para corregirlo.

## Plantilla del mensaje de entrega

```
Entrega med_nube — AAAA-MM-DD
Archivo: med_nube_entrega_AAAAMMDD.gpkg (N MB)
SHA-256 de la entrega: ...
Commit: ...  (PR #...)
Bloques procesados: N  ·  omitidos: N (motivos)
Tiempo total de proceso: ... en (CPU/RAM de la máquina)
Coltejer: h_p98 = ... m (bloque ...)   |   o: "ningún bloque lo cubre"
Reporte completo del validador:
<pegar la salida de python -m med_nube validar ...>
Preguntas abiertas: (ver PREGUNTAS.md) / ninguna
```

El archivo se envía a Luis por disco o enlace de nube. **No** se sube a GitHub.
