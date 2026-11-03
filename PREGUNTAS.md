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

## P3 · §2 y §5.4 — Conjunto de bloques para la entrega
- **Duda:** la carpeta preparada tiene 36 bloques (26,7 GB, 969 millones de puntos). Antes de la corrida completa conviene confirmar que es el conjunto previsto, porque:
  - `AGENTS.md` describe bloques típicos de ~9 GB y ~270 millones de puntos; aquí el mayor tiene 3,4 GB y 99 millones.
  - Ningún bloque cubre el Coltejer: el más cercano (Villatina) está a ~2,6 km (§5.3).
  - Tres vuelos solo traen ráster, sin `.las`: Emergencia Altos de Oriente, Las Flores y La Balastrera (2025-06-25/26).
  - Hay vuelos repetidos sobre la misma zona: Santa Rita (seis entre mayo y septiembre), Los Balsos (dos), Bello Oriente / Las Flores (dos), además de vuelos de emergencia y monitoreo.
- **Opciones:** A) Correr con los 36 bloques tal como están; cada parte toma el bloque con más puntos de techo (§3.2). B) Otro conjunto (añadir bloques que falten o retirar vuelos repetidos).
- **Impacto si no se resuelve:** define qué partes salen en la entrega y de qué vuelo; no cambia el código.
- **Elegida provisionalmente:** A.
- **Respuesta (Luis):** …
