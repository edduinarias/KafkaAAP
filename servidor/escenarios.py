"""Montar escenarios desde la pagina: ejecuta las herramientas de
_contexto/herramientas/, las mismas que se usan por CLI. Nunca un playbook: las
operaciones se lanzan en AAP.

Una a la vez, con su salida en vivo, y nunca mientras haya una operacion de AAP
en curso: el escenario escribe en el laboratorio y pisaria a la automatizacion.
"""
import os
import re
import subprocess
import threading
import time
from collections import deque

ANSI = re.compile(r"\x1b\[[0-9;]*m")


class Escenarios:
    def __init__(self, definicion, demo_dir, log_dir):
        self.defs = definicion.get("escenarios", {})
        self.dir = os.path.normpath(os.path.join(demo_dir, definicion.get("herramientas", "../herramientas")))
        self.log = os.path.join(log_dir, "escenarios.log")
        self.lock = threading.Lock()
        self.actual = None            # {"clave", "nombre", "estado", "inicio", "fin", "rc", "lineas"}
        self.al_terminar = None       # callback(clave, ok)

    def catalogo(self):
        out = []
        for k, d in self.defs.items():
            if d.get("oculto"):
                continue
            out.append({"clave": k, "nombre": d["nombre"], "descripcion": d.get("descripcion", ""),
                        "confirmar": d.get("confirmar", ""), "peligroso": bool(d.get("peligroso")),
                        "vigente_si": d.get("vigente_si"), "habilita": d.get("habilita", []),
                        "parametros": [dict(p, clave=pk) for pk, p in (d.get("parametros") or {}).items()]})
        return out

    def estado(self):
        with self.lock:
            return dict(self.actual, lineas=list(self.actual["lineas"])) if self.actual else None

    def ejecutar(self, clave, parametros, bloqueo=None):
        """Lanza el escenario. bloqueo: motivo para no hacerlo (una operacion
        en curso). Devuelve el estado inicial o levanta ValueError."""
        if clave not in self.defs:
            raise ValueError("escenario desconocido")
        if bloqueo:
            raise ValueError(bloqueo)
        d = self.defs[clave]
        env = dict(os.environ)
        for pk, p in (d.get("parametros") or {}).items():
            v = (parametros or {}).get(pk, p.get("defecto"))
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError("%s no es un número" % p.get("nombre", pk))
            if not (p.get("min", v) <= v <= p.get("max", v)):
                raise ValueError("%s fuera de rango (%s a %s)" % (p.get("nombre", pk), p.get("min"), p.get("max")))
            env[p["env"]] = str(v)
        with self.lock:
            if self.actual and self.actual["estado"] == "corriendo":
                raise ValueError("ya se está montando «%s»" % self.actual["nombre"])
            self.actual = {"clave": clave, "nombre": d["nombre"], "estado": "corriendo", "inicio": time.time(),
                           "fin": None, "rc": None, "lineas": deque(maxlen=14)}
        threading.Thread(target=self._correr, args=(clave, d["comando"], env), daemon=True,
                         name="escenario-" + clave).start()
        return self.estado()

    def _correr(self, clave, comando, env):
        cmd = [os.path.join(self.dir, comando[0])] + list(comando[1:])
        rc = -1
        try:
            with open(self.log, "a") as log:
                log.write("\n== %s  %s\n" % (time.strftime("%F %T"), " ".join(comando)))
                p = subprocess.Popen(cmd, cwd=self.dir, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
                for linea in p.stdout:
                    limpia = ANSI.sub("", linea).rstrip()
                    log.write(limpia + "\n")
                    if limpia.strip():
                        with self.lock:
                            self.actual["lineas"].append(limpia.strip())
                rc = p.wait(timeout=1800)
        except Exception as e:
            with self.lock:
                self.actual["lineas"].append("error al ejecutar: %s" % e.__class__.__name__)
        with self.lock:
            self.actual.update({"estado": "ok" if rc == 0 else "fallo", "fin": time.time(), "rc": rc})
        if self.al_terminar:
            try:
                self.al_terminar(clave, rc == 0)
            except Exception:
                pass
