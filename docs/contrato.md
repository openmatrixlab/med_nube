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
| `huellas.gpkg` | Capa `huellas`, EPSG:9377, 976 829 polígonos (MultiPolygon). Columnas: `id_parte` (texto, único), `cbml`, `tipo`, `pisos` (entero ≥ 0, nunca NULL). SHA-256 `dc50e37f65c4fa64715b37c3e8c7129216edaa3252cb3d8cd5e984beca3b4f12`. **No se modifica**: se trabaja sobre una copia y no se abre en QGIS, porque guardar cambia los bytes. |
| `huellas_coltejer.gpkg` | Recorte de 600 × 600 m alrededor del edificio Coltejer (2401 partes), para probar rápido. Misma estructura. Lo entrega Luis junto con `huellas.gpkg`. |
| Nubes `*.las` / `*.laz` | Bloques de dron (fotogrametría), un archivo por bloque, todos en una sola carpeta (no se buscan subcarpetas). Pueden venir en EPSG:9377 o en otro CRS (p. ej. WGS84 / UTM 18N). |

**Garantías de `huellas.gpkg`**, ya verificadas: todas las geometrías son válidas (`shapely.is_valid`), no hay vacías, `id_parte` no se repite y `pisos` no tiene NULL. Si se encuentra algo que contradiga esto, **se para** y se escribe en `PREGUNTAS.md`.

## 3. Reglas de procesamiento

Todas las distancias están en metros y en EPSG:9377.

**Convenciones geométricas** (aplican a todo §3):

- **Buffers**: `shapely` 2 con los parámetros por defecto: `quad_segs=16` y unión redonda.
- **"Dentro de"**: `shapely.contains_xy(geom, x, y)`. Un punto sobre la frontera **no** cuenta. Esto vale para puntos de techo, puntos de suelo y centros de celda.
- **Nombre de bloque**: `Path(archivo).stem` (`J14.las` → `J14`).
  - Si dos archivos tienen el mismo stem (p. ej. `J14.las` y `J14.laz`), **se para** y se pregunta.
  - El orden alfabético es el de Python (`sorted`, por puntos de código).

### 3.1 Lectura de cada bloque

1. **CRS**: se determina así, en este orden:
   1. `crs = laspy.open(ruta).header.parse_crs()`.
   2. Si devuelve `None` o lanza excepción, se busca el archivo `<stem>.crs` en la misma carpeta del bloque. Contiene una sola línea de texto con `EPSG:xxxx` o con un WKT, y se lee con `pyproj.CRS.from_user_input(texto)`. Esto pasa, por ejemplo, cuando el software exportó el código como "user-defined" (32767). Ese archivo lo escribe Luis u Óscar a mano, una vez por bloque, a partir del reporte de vuelo.
   3. Si tampoco hay archivo `.crs`, el bloque se **omite** con motivo `sin CRS`.
   4. Si el CRS es compuesto, se usa su parte horizontal: `crs.sub_crs_list[0]`.
   5. Si `crs_h.equals(pyproj.CRS.from_epsg(9377))`, no se transforma. Si no, se transforman **solo X e Y** con `pyproj.Transformer.from_crs(crs_h, 9377, always_xy=True)`. **Z nunca se toca.**
2. **Ruido**: se descartan los puntos con clasificación 7 u 18. Las demás clases se **ignoran**: no se usa la clasificación del archivo para nada más.
3. **RGB**:
   - Si el formato de punto no tiene RGB (formatos 0, 1, 4, 6 y 9), el bloque se **omite** con motivo `sin RGB`.
   - La normalización a [0, 1] depende del máximo de R, G y B sobre **todos los puntos del archivo**, antes de cualquier filtro (si se lee por trozos, eso exige una primera pasada). Si ese máximo es mayor que 255, se divide por 65535; si no, se divide por 255.
4. **Únicos motivos de omisión válidos**: `sin CRS` y `sin RGB`. Cualquier otra falla al leer un bloque (archivo corrupto, falta de memoria, error de laspy) **detiene la corrida**. No se omite el bloque: se escribe en `PREGUNTAS.md`.
5. **Todos los puntos**: no se submuestrea ni se descarta ningún punto, salvo por las reglas de este documento.

### 3.2 Asignación de bloque a cada parte

- Cada parte se procesa con los puntos de **un solo bloque**: el que tenga más **puntos de techo** (3.4: dentro del área efectiva y después de los filtros 3.1 y 3.3).
- En caso de empate, se toma el bloque cuyo nombre es menor en orden alfabético.
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
   - se le resta `unión(todas las huellas H con shapely.intersects(H, P.buffer(5,0))).buffer(0,20)`. Eso incluye a `P`.
