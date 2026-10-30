# Contrato de entrega med_nube · versión 1.0

Este documento es **normativo**. Lo que no está aquí no se entrega. Si algo es ambiguo, se pregunta en `PREGUNTAS.md` y no se improvisa.

Las constantes (nombres de columnas, umbrales, valores permitidos) están también en `src/med_nube/contrato.py`. Si este documento y ese archivo difieren, **manda `contrato.py`** y se reporta la diferencia en `PREGUNTAS.md`.

## 1. Objetivo

Para cada construcción del catastro de Medellín cubierta por las nubes de puntos de dron, medir:

1. **Alturas**: percentiles de la cota del techo y la cota del suelo alrededor.
2. **Techos**: forma, pendiente y orientación.

Nada más.

## 2. Insumos

| Insumo | Descripción |
|---|---|
| `huellas.gpkg` | Capa `huellas`, EPSG:9377, 976 829 polígonos (MultiPolygon). Columnas: `id_parte` (texto, único), `cbml`, `tipo`, `pisos` (entero). SHA-256 `dc50e37f65c4fa64715b37c3e8c7129216edaa3252cb3d8cd5e984beca3b4f12`. **No se modifica.** |
| `huellas_coltejer.gpkg` | Recorte de 600 × 600 m alrededor del edificio Coltejer, para probar rápido. Misma estructura. |
| Nubes `*.las` / `*.laz` | Bloques de dron (fotogrametría), un archivo por bloque. Pueden venir en EPSG:9377 o en otro CRS (p. ej. WGS84 / UTM 18N). |

## 3. Reglas de procesamiento

Todas las distancias están en metros y en EPSG:9377.

### 3.1 Lectura de cada bloque

1. **CRS**:
   - Si el LAS declara CRS distinto de EPSG:9377, transformar **solo X e Y** a EPSG:9377 con `pyproj` (`always_xy=True`). **Z no se toca.**
   - Si el LAS no declara CRS, el bloque se **omite** y se registra en `metadatos.bloques_omitidos` con el motivo.
2. **Ruido**: se descartan los puntos con clasificación 7 u 18. Las demás clases se **ignoran**: no se usa la clasificación del archivo para nada más.
3. **RGB**:
   - Se normaliza a [0, 1]: se divide por 65535 si el máximo de R, G o B del bloque es mayor que 255; si no, se divide por 255.
   - Si el bloque no tiene RGB, el filtro de vegetación (3.3) no se aplica y se registra `sin_rgb` en `metadatos.bloques_advertencias`.

### 3.2 Asignación de bloque a cada parte

- Cada parte se procesa con los puntos de **un solo bloque**: el que tenga más **puntos de techo** (3.4: dentro del área efectiva y después de los filtros 3.1 y 3.3).
- En caso de empate, se toma el bloque cuyo nombre de archivo es menor en orden alfabético.
- No se mezclan bloques en una misma parte. Pueden tener datum vertical distinto.

### 3.3 Filtro de vegetación

- Exceso de verde: `ExG = (2G − R − B) / (R + G + B)`. Si `R + G + B = 0`, entonces `ExG = 0`.
- Un punto con `ExG > 0,10` es vegetación y se descarta, tanto en el techo como en el suelo.

### 3.4 Área efectiva del techo

Para la parte `P`:

1. **Erosión**: `E = P.buffer(−0,30)`. Si `E` queda vacía o con área < 1 m², entonces `E = P`.
2. **Partes más altas**:
   - Se toman las demás partes `Q` de `huellas.gpkg` que cumplan las dos condiciones:
     - `Q.pisos > P.pisos`;
     - `área(Q ∩ P) > 1 m²`.
   - Área efectiva: `A = E − unión(Q.buffer(0,30))`.
3. **Mínimo**: si `área(A) < 4 m²`, la parte **no** aparece en ninguna tabla.

**Puntos de techo**: los del bloque asignado que caen dentro de `A` y pasan los filtros 3.1 y 3.3.

### 3.5 Anillo de suelo

1. Se construye la zona `R`:
   - punto de partida: `P.buffer(5,0) − P.buffer(1,0)`;
   - se le resta `unión(todas las huellas que tocan P.buffer(5,0)).buffer(0,20)`. Eso incluye a `P`.
2. **Puntos de suelo**: los del bloque asignado que caen dentro de `R` y pasan los filtros 3.1 y 3.3.

