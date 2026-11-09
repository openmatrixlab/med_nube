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

### 2026-11-09 · corrida completa de todo el municipio · commit `1b5caa5`

- **Máquina:** OSCAR_COSSIO · Intel64 Family 6 Model 198 (24 núcleos lógicos) · 63,4 GB de RAM · SSD · Windows 11.
- **Versiones:** Python 3.14.2 · numpy 2.5.4 · pyproj 3.8.0 · laspy 2.7.0 · shapely 2.2.0.
- **Huellas:** `huellas.gpkg` oficial (SHA-256 `dc50e37f…4f12` verificado).
- **Bloques:** 90 (259,2 GB; 8 332 033 555 puntos), preparados desde 192 comprimidos `.zip` y `.7z` con extracción verificada (CRC-32 y SHA-256): 17 teselas de 2022 (`2022_*`, LAS 1.4, «MAGNA-SIRGAS / Origen-Nacional») y 73 vuelos de dron de 2025 (`D_2025_*` y uno más, WGS 84 / UTM 18N), entre ellos los 36 del 1 de noviembre, sin cambios. Ver P3.
- **Rendimiento:** 5 000 000 puntos por trozo; procesos automáticos. Los bloques se reparten según la memoria (cada uno reserva 1 GB + 100 bytes por punto; al empezar la fase había 31,4 GB disponibles); geometrías y partes, 23 procesos.

**Un bloque real (paso 4).** `2022_10_09_I23_I24` (14,1 GB; 413 730 192 puntos), el único cuya caja contiene el Coltejer, con `huellas_coltejer.gpkg` (comparación sobre el Coltejer):

- 136,0 s con 5 000 000 puntos por trozo y 124,6 s con 1 000 000; memoria máxima del proceso: 16,0 GB.
- `alturas` y `techos` salen idénticas con los dos tamaños de trozo (26 partes en `alturas`, ninguna en `techos`).
- El Coltejer no recibe puntos de techo ni de suelo; entre los puntos del bloque que caen en techos o anillos de su entorno, los más cercanos están a unos 80 m de su huella.
- Extrapolación secuencial de la lectura al total: unos 46 min. La fase de bloques real tomó 3,3 h porque la memoria disponible obligó a leer las teselas de 2022 de a una.

**Corrida completa (paso 5).** 90 bloques, ninguno omitido; 8 332 033 555 puntos leídos, 5 484 652 629 tras ruido y vegetación.

- Tiempo: 4,7 h de reloj. Geometrías, 22,3 s (349 192 partes con área efectiva ≥ 4 m², de 528 500 huellas cerca de algún bloque); bloques, 3,27 h (la suma de los tiempos por bloque es 13 320,5 s); alturas y techos, 1,44 h (176 580 partes en 731 tareas).
- Entrega: `med_nube_entrega_20261109.gpkg` (32,9 MB), SHA-256 `1982a3db732a848dca86bc712976820ad40e71b779777624ce98f723bd5a5a75`.
- 176 580 partes en `alturas` (172 563 con suelo) y 155 044 en `techos` (plano 10 390, una_agua 18 881, dos_aguas 12 988, cuatro_aguas 32 426, otro 80 359). Mediana de h_p98: 5,5 m; 2 316 negativas (1,3 %); mediana de h_p98/pisos: 3,0 m.
- 126 937 partes toman sus valores de teselas de 2022 y 49 643 de vuelos de 2025.
- Validador sin `--prueba`: **APROBADA**. Única advertencia: ningún bloque cubre el Coltejer (§5.3).
- Frente a la entrega del 1 de noviembre: sus 16 923 partes siguen en `alturas`; 9 491 conservan el bloque y sus valores son idénticos en `alturas` y `techos`; 7 432 toman ahora otro bloque con más puntos de techo (§3.2), casi todas teselas de 2022.
- Caché de la corrida: unos 106 GB en `med_nube_salida/municipio_1b5caa5/intermedios`, fuera del repositorio; se conserva hasta que Luis apruebe la entrega.