2. **Puntos de suelo**: los del bloque asignado que caen dentro de `R` y pasan los filtros 3.1 y 3.3.
3. Es normal que muchas partes interiores o pegadas a sus vecinas no tengan suelo. En ese caso, `z_suelo` es NULL y med_texture usa los pisos del catastro. **No** se amplía el anillo ni se busca suelo de otra forma.

### 3.6 Tabla `alturas`

Una fila por cada parte con **al menos 20 puntos de techo**. Si tiene menos, no tiene fila.

| Columna | Tipo | Regla |
|---|---|---|
| `id_parte` | TEXT | Igual que en `huellas.gpkg`. Único. |
| `bloque` | TEXT | Nombre del bloque asignado (`Path.stem`). |
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
- **Reproducibilidad**: `rng = numpy.random.default_rng(42)`, un generador nuevo por parte. Los resultados solo se exigen idénticos con las mismas versiones de numpy, que se anotan en la bitácora.
- **Definiciones**: `T` = total de puntos de techo; `mínimo = max(15, 0,10·T)`; `restantes` = índices de los puntos aún no retirados (al inicio, todos, en orden canónico).
- **Bucle**, mientras haya menos de 4 planos aceptados y `len(restantes) ≥ 15`:
  1. **500 iteraciones**, cada una con exactamente una llamada `rng.choice(len(restantes), 3, replace=False)`. Los índices se refieren a `restantes`.
     - Plano por los 3 puntos: normal `n = (b − a) × (c − a)`. Si `‖n‖ < 1e-9`, la tríada es degenerada: la iteración se consume y no hay candidato.
     - Inliers del candidato: puntos de `restantes` a distancia perpendicular ≤ 0,10 m.
     - Gana el candidato con más inliers. En empate, el primero, con comparación estricta `>`.
     - Si las 500 iteraciones fueron degeneradas, el bucle **termina**.
  2. **Reajuste**: con los inliers del ganador, se calcula el centroide `c0`. Normal = última fila de `Vt`, con `numpy.linalg.svd(inliers − c0, full_matrices=False)`. Si `nz < 0`, se invierte.
  3. Se **recalculan los inliers** sobre `restantes`, con distancia `|(p − c0)·n| ≤ 0,10`.
  4. Si son menos que `mínimo`, el bucle **termina**.
  5. Si la pendiente es > 70°, no es plano (es pared o ruido): sus inliers se retiran de `restantes` y se vuelve al paso 1. Esto no cuenta para el tope de 4.
  6. En los demás casos, el plano se **acepta** y sus inliers se retiran de `restantes`.
- **Orden final**: los planos aceptados se ordenan por número de inliers, de mayor a menor, con orden estable (en empate, el que se aceptó primero).

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
| `bloques_omitidos` | JSON: objeto `{bloque: motivo}`, con motivo `sin CRS` o `sin RGB`; o `{}` si no hay. |
| `bloques_advertencias` | JSON: siempre `{}` en la versión 1.0. Queda reservado. |

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
4. **Todos los bloques**: la entrega usa **todos** los bloques de la carpeta. Cada uno aparece en `bloques` o en `bloques_omitidos`. El mensaje de entrega incluye el listado de la carpeta (`ls -l`) para que Luis lo compare.
5. **Recepción**: Luis corre él mismo `pytest` y el validador, con el código de `main` y el `huellas.gpkg` oficial. El reporte que manda Óscar es informativo.
6. **Revisión por muestreo**: Óscar conserva los archivos intermedios hasta que Luis apruebe la entrega. Luis puede pedir el detalle de partes al azar (puntos de techo y suelo).

## 6. Notas para el consumidor (med_texture)

No son obligaciones de Óscar; se dejan aquí para que el consumidor no las olvide.

- **Usar solo `h_*`**, nunca comparar `z_*` entre bloques: el datum vertical puede variar entre bloques.
- **Sin suelo**: si `h_*` es NULL, se usa la altura por pisos (`pisos × 2,8`).
- **Ladera**: en pendiente, el p25 del anillo sesga `h` hacia arriba, del orden de 1–2 m.
- **Forma `otro` con `pendiente_deg < 5`**: se modela como plano. Son terrazas con cuartos útiles.
- **Alero de `dos_aguas`**: se deriva como `h_p98 − (ancho perpendicular a la cumbrera / 2) · tan(pendiente)`.
- **Techos verdes**: un techo con `ExG > 0,10` (zinc verde, pasto sintético) desaparece de las tablas. Es aceptado.