### 3.6 Tabla `alturas`

Una fila por cada parte con **al menos 20 puntos de techo**. Si tiene menos, no tiene fila.

| Columna | Tipo | Regla |
|---|---|---|
| `id_parte` | TEXT | Igual que en `huellas.gpkg`. Único. |
| `bloque` | TEXT | Nombre del archivo del bloque asignado, sin ruta y sin extensión. |
| `n_puntos` | INTEGER | Puntos de techo. |
| `cobertura` | REAL [0, 1] | Ver la definición después de la tabla. |
| `z_p10`, `z_p50`, `z_p90`, `z_p98` | REAL | Percentiles de Z de los puntos de techo. Se calculan con `numpy.percentile` con interpolación lineal, que es el método por defecto. |
| `z_max` | REAL | Máximo de Z de los puntos de techo. |
| `n_puntos_suelo` | INTEGER | Puntos de suelo (puede ser 0). |
| `z_suelo` | REAL o NULL | Percentil 25 de Z de los puntos de suelo. Es NULL si `n_puntos_suelo < 10`. |
| `h_p50`, `h_p98` | REAL o NULL | `z_p50 − z_suelo` y `z_p98 − z_suelo`. Son NULL si `z_suelo` es NULL. |

**Cobertura**:
- Se usa una grilla de 0,5 m alineada a múltiplos de 0,5 m en EPSG:9377. La celda `(i, j)` cubre `[0,5·i, 0,5·(i+1)) × [0,5·j, 0,5·(j+1))`.
- `cobertura` es la fracción de celdas cuyo **centro** cae dentro de `A` y que contienen al menos un punto de techo.
- Si ningún centro cae dentro de `A`, entonces `cobertura = 0`.

Los valores Z van en el datum vertical del bloque, sin ninguna corrección. Todos los REAL se escriben con al menos 2 decimales de precisión; no se redondea a menos.

### 3.7 Tabla `techos`

Una fila por cada parte de `alturas` con `n_puntos ≥ 50` y `cobertura ≥ 0,5`. Las demás partes no tienen fila.

**Ajuste de planos (RANSAC secuencial, determinístico)**:

- **Entrada**: puntos de techo `(x, y, z)`.
  - Primero se ordenan en orden canónico: `orden = numpy.lexsort((z, y, x))`, es decir, por x, luego y, luego z. Así el resultado no depende del orden del archivo, del tamaño de los trozos de lectura ni del número de procesos.
  - Después se centran restando su media.
- **Reproducibilidad**: `numpy.random.default_rng(42)`, con un generador nuevo por parte.
- **Iteraciones**: 500 por plano.
  - En cada una se eligen 3 puntos sin reemplazo y se calcula el plano que pasa por ellos.
  - Se descartan las tríadas degeneradas: norma de la normal < 1e-9.
- **Inliers**: puntos a distancia perpendicular ≤ 0,10 m del plano.
- **Selección**: gana el plano con más inliers; en empate, el primero encontrado.
  - Se reajusta por mínimos cuadrados (SVD) sobre sus inliers.
  - Se recalculan los inliers con el plano reajustado y la misma tolerancia.
- **Planos que se descartan**: si la **pendiente** del plano reajustado es > 70°, no cuenta como plano (es pared o ruido). Sus inliers se retiran igual y se sigue buscando.
- **Aceptación**: un plano se acepta si sus inliers son ≥ `max(15, 10 % del total de puntos de techo)`.
- **Parada**: se para cuando se rechaza un plano por pocos inliers, cuando quedan menos de 15 puntos, o cuando ya hay 4 planos aceptados.
- **Orden**: los planos aceptados se ordenan por número de inliers, de mayor a menor.

**Magnitudes de cada plano**, con normal unitaria `n = (nx, ny, nz)` y `nz ≥ 0` (si `nz < 0`, se invierte):

- `pendiente = degrees(arccos(nz))`.
- `azimut_caida = degrees(atan2(nx, ny)) mod 360`. Es la dirección hacia donde baja el techo: 0 = norte y crece en sentido horario.
- **Dirección de la intersección** de dos planos: `d = n1 × n2`. Su azimut es `degrees(atan2(dx, dy)) mod 180`.

**Forma**: se aplican estas reglas en orden y gana la primera que se cumpla.

