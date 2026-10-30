"""Validador de la entrega (docs/contrato.md §4 y §5).

Lee el GeoPackage con sqlite3 (no requiere GDAL) y devuelve errores, advertencias y
un resumen. Un solo error = entrega rechazada.

NO MODIFICAR para hacer pasar una entrega: si el validador parece estar mal,
escribirlo en PREGUNTAS.md.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
from pathlib import Path
from statistics import median

from . import contrato as C

GPKG_APPLICATION_ID = 0x47504B47  # 'GPKG'
FAMILIAS_TIPO = {
    "INTEGER": {"INTEGER", "INT", "BIGINT", "MEDIUMINT", "SMALLINT", "TINYINT"},
    "REAL": {"REAL", "DOUBLE", "FLOAT"},
    "TEXT": {"TEXT"},
}
TOL = 1e-6
TOL_H = 0.01


@dataclass
class Resultado:
    errores: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    resumen: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errores

    def error(self, msg: str) -> None:
        self.errores.append(msg)

    def advertir(self, msg: str) -> None:
        self.advertencias.append(msg)


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _familia(tipo_sql: str) -> str | None:
    base = re.sub(r"\(.*\)", "", tipo_sql or "").strip().upper()
    for familia, nombres in FAMILIAS_TIPO.items():
        if base in nombres:
            return familia
    return None


def _filas(con: sqlite3.Connection, tabla: str, columnas: list[str]) -> list[dict]:
    sql = f"SELECT {', '.join(f'[{c}]' for c in columnas)} FROM [{tabla}]"
    return [dict(zip(columnas, fila, strict=True)) for fila in con.execute(sql)]


def _ids_huellas(ruta: Path) -> dict[str, int]:
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        filas = con.execute(f"SELECT id_parte, pisos FROM [{C.HUELLAS_CAPA}]").fetchall()
    finally:
        con.close()
    ids = {i: (p or 0) for i, p in filas}
    if len(ids) != len(filas):
        raise ValueError(f"'{ruta}' tiene id_parte repetidos: no es un archivo de huellas válido")
    return ids


def _revisar_estructura(con: sqlite3.Connection, r: Resultado) -> bool:
    (app_id,) = con.execute("PRAGMA application_id").fetchone()
    if app_id != GPKG_APPLICATION_ID:
        r.error("El archivo no es un GeoPackage (application_id distinto de 'GPKG').")
        return False
    contenidos = dict(con.execute("SELECT table_name, data_type FROM gpkg_contents"))
    if set(contenidos) != set(C.TABLAS):
        r.error(f"Tablas en gpkg_contents {sorted(contenidos)}; se esperan {sorted(C.TABLAS)}.")
        return False
    for tabla, tipo in contenidos.items():
        if tipo != "attributes":
            r.error(f"La tabla '{tabla}' es '{tipo}'; debe ser 'attributes' (sin geometría).")
    try:
        geom = con.execute("SELECT COUNT(*) FROM gpkg_geometry_columns").fetchone()[0]
    except sqlite3.OperationalError:
        geom = 0
    if geom:
        r.error("El GeoPackage tiene columnas de geometría; no debe tener ninguna.")
    for tabla, esperadas in C.TABLAS.items():
        info = con.execute(f"PRAGMA table_info([{tabla}])").fetchall()
        reales = {fila[1]: fila[2] for fila in info if fila[1] != "fid"}
        if list(reales) != list(esperadas):
            r.error(f"'{tabla}': columnas {list(reales)}; se esperan {list(esperadas)} (en orden).")
            continue
        for col, (tipo, _) in esperadas.items():
            if _familia(reales[col]) != tipo:
                r.error(f"'{tabla}.{col}': tipo '{reales[col]}'; se espera {tipo}.")
    return not r.errores


def _revisar_nulos_y_tipos(tabla: str, filas: list[dict], r: Resultado) -> None:
    for col, (tipo, nulo) in C.TABLAS[tabla].items():
        malos_nulos = sum(1 for f in filas if f[col] is None)
        if malos_nulos and not nulo:
            r.error(f"'{tabla}.{col}': {malos_nulos} valores NULL (no se admiten).")
        if tipo == "REAL":
            nan = sum(1 for f in filas if isinstance(f[col], float) and not math.isfinite(f[col]))
            if nan:
                r.error(f"'{tabla}.{col}': {nan} valores NaN/inf.")


def _revisar_metadatos(filas: list[dict], huellas: Path, oficial: bool, r: Resultado) -> list[str]:
    meta = {}
    for f in filas:
        if f["clave"] in meta:
            r.error(f"metadatos: clave repetida '{f['clave']}'.")
        meta[f["clave"]] = f["valor"]
    if sorted(meta) != sorted(C.CLAVES_METADATOS):
        r.error(f"metadatos: claves {sorted(meta)}; se esperan {sorted(C.CLAVES_METADATOS)}.")
        return []
    if meta["version_contrato"] != C.VERSION_CONTRATO:
        r.error(f"version_contrato '{meta['version_contrato']}'; se espera {C.VERSION_CONTRATO}.")
    try:
        fecha = datetime.fromisoformat(meta["fecha_proceso"])
        if fecha.tzinfo is None:
            r.error("fecha_proceso sin zona horaria.")
    except ValueError:
        r.error(f"fecha_proceso no es ISO 8601: '{meta['fecha_proceso']}'.")
    if not re.fullmatch(r"[0-9a-f]{7,40}", meta["commit"] or ""):
        r.error(f"commit no es un hash de git: '{meta['commit']}'.")
    hash_huellas = sha256(huellas)
    if meta["huellas_sha256"] != hash_huellas:
        r.error("metadatos.huellas_sha256 no corresponde al archivo de huellas indicado.")
    if oficial and hash_huellas != C.HUELLAS_SHA256:
        r.error(f"'{huellas}' no es el huellas.gpkg oficial (SHA-256 distinto).")
    bloques: list[str] = []
    try:
        bloques = json.loads(meta["bloques"])
        if not (isinstance(bloques, list) and all(isinstance(b, str) for b in bloques)):
            raise ValueError
        if bloques != sorted(bloques) or len(set(bloques)) != len(bloques):
            r.error("bloques: la lista debe estar ordenada y sin repetidos.")
    except ValueError:
        r.error("bloques: debe ser una lista JSON de textos.")
        bloques = []
    if not bloques:
        r.error("bloques: no se procesó ningún bloque.")
    for clave in ("bloques_omitidos", "bloques_advertencias"):
        try:
            valor = json.loads(meta[clave])
            if not isinstance(valor, dict):
                raise ValueError
        except ValueError:
            r.error(f"{clave}: debe ser un objeto JSON.")
            continue
        r.resumen[clave] = valor
        if clave == "bloques_omitidos":
            if set(valor) & set(bloques):
                r.error("Un bloque no puede estar a la vez en bloques y bloques_omitidos.")
            malos = {b: m for b, m in valor.items() if m not in C.MOTIVOS_OMISION}
            if malos:
                r.error(
                    f"bloques_omitidos con motivos no permitidos {malos}: "
                    f"solo {list(C.MOTIVOS_OMISION)}; cualquier otra falla detiene la corrida."
                )
        elif valor:
            r.error("bloques_advertencias debe ser {} en la versión 1.0.")
    r.resumen["bloques"] = bloques
    return bloques


def _cerca(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def _revisar_alturas(
    filas: list[dict], ids: dict[str, int], bloques: list[str], r: Resultado
) -> dict[str, dict]:
    por_id: dict[str, dict] = {}
    problemas: dict[str, int] = {}

    def anotar(motivo: str) -> None:
        problemas[motivo] = problemas.get(motivo, 0) + 1

    for f in filas:
        i = f["id_parte"]
        if i in por_id:
            anotar("id_parte repetido")
        por_id[i] = f
        if i not in ids:
            anotar("id_parte que no existe en huellas")
        if f["bloque"] not in bloques:
            anotar("bloque que no está en metadatos.bloques")
        if f["n_puntos"] is None or f["n_puntos"] < C.MIN_PUNTOS_TECHO:
            anotar(f"n_puntos < {C.MIN_PUNTOS_TECHO}")
        if f["cobertura"] is None or not (0.0 <= f["cobertura"] <= 1.0):
            anotar("cobertura fuera de [0, 1]")
        zs = [f[c] for c in ("z_p10", "z_p50", "z_p90", "z_p98", "z_max")]
        if None not in zs and any(a > b + TOL for a, b in pairwise(zs)):
            anotar("percentiles no ordenados (z_p10 ≤ z_p50 ≤ z_p90 ≤ z_p98 ≤ z_max)")
        ns = f["n_puntos_suelo"]
        if ns is None or ns < 0:
            anotar("n_puntos_suelo inválido")
            continue
        sin_suelo = ns < C.MIN_PUNTOS_SUELO
        if sin_suelo != (f["z_suelo"] is None):
            anotar(f"z_suelo debe ser NULL si y solo si n_puntos_suelo < {C.MIN_PUNTOS_SUELO}")
        if f["z_suelo"] is None:
            if f["h_p50"] is not None or f["h_p98"] is not None:
                anotar("h_p50/h_p98 deben ser NULL si z_suelo es NULL")
        elif None in (f["h_p50"], f["h_p98"]) or not (
            _cerca(f["h_p50"], f["z_p50"] - f["z_suelo"], TOL_H)
            and _cerca(f["h_p98"], f["z_p98"] - f["z_suelo"], TOL_H)
        ):
            anotar("h_p50/h_p98 no son z_p50/z_p98 − z_suelo")
    for motivo, n in sorted(problemas.items()):
        r.error(f"alturas: {n} filas con {motivo}.")
    return por_id


def _revisar_techos(filas: list[dict], alturas: dict[str, dict], r: Resultado) -> None:
    problemas: dict[str, int] = {}

    def anotar(motivo: str) -> None:
        problemas[motivo] = problemas.get(motivo, 0) + 1

    vistos = set()
    for f in filas:
        i = f["id_parte"]
        if i in vistos:
            anotar("id_parte repetido")
        vistos.add(i)
        a = alturas.get(i)
        if a is None:
            anotar("id_parte que no está en alturas")
        elif a["n_puntos"] < C.MIN_PUNTOS_TECHOS or a["cobertura"] < C.MIN_COBERTURA_TECHOS:
            anotar("parte que no cumple n_puntos ≥ 50 y cobertura ≥ 0,5")
        forma, n = f["forma"], f["n_planos"]
        pend, caida, cumbre = f["pendiente_deg"], f["azimut_caida_deg"], f["azimut_cumbrera_deg"]
        if forma not in C.FORMAS:
            anotar("forma no permitida")
            continue
        if n is None or not (0 <= n <= C.RANSAC_MAX_PLANOS):
            anotar("n_planos fuera de 0–4")
            continue
        if not (0.0 <= (f["frac_inliers"] or 0.0) <= 1.0):
            anotar("frac_inliers fuera de [0, 1]")
        if n == 0:
            if forma != "otro" or pend is not None or f["rmse_m"] is not None or caida is not None:
                anotar("con 0 planos: forma 'otro' y pendiente/azimut/rmse NULL")
            if f["frac_inliers"] not in (0, 0.0):
                anotar("con 0 planos frac_inliers debe ser 0")
            continue
        if pend is None or not (0.0 <= pend <= C.RANSAC_PENDIENTE_MAX_DEG + TOL):
            anotar("pendiente_deg fuera de [0, 70]")
            continue
        if f["rmse_m"] is None or not (0.0 <= f["rmse_m"] <= C.RANSAC_TOLERANCIA_M + TOL):
            anotar("rmse_m fuera de [0, 0,10]")
        inclinado = pend >= C.PENDIENTE_PLANO_DEG
        if inclinado != (caida is not None):
            anotar("azimut_caida_deg debe existir si y solo si pendiente ≥ 5°")
        if caida is not None and not (0.0 <= caida < 360.0):
            anotar("azimut_caida_deg fuera de [0, 360)")
        if cumbre is not None and not (0.0 <= cumbre < 180.0):
            anotar("azimut_cumbrera_deg fuera de [0, 180)")
        if forma not in ("dos_aguas", "cuatro_aguas") and cumbre is not None:
            anotar("azimut_cumbrera_deg solo para dos_aguas/cuatro_aguas")
        if forma == "dos_aguas" and (n != 2 or cumbre is None or not inclinado):
            anotar("dos_aguas exige 2 planos inclinados y azimut_cumbrera_deg")
        if forma == "plano" and inclinado:
            anotar("plano exige pendiente < 5°")
        if forma == "una_agua" and (n != 1 or not inclinado):
            anotar("una_agua exige 1 plano con pendiente ≥ 5°")
        if forma == "cuatro_aguas" and (n not in (3, 4) or not inclinado):
            anotar("cuatro_aguas exige 3 o 4 planos inclinados")
    faltan = [
        i
        for i, a in alturas.items()
        if a["n_puntos"] >= C.MIN_PUNTOS_TECHOS
        and a["cobertura"] >= C.MIN_COBERTURA_TECHOS
        and i not in vistos
    ]
    if faltan:
        problemas["partes de alturas que cumplen el umbral y faltan en techos"] = len(faltan)
    for motivo, n in sorted(problemas.items()):
        r.error(f"techos: {n} filas con {motivo}.")


def _resumen(alturas: dict[str, dict], techos: list[dict], ids: dict[str, int], r: Resultado):
    hs = [a["h_p98"] for a in alturas.values() if a["h_p98"] is not None]
    razones = [
        a["h_p98"] / ids[i]
        for i, a in alturas.items()
        if a["h_p98"] is not None and (ids.get(i) or 0) > 0
    ]
    formas: dict[str, int] = {}
    for t in techos:
        formas[t["forma"]] = formas.get(t["forma"], 0) + 1
    por_bloque: dict[str, int] = {}
    for a in alturas.values():
        por_bloque[a["bloque"]] = por_bloque.get(a["bloque"], 0) + 1
    r.resumen.update(
        {
            "partes_alturas": len(alturas),
            "partes_con_suelo": len(hs),
            "partes_techos": len(techos),
            "formas": formas,
            "partes_por_bloque": por_bloque,
            "h_p98_mediana_m": round(median(hs), 2) if hs else None,
            "h_p98_negativas": sum(1 for h in hs if h < 0),
            "metros_por_piso_mediana": round(median(razones), 2) if razones else None,
        }
    )
    if hs and sum(1 for h in hs if h < 0) / len(hs) > 0.02:
        r.advertir("Más del 2 % de las partes tiene h_p98 negativa: revisar el anillo de suelo.")
    mpp = r.resumen["metros_por_piso_mediana"]
    if mpp is not None and not (2.0 <= mpp <= 4.5):
        r.advertir(f"Mediana de h_p98/pisos = {mpp} m: se esperaba entre 2,0 y 4,5.")


def _revisar_coltejer(alturas: dict[str, dict], r: Resultado) -> None:
    a = alturas.get(C.COLTEJER_ID)
    if a is None:
        r.advertir(
            f"Coltejer ({C.COLTEJER_ID}) no está en alturas: "
            "decir explícitamente en la entrega si ningún bloque lo cubre."
        )
        r.resumen["coltejer"] = None
        return
    r.resumen["coltejer"] = {
        k: a[k] for k in ("bloque", "n_puntos", "cobertura", "z_max", "z_suelo", "h_p98")
    }
    h = a["h_p98"]
    if h is None or not (C.COLTEJER_H_P98_MIN <= h <= C.COLTEJER_H_P98_MAX):
        r.advertir(
            "REVISAR — "
            f"Coltejer: h_p98 = {h}; se esperaba entre {C.COLTEJER_H_P98_MIN} "
            f"y {C.COLTEJER_H_P98_MAX} m. No ajustar parámetros: reportarlo en la entrega."
        )


def validar(entrega: Path, huellas: Path, oficial: bool = True) -> Resultado:
    """Valida una entrega. `oficial=False` (modo prueba) acepta cualquier archivo de
    huellas, p. ej. huellas_coltejer.gpkg; una entrega real siempre es oficial."""
    r = Resultado()
    r.resumen["modo"] = "oficial" if oficial else "PRUEBA (no vale como entrega)"
    entrega, huellas = Path(entrega), Path(huellas)
    if not re.fullmatch(r"med_nube_entrega_\d{8}\.gpkg", entrega.name):
        r.error(f"Nombre '{entrega.name}': debe ser med_nube_entrega_AAAAMMDD.gpkg.")
    for ruta in (entrega, huellas):
        if not ruta.is_file():
            r.error(f"No existe '{ruta}'.")
    if not r.ok:
        return r
    con = sqlite3.connect(f"file:{entrega}?mode=ro", uri=True)
    try:
        if not _revisar_estructura(con, r):
            return r
        datos = {t: _filas(con, t, list(cols)) for t, cols in C.TABLAS.items()}
    finally:
        con.close()
    for tabla, filas in datos.items():
        _revisar_nulos_y_tipos(tabla, filas, r)
    bloques = _revisar_metadatos(datos["metadatos"], huellas, oficial, r)
    ids = _ids_huellas(huellas)
    alturas = _revisar_alturas(datos["alturas"], ids, bloques, r)
    _revisar_techos(datos["techos"], alturas, r)
    _resumen(alturas, datos["techos"], ids, r)
    _revisar_coltejer(alturas, r)
    return r


def reporte(r: Resultado) -> str:
    lineas = ["RESULTADO: " + ("APROBADA" if r.ok else "RECHAZADA"), ""]
    if r.errores:
        lineas += ["Errores:", *[f"  - {e}" for e in r.errores], ""]
    if r.advertencias:
        lineas += ["Advertencias:", *[f"  - {a}" for a in r.advertencias], ""]
    lineas += ["Resumen:", json.dumps(r.resumen, ensure_ascii=False, indent=2)]
    return "\n".join(lineas)
