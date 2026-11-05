"""Descarga cada fuente desde su URL oficial y deja constancia en un manifiesto.

Para cada recurso se guarda: URL usada, fecha y hora de descarga (UTC), tamaño, SHA-256,
licencia declarada en el catálogo y fecha de última modificación según el portal.
El manifiesto vive en el repositorio (`fuentes/manifiesto.json`) para que cualquiera pueda
comprobar que trabaja con los mismos ficheros.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import time
import urllib.parse
import urllib.request

from .fuentes import API, FUENTES, Fuente

UA = {"User-Agent": "radar-natalidad-municipal/1.0 (datos abiertos; https://datos.comunidad.madrid)"}
PAUSA_S = 1.5


def _get(url: str, intentos: int = 3, timeout: int = 180) -> bytes:
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - se reintenta y, si no, se propaga
            ultimo = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo}")


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def metadatos(dataset: str, dir_meta: pathlib.Path, forzar: bool) -> dict:
    p = dir_meta / f"{dataset}.json"
    if forzar or not p.exists():
        p.write_bytes(_get(API + "package_show?id=" + urllib.parse.quote(dataset)))
        time.sleep(PAUSA_S)
    return json.loads(p.read_bytes())["result"]


def localizar_recurso(meta: dict, fuente: Fuente) -> dict:
    """Recurso cuya URL coincide con la registrada; si no, el de mismo nombre y formato."""
    recursos = meta.get("resources", [])
    for r in recursos:
        if r.get("url") == fuente.url:
            return r
    ext = fuente.fichero.rsplit(".", 1)[-1].lower()
    formato = {"csv": "CSV", "zip": "SHP"}.get(ext, ext.upper())
    for r in recursos:
        if (r.get("name") or "").strip().lower() == fuente.recurso.lower() and (r.get("format") or "").upper() == formato:
            return r
    raise LookupError(f"El dataset {fuente.dataset} ya no tiene el recurso «{fuente.recurso}»")


def descargar(dir_datos: pathlib.Path, manifiesto: pathlib.Path, forzar: bool = False) -> list[dict]:
    crudos = dir_datos / "crudos"
    dir_meta = crudos / "metadatos"
    dir_meta.mkdir(parents=True, exist_ok=True)
    previo = {}
    if manifiesto.exists():
        previo = {e["clave"]: e for e in json.loads(manifiesto.read_text(encoding="utf-8"))["recursos"]}
    entradas = []
    for f in FUENTES:
        meta = metadatos(f.dataset, dir_meta, forzar)
        rec = localizar_recurso(meta, f)
        url = rec["url"]
        destino = crudos / f.fichero
        if forzar or not destino.exists() or destino.stat().st_size == 0:
            datos = _get(url)
            destino.write_bytes(datos)
            fecha = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
            time.sleep(PAUSA_S)
            print(f"descargado  {f.clave:<24} {len(datos):>10,} B")
        else:
            fecha = previo.get(f.clave, {}).get("fecha_descarga_utc")
            if fecha is None:
                fecha = dt.datetime.fromtimestamp(destino.stat().st_mtime, dt.timezone.utc).replace(microsecond=0).isoformat()
            print(f"en caché    {f.clave:<24} {destino.stat().st_size:>10,} B")
        entradas.append(dict(
            clave=f.clave, dataset=f.dataset, titulo=f.titulo, recurso=rec.get("name"), editor=f.editor,
            pagina=f.pagina, url=url, fichero=f.fichero, fecha_descarga_utc=fecha,
            bytes=destino.stat().st_size, sha256=sha256(destino),
            licencia=meta.get("license_id"), licencia_titulo=meta.get("license_title"),
            modificado_en_portal=rec.get("last_modified") or rec.get("metadata_modified") or meta.get("metadata_modified"),
            uso=f.uso,
        ))
    manifiesto.parent.mkdir(parents=True, exist_ok=True)
    manifiesto.write_text(json.dumps({
        "portal": "https://datos.comunidad.madrid",
        "nota": "Generado por `python -m radar descargar`. Fechas en UTC.",
        "recursos": entradas,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return entradas