| # | Condición | `forma` |
|---|---|---|
| 1 | 0 planos aceptados | `otro` |
| 2 | El plano 1 tiene pendiente < 5° y sus inliers son ≥ 60 % del total | `plano` |
| 3 | Exactamente 1 plano aceptado, con pendiente ≥ 5° | `una_agua` |
| 4 | Exactamente 2 planos, ambos con pendiente ≥ 5°, y la diferencia angular de sus `azimut_caida` está en [150°, 210°] | `dos_aguas` |
| 5 | 3 o 4 planos, todos con pendiente ≥ 5° | `cuatro_aguas` |
| 6 | Cualquier otro caso | `otro` |

| Columna | Tipo | Regla |
|---|---|---|
| `id_parte` | TEXT | Único y presente en `alturas`. |
| `forma` | TEXT | `plano` · `una_agua` · `dos_aguas` · `cuatro_aguas` · `otro` |
| `n_planos` | INTEGER 0–4 | Planos aceptados. |
| `pendiente_deg` | REAL o NULL | Del plano 1. Es NULL si hay 0 planos. |
| `azimut_caida_deg` | REAL o NULL | Del plano 1, en [0, 360). Es NULL si hay 0 planos o si `pendiente_deg < 5`. |
| `azimut_cumbrera_deg` | REAL o NULL | En [0, 180). Ver la regla después de la tabla. |
| `frac_inliers` | REAL [0, 1] | Inliers de todos los planos aceptados dividido por el total de puntos de techo. |
| `rmse_m` | REAL o NULL | Raíz del error cuadrático medio de las distancias de los inliers de todos los planos aceptados a su plano. Es NULL si hay 0 planos. |

**`azimut_cumbrera_deg`**:
- Con `dos_aguas`: es el azimut de la intersección de los planos 1 y 2.
- Con `cuatro_aguas`: es el de la intersección del primer par `(i, j)`, con `i < j` en orden de planos, cuyas `azimut_caida` difieren en [150°, 210°]. Si no hay ningún par así, es NULL.
- Con cualquier otra forma: NULL.

### 3.8 Tabla `metadatos`

Dos columnas TEXT: `clave` y `valor`. Claves obligatorias, ni más ni menos:

| clave | valor |
|---|---|
| `version_contrato` | `1.0` |
| `fecha_proceso` | ISO 8601 (`2026-11-03T14:05:00-05:00`) |
| `commit` | Hash del commit de med_nube con que se generó. |
| `huellas_sha256` | SHA-256 del `huellas.gpkg` usado. |
| `bloques` | JSON: lista de nombres de bloque procesados, ordenada. |
| `bloques_omitidos` | JSON: objeto `{bloque: motivo}`, o `{}` si no hay. |
| `bloques_advertencias` | JSON: objeto `{bloque: [advertencias]}`, o `{}` si no hay. |

## 4. Formato de entrega

- **Un solo** GeoPackage: `med_nube_entrega_<AAAAMMDD>.gpkg`.
- **Exactamente** tres tablas sin geometría: `alturas`, `techos` y `metadatos`. Sin columnas extra, sin capas extra y sin geometrías.
- Debe pasar el validador sin errores:
  ```
  python -m med_nube validar med_nube_entrega_AAAAMMDD.gpkg --huellas huellas.gpkg
  ```
- **Envío**: a Luis, junto con el reporte que imprime el validador. Va por disco o enlace de nube, **no** por GitHub.

## 5. Criterios de aceptación

1. **Pruebas**: `pytest` en verde, incluidas las de aceptación con datos sintéticos de `tests/`.
2. **Validador**: sin errores sobre la entrega completa.
3. **Coltejer** (`id_parte = cat20250121:1466693`): es el caso de control.
   - Si algún bloque lo cubre, debe estar en `alturas`. Se espera `h_p98` entre 120 y 190 m.
   - Si el valor sale fuera de ese rango, el validador muestra una advertencia `REVISAR`. **No se ajustan parámetros para corregirlo**: se reporta en el mensaje de entrega con sus valores, y Luis decide.
   - Si ningún bloque lo cubre, se dice explícitamente en el mensaje de entrega.
4. **Todos los bloques**: la entrega usa **todos** los bloques disponibles. Cada uno aparece en `bloques` o en `bloques_omitidos`.
