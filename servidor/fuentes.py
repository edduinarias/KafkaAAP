"""Configuracion y acceso HTTP a las fuentes: la API de cada sitio y la de AAP.

Los tokens se leen del archivo en cada consulta, asi un token renovado se toma
sin reiniciar. Su valor nunca se devuelve a quien llama ni se escribe en logs.
"""
import json
import os
import re
import ssl
import urllib.error
import urllib.request

import yaml

DEMO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _expandir(ruta):
    return os.path.expanduser(os.path.expandvars(ruta))


def cargar_config():
    with open(os.path.join(DEMO, "config.yml")) as f:
        cfg = yaml.safe_load(f)
    cfg["proyecto"] = os.path.normpath(os.path.join(DEMO, cfg.get("proyecto", "../..")))
    return cfg


def cargar_proyecto(cfg):
    """Inventario y contrato del proyecto: la pagina no declara nada propio
    sobre los sitios, lo lee de donde lo lee la automatizacion."""
    base = os.path.join(cfg["proyecto"], "playbooks", "group_vars", "all")
    datos = {}
    for nombre in ("parejas.yml", "umbrales.yml", "plataforma.yml"):
        with open(os.path.join(base, nombre)) as f:
            datos.update(yaml.safe_load(f) or {})
    with open(os.path.join(cfg["proyecto"], "transitions.yml")) as f:
        datos["contrato"] = yaml.safe_load(f)
    with open(os.path.join(DEMO, "catalogo.yml")) as f:
        datos["catalogo"] = yaml.safe_load(f)
    for nombre, clave in (("escenarios.yml", "escenarios_def"), ("guion.yml", "guion_def"),
                          ("casos_demo.yml", "casos_demo")):
        ruta = os.path.join(DEMO, nombre)
        with open(ruta) as f:
            datos[clave] = yaml.safe_load(f) or {}
    return datos


def leer_env_aap(ruta):
    """El archivo de entorno de AAP es de shell (CLAVE=valor). Se leen solo las
    claves que hacen falta."""
    valores = {}
    with open(_expandir(ruta)) as f:
        for linea in f:
            m = re.match(r"\s*(?:export\s+)?(AAP_[A-Z_]+)=(\S+)", linea)
            if m and not linea.lstrip().startswith("#"):
                valores[m.group(1)] = m.group(2).strip("'\"")
    return valores


class Token:
    """Un token en disco. Se relee en cada uso; nunca expone su valor."""

    def __init__(self, ruta):
        self.ruta = _expandir(ruta)

    def valor(self):
        with open(self.ruta) as f:
            return f.read().strip()

    def existe(self):
        return os.path.isfile(self.ruta) and os.path.getsize(self.ruta) > 0


class Http:
    def __init__(self, verificar_tls=False):
        self.ctx = ssl.create_default_context()
        if not verificar_tls:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def _pedir(self, url, token=None, metodo="GET", cuerpo=None, timeout=8, aceptar="application/json"):
        cabeceras = {"Accept": aceptar}
        if token:
            cabeceras["Authorization"] = "Bearer " + token
        datos = None
        if cuerpo is not None:
            datos = json.dumps(cuerpo).encode()
            cabeceras["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=datos, headers=cabeceras, method=metodo)
        ctx = self.ctx if url.startswith("https") else None
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return r.read()

    def json(self, url, token=None, **kw):
        return json.loads(self._pedir(url, token, **kw))

    def texto(self, url, token=None, **kw):
        return self._pedir(url, token, aceptar="text/plain", **kw).decode("utf-8", "replace")

    def post_json(self, url, cuerpo, token=None, timeout=60):
        return json.loads(self._pedir(url, token, metodo="POST", cuerpo=cuerpo, timeout=timeout))


def describir_error(e):
    """Un error de red en palabras, sin URL con datos sensibles."""
    if isinstance(e, urllib.error.HTTPError):
        return "HTTP %s" % e.code
    if isinstance(e, urllib.error.URLError):
        return "sin conexion (%s)" % (getattr(e, "reason", "") or "").__class__.__name__
    if isinstance(e, TimeoutError) or "timed out" in str(e):
        return "no respondio a tiempo"
    return e.__class__.__name__