| Bloque | Puntos | Vegetación | Lectura y asignación (s) | Partes cuyo bbox intersecta el bloque | Partes asignadas con ≥ 20 puntos de techo |
|---|---:|---:|---:|---:|---:|
| `2022_08_30_M14` | 123 020 082 | 11 % | 151,3 | 3 512 | 2 304 |
| `2022_08_30_M15` | 187 415 229 | 6 % | 309,4 | 4 802 | 2 903 |
| `2022_09_01_N17` | 265 110 384 | 34 % | 328,4 | 4 292 | 2 304 |
| `2022_09_01_Q15` | 340 580 971 | 16 % | 942,8 | 26 210 | 13 116 |
| `2022_09_08_M20` | 370 881 732 | 23 % | 632,5 | 5 582 | 3 697 |
| `2022_09_09_H12` | 332 739 091 | 30 % | 748,6 | 13 133 | 8 337 |
| `2022_09_09_H13` | 250 927 377 | 36 % | 395,7 | 8 891 | 2 195 |
| `2022_09_09_I11` | 261 927 147 | 55 % | 204,2 | 6 001 | 2 003 |
| `2022_09_09_I13` | 407 014 369 | 18 % | 1 220,8 | 21 915 | 8 799 |
| `2022_09_09_J14` | 274 430 768 | 17 % | 716,3 | 27 653 | 10 065 |
| `2022_09_09_J24` | 311 594 343 | 14 % | 1 040,4 | 31 020 | 11 732 |
| `2022_09_09_J25` | 256 427 835 | 13 % | 780,1 | 20 588 | 4 797 |
| `2022_09_12_K23` | 374 796 444 | 9 % | 1 360,6 | 28 061 | 15 329 |
| `2022_09_12_K24` | 428 657 224 | 16 % | 1 243,9 | 29 660 | 6 144 |
| `2022_10_09_I23_I24` | 413 730 192 | 26 % | 775,1 | 359 887 | 29 800 |
| `2022_10_27_J4` | 116 362 379 | 55 % | 37,6 | 712 | 359 |
| `2022_10_27_L6` | 177 277 799 | 38 % | 211,2 | 6 233 | 3 053 |
| `20250627_ViaSantaFe_LaLoma_cloud` | 20 863 576 | 75 % | 4,2 | 146 | 7 |
| `D_2025_02_11_SATC_OlayaHerrera` | 144 019 495 | 35 % | 166,0 | 13 958 | 7 329 |
| `D_2025_02_14_Acuarela_SanCristobal` | 89 029 713 | 63 % | 27,1 | 242 | 155 |
| `D_2025_02_14_SATC_NuevaVilla` | 283 531 350 | 48 % | 253,8 | 6 867 | 1 185 |
| `D_2025_02_17_LaMontanaLaverde` | 58 770 149 | 62 % | 29,5 | 914 | 435 |
| `D_2025_02_17_LaZorrita` | 37 818 625 | 42 % | 12,9 | 348 | 27 |
| `D_2025_02_17_TieraAlta` | 40 311 360 | 77 % | 11,0 | 213 | 57 |
| `D_2025_02_18_AvLasPalmaskm11` | 53 858 227 | 58 % | 19,3 | 492 | 146 |
| `D_2025_02_18_LaPalmera` | 61 177 148 | 75 % | 20,1 | 560 | 296 |
| `D_2025_02_19_LaEscombreraSanJavier` | 63 055 415 | 56 % | 24,1 | 1 644 | 670 |
| `D_2025_02_20_Montanita` | 82 451 049 | 72 % | 28,4 | 83 | 47 |
| `D_2025_02_20_TanqueSanJose` | 118 116 527 | 75 % | 25,8 | 49 | 23 |
| `D_2025_02_24_SATC_ColinasdeEnciso` | 48 139 934 | 25 % | 59,1 | 22 581 | 5 849 |
| `D_2025_02_26_LasFlores` | 114 391 964 | 37 % | 52,8 | 543 | 83 |
| `D_2025_02_27_SATC_JhonFKennedy` | 215 486 090 | 27 % | 392,6 | 15 692 | 5 328 |
| `D_2025_03_03_SATC_LasEstancias` | 92 117 327 | 26 % | 147,9 | 32 641 | 518 |
| `D_2025_03_07_ElPacifico` | 35 015 590 | 26 % | 22,5 | 2 861 | 759 |
| `D_2025_03_07_SATC_AltosDeLaTorre` | 43 483 784 | 26 % | 48,0 | 12 369 | 3 716 |
| `D_2025_03_10_LaPresidenta` | 33 409 219 | 16 % | 16,9 | 366 | 177 |
| `D_2025_03_10_NewSchool` | 39 893 652 | 34 % | 17,4 | 321 | 39 |
| `D_2025_03_11_PajaritoPartidas` | 39 309 664 | 34 % | 13,5 | 161 | 45 |
| `D_2025_03_11_PradoCampestre` | 110 712 220 | 48 % | 72,4 | 5 854 | 1 395 |
| `D_2025_03_12_SATC_VillaEsperanza` | 39 803 842 | 45 % | 37,8 | 11 147 | 2 356 |
| `D_2025_03_18_Leoncito` | 38 984 700 | 38 % | 17,7 | 253 | 82 |
| `D_2025_03_20_LaPalmaSanCristobal` | 33 532 629 | 55 % | 10,0 | 65 | 25 |
| `D_2025_05_01_Altavista_LaEsperanza` | 79 544 946 | 27 % | 37,8 | 2 210 | 1 116 |
| `D_2025_05_01_Altavista_LosKrisnas` | 50 539 480 | 74 % | 12,1 | 1 159 | 252 |
| `D_2025_05_02_AguasFrias_QPicacha` | 101 912 393 | 17 % | 46,7 | 507 | 164 |
| `D_2025_05_02_AltavistaLaPerla` | 65 907 262 | 60 % | 23,2 | 1 941 | 926 |
| `D_2025_05_02_BelencitoCorazon` | 62 974 624 | 83 % | 15,0 | 260 | 110 |
| `D_2025_05_03_LaFlorida` | 99 114 117 | 67 % | 29,2 | 522 | 234 |
| `D_2025_05_05_SantaRita` | 39 264 956 | 69 % | 18,4 | 1 836 | 218 |
| `D_2025_05_06_LosBalsos` | 35 824 645 | 61 % | 11,3 | 634 | 48 |
| `D_2025_05_10_LosBalsos` | 66 281 818 | 49 % | 28,1 | 1 063 | 211 |
| `D_2025_05_10_Robledo_ViaSanPedro` | 6 904 460 | 30 % | 3,3 | 1 652 | 520 |
| `D_2025_05_19_Golondrinas` | 7 325 700 | 49 % | 2,6 | 1 021 | 391 |
| `D_2025_05_20_ManoDeDios_Altavista` | 42 680 752 | 47 % | 34,5 | 4 261 | 2 592 |
| `D_2025_05_22_SanAntonioDePrado_Occidental` | 100 321 314 | 58 % | 43,5 | 7 948 | 2 877 |
| `D_2025_05_22_Villatina` | 33 654 193 | 15 % | 58,7 | 5 913 | 440 |
| `D_2025_05_23_SantaRita` | 47 327 760 | 70 % | 20,9 | 2 197 | 444 |
| `D_2025_05_26_SantaRita` | 49 083 621 | 72 % | 21,2 | 2 123 | 273 |
| `D_2025_06_24_Emergencia_BelloOriente` | 9 060 488 | 46 % | 2,7 | 66 | 0 |
| `D_2025_06_26_CanadaNegra` | 17 144 499 | 27 % | 19,5 | 7 005 | 7 |
| `D_2025_07_07_LaLoma_SanJose_SanCristobal` | 5 497 363 | 52 % | 1,6 | 49 | 5 |
| `D_2025_07_17_SubestacionSantaElena` | 35 495 119 | 70 % | 7,8 | 16 | 6 |
| `D_2025_07_25_Monitoreo_LasFlores_Granizal_Bello` | 39 895 095 | 25 % | 21,3 | 3 524 | 20 |
| `D_2025_08_11_Monitoreo_SantaRita` | 7 960 563 | 70 % | 2,5 | 1 028 | 8 |
| `D_2025_08_12_CinturonVerde` | 8 425 435 | 71 % | 1,9 | 96 | 3 |
| `D_2025_08_12_LosBalsos` | 22 125 050 | 61 % | 7,7 | 1 882 | 282 |
| `D_2025_08_13_LaPresidenta` | 15 407 982 | 75 % | 4,1 | 647 | 104 |
| `D_2025_08_19_LaChorrera_PaloBlanco` | 7 924 032 | 56 % | 5,9 | 2 178 | 463 |
| `D_2025_08_19_Lenocito` | 15 888 976 | 33 % | 6,6 | 484 | 18 |
| `D_2025_08_19_Pajarito` | 19 006 751 | 50 % | 7,6 | 253 | 48 |
| `D_2025_08_20_Carambolas` | 5 420 435 | 32 % | 3,7 | 203 | 140 |
| `D_2025_08_20_LaPalma` | 27 015 539 | 74 % | 6,2 | 193 | 22 |
| `D_2025_08_25_Deslizamiento_LaLoma` | 45 342 837 | 78 % | 10,8 | 41 | 23 |
| `D_2025_08_25_LaZorrita` | 4 182 338 | 67 % | 1,0 | 126 | 0 |
| `D_2025_08_26_EmergenciaElSalado` | 21 087 478 | 77 % | 4,2 | 26 | 7 |
| `D_2025_08_27_LaMontanita` | 21 041 715 | 76 % | 5,4 | 145 | 50 |
| `D_2025_08_27_Pollocoa` | 15 355 809 | 66 % | 4,3 | 222 | 42 |
| `D_2025_09_08_MonitoreoPacifico` | 3 928 454 | 51 % | 2,5 | 3 024 | 24 |
| `D_2025_09_08_MonitoreoVillatina` | 3 665 225 | 46 % | 2,3 | 4 856 | 139 |
| `D_2025_09_10_Barichara` | 53 621 155 | 48 % | 57,5 | 5 070 | 2 246 |
| `D_2025_09_10_Taboga` | 21 967 692 | 63 % | 11,1 | 907 | 317 |
| `D_2025_09_10_TanqueSanJose` | 8 480 094 | 61 % | 2,2 | 1 | 0 |
| `D_2025_09_11_Monitoreo_LasFlores_Granizal_Bello` | 21 033 135 | 39 % | 8,8 | 2 735 | 0 |
| `D_2025_09_16_TierraAltaLaMontana` | 28 091 255 | 76 % | 10,2 | 480 | 72 |
| `D_2025_09_17_ElFaroLlanaditas` | 7 314 733 | 19 % | 11,3 | 322 | 125 |
| `D_2025_09_23_AguasFrias_Bocatoma` | 33 228 510 | 81 % | 9,1 | 352 | 159 |
| `D_2025_09_23_Leoncito` | 17 120 097 | 35 % | 11,2 | 1 372 | 66 |
| `D_2025_09_23_PanDeAzucar` | 41 810 484 | 38 % | 18,2 | 2 | 1 |
| `D_2025_10_13_Picacho` | 6 850 254 | 18 % | 10,1 | 12 962 | 3 563 |
| `D_2025_10_22_Palmitas` | 22 806 307 | 76 % | 5,0 | 284 | 118 |
| **Total** | **8 332 033 555** | | **13 320,5** | | **176 580** |

