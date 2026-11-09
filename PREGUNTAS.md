# Preguntas abiertas

Formato: una entrada por duda. No se elige opción por cuenta propia: se sigue con lo demás hasta que Luis responda.

<!--
## P1 · §3.x — título corto
- **Duda:** …
- **Opciones:** A) … B) …
- **Impacto si no se resuelve:** …
- **Respuesta (Luis):** …
-->

## P1 · §3.1.3 — Máximo de RGB: uno común o uno por canal
- **Duda:** «La normalización a [0, 1] depende del máximo de R, G y B sobre todos los puntos del archivo… Si ese máximo es mayor que 255, se divide por 65535». ¿Es un solo máximo para los tres canales o uno por canal, cada uno con su divisor?
- **Opciones:** A) Un solo máximo sobre R, G y B; el mismo divisor para los tres (lectura literal: «ese máximo», en singular). B) Un máximo y un divisor por canal.
- **Impacto si no se resuelve:** solo cambiaría el ExG de un archivo con un canal por encima de 255 y otro por debajo. En los 36 bloques reales el máximo es 65 280; en el escenario sintético los tres canales están en la misma escala.
- **Elegida provisionalmente:** A (`# P1` en `src/med_nube/proc_lectura.py`).
- **Respuesta (Luis):** …

## P2 · §3.1.1 y §3.1.4 — Qué excepción equivale a «sin CRS»
- **Duda:** §3.1.1.2: si `laspy.open(ruta).header.parse_crs()` «devuelve None o lanza excepción», se busca `<stem>.crs`. §3.1.4: un archivo corrupto o un error de laspy detiene la corrida. Si lo que falla es abrir el archivo (no `parse_crs()`), ¿se trata como «sin CRS» o se detiene?
- **Opciones:** A) Solo una excepción de `parse_crs()` cuenta como «sin CRS»; si el archivo no abre, la corrida se detiene (§3.1.4). B) Cualquier excepción, incluida la de abrir el archivo, cuenta como «sin CRS».
- **Impacto si no se resuelve:** ninguno con los datos actuales: los 36 bloques abren y traen el CRS en la cabecera (WGS 84 / UTM 18N).
- **Elegida provisionalmente:** A (`# P2` en `src/med_nube/proc_lectura.py`).
- **Respuesta (Luis):** …

## P3 · §2, §3.2 y §5.4 — Conjunto de bloques para la entrega
- **Duda:** la carpeta de bloques tiene ahora 90 bloques (259,2 GB; 8 332 millones de puntos) de dos campañas: 17 teselas de 2022 (`2022_*`, de 3,7 a 14,1 GB, como el bloque típico de `AGENTS.md`) y 73 vuelos de dron de 2025 (`D_2025_*` y uno más), entre ellos los 36 del 1 de noviembre. Conviene confirmar que es el conjunto previsto, porque:
  - Las campañas se mezclan: donde se solapan, cada parte toma el bloque con más puntos de techo (§3.2), sin importar la fecha. En la corrida del 9 de noviembre, 126 937 partes salen de 2022 y 49 643 de 2025; 7 432 partes de la entrega del 1 de noviembre pasan de un vuelo de 2025 a una tesela de 2022.
  - La cobertura no es total: 176 580 de 976 829 huellas (18 %) tienen alturas.
  - El Coltejer sigue sin cubrir: queda dentro de la caja de `2022_10_09_I23_I24` (56 km², mucho mayor que las demás teselas), pero ninguno de sus puntos cae en su huella ni en su anillo; los más cercanos registrados están a unos 80 m (§5.3).
  - Los comprimidos de los vuelos de 2021 traen solo ortomosaicos, sin nube de puntos; uno (`imagen1_D_2021_03_12_0713_2.7z`) trae dentro otro `.zip` que no se abrió. Siguen sin nube los tres vuelos de 2025 ya citados (Emergencia Altos de Oriente, Las Flores y La Balastrera) e `imagen2241_D_2025_02_10_7004.7z`.
  - Siguen los vuelos repetidos sobre la misma zona (Santa Rita, Los Balsos, Bello Oriente / Las Flores), además de vuelos de emergencia y monitoreo.
- **Opciones:** A) Mantener los 90 bloques; §3.2 decide por puntos de techo. B) Dar prioridad a una campaña (por ejemplo, la más reciente); exigiría una regla nueva en el contrato. C) Otro conjunto de bloques (retirar o añadir).
- **Impacto si no se resuelve:** define qué partes salen en la entrega y de qué campaña; no cambia el código.
- **Elegida provisionalmente:** A.
- **Antecedente:** el 1 de noviembre la carpeta tenía 36 bloques (26,7 GB, 969 millones de puntos), sin bloques de ~9 GB y sin el Coltejer; también se eligió A provisionalmente.
- **Respuesta (Luis):** …
