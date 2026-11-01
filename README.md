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

python -m med_nube procesar --huellas insumos/huellas.gpkg --nubes /ruta/bloques --salida salida/
python -m med_nube validar salida/med_nube_entrega_AAAAMMDD.gpkg --huellas insumos/huellas.gpkg
```

Prueba rápida con el recorte del Coltejer (no vale como entrega):

```bash
python -m med_nube validar <entrega> --huellas insumos/huellas_coltejer.gpkg --prueba
```

## Datos

Las huellas vienen **en el repo**, en `insumos/`, comprimidas y partidas porque GitHub no admite archivos de más de 100 MB. Para armarlas:

```bash
bash insumos/armar_huellas.sh   # crea insumos/huellas.gpkg y verifica los SHA-256
```

| Archivo | SHA-256 |
|---|---|
| `insumos/huellas.gpkg` | `dc50e37f65c4fa64715b37c3e8c7129216edaa3252cb3d8cd5e984beca3b4f12` |
| `insumos/huellas_coltejer.gpkg` | `2ca846a759ead1ea4d2bd8dac5f5875a3da7d452d4e0ef66b5d7d984b343b138` |

- Las huellas no se modifican. Abrirlas en QGIS y guardar cambia el hash.
- Las nubes de puntos **no** van en git: las tiene Óscar. Si un bloque tiene el CRS como "user-defined", se agrega a su lado `<bloque>.crs` con `EPSG:xxxx` (ver contrato §3.1).

## Recepción (Luis)

1. Revisar el PR. CI en verde, incluido `alcance`.
2. Hacer merge a `main`.
3. Con el código de `main`, correr `pytest` y `python -m med_nube validar <entrega> --huellas insumos/huellas.gpkg`, sin `--prueba`.
4. Comparar el `ls -l` de la carpeta de bloques con `bloques` y `bloques_omitidos`.
5. Revisar las advertencias: Coltejer, `h_p98` negativas, metros por piso.
6. Pedir partes al azar si hace falta.

## Bitácora

<!-- Notas de corrida (ver AGENTS.md): fecha, máquina, versiones, por bloque (tiempo, partes intersectadas, partes asignadas), incidencias. -->

### 2026-11-01 · corrida completa · commit `2e9b3b7`

- **Máquina:** OSCAR_COSSIO · Intel64 Family 6 Model 198 (24 núcleos lógicos) · 63,4 GB de RAM · SSD · Windows 11.
- **Versiones:** Python 3.14.2 · numpy 2.5.4 · pyproj 3.8.0 · laspy 2.7.0 · shapely 2.2.0.
- **Huellas:** `huellas.gpkg` oficial, armado con `insumos/armar_huellas.sh` (SHA-256 `dc50e37f…4f12` verificado).
- **Rendimiento:** 5 000 000 puntos por trozo; procesos automáticos (7 bloques en paralelo, limitados por la memoria; 23 procesos para geometrías y partes).

**Un bloque real (paso 4).** `D_2025_05_03_LaFlorida`, el bloque más grande (3,37 GB; 99 114 117 puntos; 33 154 686 tras ruido y vegetación):

- 97,8 s con 5 000 000 puntos por trozo y 109,4 s con 1 000 000; memoria máxima del proceso: 2,83 GB.
- `alturas` y `techos` salen idénticas con los dos tamaños de trozo (256 y 249 partes).
- Extrapolación secuencial al total (969 millones de puntos): unos 16 min.

**Corrida completa (paso 5).** 36 bloques, ninguno omitido; 969 044 789 puntos leídos, 381 113 722 tras ruido y vegetación.

- Tiempo: 8,8 min de reloj. Geometrías, 14,5 s; bloques en paralelo, 117 s (la suma de los tiempos por bloque es 706,5 s); alturas y techos, 390 s.
- Entrega: `med_nube_entrega_20261101.gpkg` (3,4 MB), SHA-256 `1919afd47433f492c73e003ea56e2a0ec5c90e39024ce0f41d7596dd427af801`.
- 16 923 partes en `alturas` (16 849 con suelo) y 15 678 en `techos`. Mediana de h_p98: 5,6 m; 186 negativas (1,1 %); mediana de h_p98/pisos: 3,2 m.
- Validador sin `--prueba`: **APROBADA**. Única advertencia: ningún bloque cubre el Coltejer (§5.3).

| Bloque | Puntos | Vegetación | Lectura y asignación (s) | Partes cuyo bbox intersecta el bloque | Partes asignadas con ≥ 20 puntos de techo |
|---|---:|---:|---:|---:|---:|
| `20250627_ViaSantaFe_LaLoma_cloud` | 20 863 576 | 75 % | 7,2 | 146 | 11 |
| `D_2025_05_02_BelencitoCorazon` | 62 974 624 | 83 % | 25,2 | 260 | 110 |
| `D_2025_05_03_LaFlorida` | 99 114 117 | 67 % | 48,9 | 522 | 256 |
| `D_2025_05_05_SantaRita` | 39 264 956 | 69 % | 31,0 | 1 836 | 218 |
| `D_2025_05_06_LosBalsos` | 35 824 645 | 61 % | 18,8 | 634 | 284 |
| `D_2025_05_10_Robledo_ViaSanPedro` | 6 904 460 | 30 % | 5,6 | 1 652 | 520 |
| `D_2025_05_19_Golondrinas` | 7 325 700 | 49 % | 4,7 | 1 021 | 418 |
| `D_2025_05_20_ManoDeDios_Altavista` | 42 680 752 | 47 % | 50,2 | 4 261 | 2 592 |
| `D_2025_05_22_Villatina` | 33 654 193 | 15 % | 81,6 | 5 913 | 2 895 |
| `D_2025_05_23_SantaRita` | 47 327 760 | 70 % | 34,3 | 2 197 | 444 |
| `D_2025_05_26_SantaRita` | 49 083 621 | 72 % | 35,9 | 2 123 | 273 |
| `D_2025_06_24_Emergencia_BelloOriente` | 9 060 488 | 46 % | 4,9 | 66 | 1 |
| `D_2025_06_26_CanadaNegra` | 17 144 499 | 27 % | 26,6 | 7 005 | 2 351 |
| `D_2025_07_07_LaLoma_SanJose_SanCristobal` | 5 497 363 | 52 % | 2,6 | 49 | 5 |
| `D_2025_07_17_SubestacionSantaElena` | 35 495 119 | 70 % | 13,6 | 16 | 6 |
| `D_2025_07_25_Monitoreo_LasFlores_Granizal_Bello` | 39 895 095 | 25 % | 34,4 | 3 524 | 534 |
| `D_2025_08_11_Monitoreo_SantaRita` | 7 960 563 | 70 % | 4,1 | 1 028 | 8 |
| `D_2025_08_12_CinturonVerde` | 8 425 435 | 71 % | 3,6 | 96 | 50 |
| `D_2025_08_12_LosBalsos` | 22 125 050 | 61 % | 13,6 | 1 882 | 523 |
| `D_2025_08_13_LaPresidenta` | 15 407 982 | 75 % | 6,7 | 647 | 204 |
| `D_2025_08_19_LaChorrera_PaloBlanco` | 7 924 032 | 56 % | 8,8 | 2 178 | 676 |
| `D_2025_08_19_Lenocito` | 15 888 976 | 33 % | 11,5 | 484 | 47 |
| `D_2025_08_19_Pajarito` | 19 006 751 | 50 % | 11,2 | 253 | 83 |
| `D_2025_08_20_Carambolas` | 5 420 435 | 32 % | 6,1 | 203 | 140 |
| `D_2025_08_20_LaPalma` | 27 015 539 | 74 % | 10,9 | 193 | 65 |
| `D_2025_08_25_Deslizamiento_LaLoma` | 45 342 837 | 78 % | 15,9 | 41 | 24 |
| `D_2025_08_25_LaZorrita` | 4 182 338 | 67 % | 1,9 | 126 | 74 |
| `D_2025_08_26_EmergenciaElSalado` | 21 087 478 | 77 % | 7,2 | 26 | 7 |
| `D_2025_08_27_LaMontanita` | 21 041 715 | 76 % | 9,1 | 145 | 100 |
| `D_2025_08_27_Pollocoa` | 15 355 809 | 66 % | 7,1 | 222 | 47 |
| `D_2025_09_10_Barichara` | 53 621 155 | 48 % | 82,3 | 5 070 | 3 120 |
| `D_2025_09_10_Taboga` | 21 967 692 | 63 % | 17,5 | 907 | 343 |
| `D_2025_09_17_ElFaroLlanaditas` | 7 314 733 | 19 % | 14,3 | 322 | 166 |
| `D_2025_09_23_AguasFrias_Bocatoma` | 33 228 510 | 81 % | 14,2 | 352 | 209 |
| `D_2025_09_23_PanDeAzucar` | 41 810 484 | 38 % | 26,8 | 2 | 1 |
| `D_2025_10_22_Palmitas` | 22 806 307 | 76 % | 8,2 | 284 | 118 |
| **Total** | **969 044 789** | | **706,5** | | **16 923** |

**Incidencias**

- El primer intento se detuvo después del bloque de prueba por un error del lanzador local al medir la memoria (fuera del repositorio, no de `med_nube`). Se corrigió y se repitió todo desde cero.
- Ningún bloque cubre el Coltejer; el más cercano (Villatina) está a unos 2,6 km.
- Cinco de los 40 zip de origen no traen nube de puntos: uno trae solo una capa `.lyr`, otro solo el ortomosaico y tres solo productos ráster (Emergencia Altos de Oriente, Las Flores y La Balastrera). Ver P3.
- El filtro de vegetación (ExG > 0,10) retira entre el 15 % y el 83 % de los puntos según el bloque. No se ajustó nada.
- Hay vuelos repetidos sobre la misma zona (Santa Rita, Los Balsos, Bello Oriente): cada parte tomó el bloque con más puntos de techo (§3.2).
