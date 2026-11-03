"""Los pasos del procedimiento operativo, leidos del documento.

La consola los muestra tal cual: el titulo y la explicacion de cada paso son
texto del documento, no una copia. Lo que se anota aparte -quien hace cada
paso y como, en la demo- vive en casos_demo.yml.
"""
import os
import re

from fuentes import DEMO

DOC = os.path.normpath(os.path.join(DEMO, "..", "1-fuente", "BPD-Procedimiento-Operativo.md"))

_TITULO = re.compile(r"^#{2,4}\s+(\d+(?:\.\d+)*)\s")
_FILA = re.compile(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*$")
_ENLACE = re.compile(r"\[([^\]]+)\]\(#[^)]*\)")
_cache = {"mtime": None, "secciones": {}}


def _limpio(t):
    t = _ENLACE.sub(lambda m: "§" + m.group(1), t)
    return re.sub(r"\s+", " ", t.replace("**", "")).strip()


def _leer():
    """{seccion: [paso, ...]} con las tablas de pasos de cada seccion numerada.
    Un titulo sin numero -las fases del 3.2- sigue en la seccion anterior."""
    mtime = os.path.getmtime(DOC)
    if _cache["mtime"] == mtime:
        return _cache["secciones"]
    secciones, actual = {}, None
    with open(DOC, encoding="utf-8") as f:
        for linea in f:
            m = _TITULO.match(linea)
            if m:
                actual = m.group(1)
                continue
            m = _FILA.match(linea.rstrip("\n"))
            if m and actual:
                titulo, _, explicacion = m.group(2).partition("<br>")
                secciones.setdefault(actual, []).append(
                    {"n": int(m.group(1)), "titulo": _limpio(titulo), "explicacion": _limpio(explicacion)})
    _cache.update(mtime=mtime, secciones=secciones)
    return secciones


def pasos(seccion):
    """Los pasos de una seccion, en orden, o una lista vacia si no tiene."""
    return list(_leer().get(seccion, []))