**Incidencias**

- **Primer intento** (commit `a6b31e0`, 2026-11-08 desde las 15:35): leyó los 90 bloques y se detuvo a las 21:14, en la fase de partes, por falta de memoria (`MemoryError` en `np.searchsorted`). Causa: `_tramo()` buscaba con una clave int64 en `techo_parte`/`suelo_parte` (int32, abiertos como memmap) y NumPy convertía el arreglo completo a int64 en cada búsqueda, cuatro veces por parte (1,6 GiB por búsqueda en las teselas de 2022). Se corrigió en `1b5caa5` pasando la clave con el tipo del arreglo: misma búsqueda, mismo resultado, sin copia. Prueba nueva: `tests/test_proc_tramo.py`, que falla con el código anterior. No cambió ningún parámetro ni prueba existente. Su caché (unos 106 GB) se conserva en `med_nube_salida/municipio_a6b31e0`.
- **Segundo intento** (`1b5caa5`, 23:27): las 50 pruebas pasaron, pero pytest terminó con error al limpiar su carpeta temporal compartida de Windows (`PermissionError` en `pytest-of-ingos/pytest-current`) y el lanzador local se detuvo antes de la corrida. Desde entonces el lanzador (fuera del repositorio) corre pytest con `--basetemp` en una carpeta nueva. No cambió ninguna prueba ni la configuración del repositorio.
- La caja de `2022_10_09_I23_I24` abarca 56 km² (las demás teselas, unos 2 km²), así que es candidata para unas 359 000 huellas. Contiene el Coltejer, pero ninguno de sus puntos cae en su huella ni en su anillo.
- Las 17 teselas de 2022 declaran «MAGNA-SIRGAS / Origen-Nacional» sin código EPSG; pyproj no lo da por igual a EPSG:9377 y se transforman, como pide §3.1. Sus esquinas se desplazan 0,0000 m.
- Los comprimidos de los vuelos de 2021 traen solo ortomosaicos, sin nube de puntos; uno (`imagen1_D_2021_03_12_0713_2.7z`) trae dentro otro `.zip` que no se abrió. Una copia descargada dos veces (`imagen2157_L_2022_09_09_I13 (1).7z`) se extrajo una sola vez. Ver P3.
- Cobertura: 176 580 de las 976 829 huellas (18 %) tienen alturas. Ver P3.
