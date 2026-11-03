"""Servidor local de la demo: recolecta en segundo plano y sirve la pagina.

Cada fuente se lee en su propio hilo y a su ritmo; la vista se arma cada
intervalo con lo ultimo de cada una y se empuja al navegador por SSE. Si una
fuente se cae, las demas siguen y la pagina muestra que esa lectura esta vieja.

  python3 app.py [--host 127.0.0.1] [--puerto 8765]
"""
import argparse
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, wait
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aap import LectorAAP                                     # noqa: E402
from credenciales import credencial_sitio                     # noqa: E402
from escenarios import Escenarios                            # noqa: E402
from fuentes import DEMO, Http, Token, cargar_config, cargar_proyecto, describir_error  # noqa: E402
from guion import Guion, cumple                              # noqa: E402
from anticipo import anticipar, resultado_real               # noqa: E402
from modelo import _ts                                       # noqa: E402
from modelo import Modelo                                     # noqa: E402
import procedimiento                                          # noqa: E402
from sitios import LectorSitio                                # noqa: E402
from temenos import Temenos                                   # noqa: E402

WEB = os.path.join(DEMO, "web")


def _log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class Recolector:
    """Lo ultimo que se supo de cada fuente, y cuando."""

    def __init__(self, cfg, proyecto):
        self.cfg, self.pj = cfg, proyecto
        self.http = Http(cfg.get("verificar_tls", False))
        self.pareja = dict(proyecto["parejas"][cfg["pareja"]])
        self.pareja["_temenos_cfg"] = cfg["temenos"]
        self.tokens = {s: Token(cfg["tokens"][s]) for s in self.pareja["sitios"]}
        self.lectores = {s: LectorSitio(s, self.pareja, proyecto["api_versions"], self.tokens[s], self.http)
                         for s in self.pareja["sitios"]}
        self.aap = LectorAAP(cfg, proyecto, self.http)
        self.temenos = Temenos(cfg["temenos"], self.http)
        self.modelo = Modelo(cfg, proyecto)
        self.escenarios = Escenarios(proyecto["escenarios_def"], DEMO, os.path.join(DEMO, "logs"))
        self.escenarios.al_terminar = self._escenario_termino
        self.guion = Guion(proyecto["guion_def"])
        # El caso de uso que el presentador eligio en la consola. Lo ven las dos
        # pantallas. 'anticipados': lo que se anticipo al ver lanzarse cada
        # operacion, para compararlo con lo que AAP decidio.
        self.demo = {"caso": None, "direccion": None, "t": 0, "vistos": {}, "anticipados": {}}
        self._paso_seguido = None
        self._tm = {"falla_desde": None, "errores": 0, "desde": None}   # para avisar cuando Temenos deja de publicar
        self.guion.al_cumplir = self._paso_cumplido
        self.datos = {"sitios": {}, "metricas": {}, "operacion": None, "plantillas": [], "credenciales": []}
        self.salud = {}
        self._ex_metricas = ThreadPoolExecutor(max_workers=2 * len(self.lectores), thread_name_prefix="metricas")
        self._metricas_en_vuelo = {}
        self._guardado_t = 0
        self.ruta_memoria = os.path.join(DEMO, "run", "memoria.json")
        self._recordar()
        self.vista, self.version = None, 0
        self._ultima = {}
        self.cambio = threading.Condition()
        self.parar = threading.Event()

    # ── un hilo por fuente ──────────────────────────────────────────────────
    def _ciclo(self, nombre, fn, intervalo):
        def bucle():
            while not self.parar.is_set():
                t0 = time.time()
                try:
                    fn()
                    self.salud[nombre] = {"ok": True, "t": time.time(), "ms": int((time.time() - t0) * 1000)}
                except Exception as e:
                    previo = self.salud.get(nombre) or {}
                    self.salud[nombre] = {"ok": False, "t": previo.get("t"), "error": describir_error(e),
                                          "ms": int((time.time() - t0) * 1000)}
                    if not previo or previo.get("ok"):
                        _log("fuente %s: %s" % (nombre, describir_error(e)))
                        if os.environ.get("DEMO_DEBUG"):
                            traceback.print_exc()
                espera = intervalo() if callable(intervalo) else intervalo
                self.parar.wait(max(0.3, espera - (time.time() - t0)))
        threading.Thread(target=bucle, daemon=True, name=nombre).start()

    def _sitio(self, s):
        def leer():
            d = self.lectores[s].leer()
            self.datos["sitios"][s] = d
            if not d.get("alcanzable"):
                raise RuntimeError(d["errores"].get("api", "sin conexion"))
        return leer

    def _metricas(self):
        """Los sitios se piden a la vez: con carga viva, dos lecturas separadas
        por unos segundos muestran una diferencia que es solo el momento de
        medir. Pero ninguno espera al otro: con el Kafka de un sitio caido su
        exporter tarda en contestar, y el sitio que sirve no puede quedarse
        sin datos frescos justo durante la contingencia."""
        futuros = []
        for s, lec in self.lectores.items():
            f = self._metricas_en_vuelo.get(s)
            if f is None or f.done():
                t0 = time.time()
                f = self._ex_metricas.submit(lec.leer_metricas)
                f.add_done_callback(lambda f, s=s, t0=t0: self._guardar_metricas(s, f, t0))
                self._metricas_en_vuelo[s] = f
            futuros.append(f)
        wait(futuros, timeout=4)

    def _guardar_metricas(self, s, f, t0):
        try:
            m = f.result()
        except Exception as e:
            m = {"medido": False, "error": describir_error(e)}
        self.datos["metricas"][s] = m
        previo = self.salud.get("metricas_" + s) or {}
        ms = int((time.time() - t0) * 1000)
        self.salud["metricas_" + s] = ({"ok": True, "t": time.time(), "ms": ms} if not m.get("error")
                                       else {"ok": False, "t": previo.get("t"), "error": m["error"], "ms": ms})

    # ── memoria entre reinicios: la linea de tiempo y la historia ───────────
    def _recordar(self):
        try:
            with open(self.ruta_memoria) as f:
                d = json.load(f)
            if self.modelo.importar(d, self.cfg["historia_minutos"] * 60):
                _log("linea de tiempo recuperada (%d eventos)" % len(self.modelo.eventos))
            # El guion se recupera aunque la historia sea vieja: una demo se
            # puede retomar despues de una pausa larga.
            self.guion.importar(d.get("guion"))
            self.demo.update(d.get("demo") or {})
        except FileNotFoundError:
            pass
        except Exception as e:
            _log("no se pudo recuperar la linea de tiempo: %s" % e.__class__.__name__)

    def _guardar_memoria(self):
        if time.time() - self._guardado_t < 10:
            return
        self._guardado_t = time.time()
        tmp = self.ruta_memoria + ".tmp"
        with open(tmp, "w") as f:
            json.dump(dict(self.modelo.exportar(), guion=self.guion.exportar(), demo=self.demo), f, default=str)
        os.replace(tmp, self.ruta_memoria)

    def _aap(self):
        self.datos["operacion"] = self.aap.leer()
        self.datos["plantillas"] = self.aap.plantillas()

    def _intervalo_aap(self):
        op = self.datos.get("operacion") or {}
        en_curso = op.get("estado") not in (None, "successful", "failed", "error", "canceled")
        return self.cfg["intervalos"]["aap_en_curso" if en_curso else "aap_reposo"]

    def _credenciales(self):
        out = [credencial_sitio(s, self.pareja["sitios"][s]["api"], self.tokens[s], self.http) for s in self.tokens]
        out.append(self.aap.credencial())
        self.datos["credenciales"] = out

    def _armar(self):
        L = dict(self.datos)
        L["temenos"] = self.temenos.estado()
        self._vigilar_temenos(L["temenos"].get("continuo"))
        L["aap_url"] = self.aap.url
        L["salud"] = self._salud()
        L["aap_leido"] = "aap" in self.salud and self.salud["aap"].get("t") is not None
        v = self.modelo.armar(L)
        enlaces = {p["operacion"]: p["url"] for p in self.datos.get("plantillas") or [] if p.get("operacion")}
        v["guion"] = self.guion.evaluar(v, enlaces)
        self._seguir_guion()
        v["escenarios"] = {"catalogo": [dict(x, vigente=bool(x["vigente_si"]) and cumple(x["vigente_si"], v))
                                        for x in self.escenarios.catalogo()],
                           "actual": self.escenarios.estado(), "bloqueo": self._bloqueo(v)}
        v["marca"] = self.cfg.get("marca") or {}
        v["temenos_defecto"] = self.cfg["temenos"].get("por_defecto") or {}
        v["puertos"] = getattr(self, "puertos", {})
        try:
            v["demo"] = self._demo(v)
        except Exception as e:
            v["demo"] = {"casos": [], "seleccion": None, "error": e.__class__.__name__}
            if os.environ.get("DEMO_DEBUG"):
                traceback.print_exc()
        # Al final: el guion y el caso ya evaluaron con la operacion real; esto
        # solo decide que se muestra.
        self._ocultar_ajena(v)
        self._ultima = v
        try:
            self._guardar_memoria()
        except OSError:
            pass
        with self.cambio:
            self.vista = json.dumps(v, ensure_ascii=False, default=str)
            self.version += 1
            self.cambio.notify_all()

    def _salud(self):
        ahora = time.time()
        out = {}
        for k, v in self.salud.items():
            out[k] = dict(v, antiguedad=round(ahora - v["t"], 1) if v.get("t") else None)
        return out

    def arrancar(self):
        iv = self.cfg["intervalos"]
        for s in self.lectores:
            self._ciclo("sitio_" + s, self._sitio(s), iv["sitios"])
        self._ciclo("metricas", self._metricas, iv["metricas"])
        self._ciclo("aap", self._aap, self._intervalo_aap)
        self._ciclo("credenciales", self._credenciales, iv["credenciales"])
        self._ciclo("vista", self._armar, iv["vista"])

    # ── la demo por caso de uso ─────────────────────────────────────────────
    def _seguir_guion(self):
        """Mientras corre el guion, el caso elegido sigue a su paso: se ve el
        procedimiento de ese paso, y la vista en vivo muestra su operacion.
        Solo al cambiar de paso: si el presentador elige otro caso a mano, se
        respeta hasta el paso siguiente."""
        g = self.guion
        if not (g.activo and g.pasos):
            self._paso_seguido = None
            return
        if g.indice == self._paso_seguido:
            return
        self._paso_seguido = g.indice
        p = g.pasos[g.indice]
        casos = (self.pj.get("casos_demo") or {}).get("casos") or {}
        caso = next((k for k, c in casos.items()
                     if not c.get("oculto") and p.get("caso") in (c.get("etapas") or [c.get("flujo")])), None)
        if not caso or caso == self.demo.get("caso"):
            return
        direccion = (p.get("aap") or {}).get("direccion") or casos[caso].get("direccion")
        self.demo.update({"caso": caso, "direccion": direccion, "t": time.time(), "vistos": {}})
        self.modelo.evento("Caso de uso en demostración: %s" % casos[caso]["nombre"], "info", "guion")

    def _ocultar_ajena(self, v):
        """Con un caso elegido, un flujo terminado que no es de ese caso no se
        muestra, ni como el ultimo: la vista en vivo hablaria de dos
        operaciones distintas a la vez. Uno en curso si, porque esta cambiando
        el ambiente."""
        op = v.get("operacion") or {}
        c = ((self.pj.get("casos_demo") or {}).get("casos") or {}).get((self.demo or {}).get("caso") or "")
        if not c or op.get("en_curso") or not op.get("operacion"):
            return
        if op["operacion"] not in (c.get("etapas") or [c.get("flujo")]):
            v["operacion"] = None

    @staticmethod
    def _rellenar(x, o, d):
        if isinstance(x, str):
            return x.replace("{O}", o.upper()).replace("{D}", d.upper()).replace("{o}", o).replace("{d}", d)
        if isinstance(x, list):
            return [Recolector._rellenar(i, o, d) for i in x]
        if isinstance(x, dict):
            return {k: Recolector._rellenar(i, o, d) for k, i in x.items()}
        return x

    def _demo(self, v):
        cfg = self.pj.get("casos_demo") or {}
        casos = cfg.get("casos") or {}
        out = {"casos": [{"clave": k, "nombre": c["nombre"], "seccion": c.get("seccion", ""), "que_es": c.get("que_es", ""),
                          "proximo": bool(c.get("proximo"))}
                         for k, c in casos.items() if not c.get("oculto")], "seleccion": None}
        sel = self.demo
        c = casos.get(sel.get("caso") or "")
        if not c or c.get("proximo") or c.get("oculto"):
            return out
        sitios = v["pareja"]["sitios"]
        direccion = sel.get("direccion") or c.get("direccion")
        ops = c.get("etapas") or [c["flujo"]]
        antic = [anticipar(op, direccion, v, self.pj["contrato"], self.cfg["pareja"], self.pareja, self.modelo._accion)
                 for op in ops]
        op = v.get("operacion") or {}
        # En el failback, la etapa 2 sigue a unos Preparativos que terminaron bien.
        actual = 1 if (len(ops) > 1 and op.get("visible") and op.get("transicion") == "FAILBACK_PREPARATIVOS"
                       and op.get("estado") == "successful") else 0
        # Con el guion en marcha, la etapa es la de su paso actual.
        g = self.guion
        if g.activo and g.pasos and g.pasos[g.indice].get("caso") in ops:
            actual = ops.index(g.pasos[g.indice]["caso"])
        a = antic[actual]
        # Una transicion que en este caso no es su escenario -la conmutacion
        # planificada dentro del caso Failover- se muestra como tal, aunque su
        # propia validacion la fuera a frenar: lo que importa es que no es el
        # punto de partida del caso.
        neutra = ((c.get("salidas") or {}).get(a.get("transicion") or "") or {}).get("nivel") == "neutro"
        if neutra and a["salida"] in ("detiene", "no_aplica"):
            a = dict(a, salida=a["transicion"])
        o, d = a["origen"], a["destino"]
        gen = cfg.get("generales") or {}
        sal = self._rellenar((c.get("salidas") or {}).get(a["salida"]) or gen.get(a["salida"]) or {}, o, d)
        # Lo que se ve, marcado cuando se cumple y sin desmarcarse mientras no
        # cambie la eleccion o la salida.
        clave = "%s|%s|%s" % (sel["caso"], direccion, a["salida"])
        vistos = sel["vistos"].setdefault(clave, [])
        ves = []
        for j, x in enumerate(sal.get("ves") or []):
            if j not in vistos and cumple(x.get("si"), v):
                vistos.append(j)
            ves.append({"texto": x["texto"], "visto": j in vistos})
        # Lo anticipado se congela al ver lanzarse la operacion: despues el
        # estado cambia y el anticipo con el.
        real = None
        if op.get("visible") and op.get("operacion") in ops and (_ts(op.get("inicio") or "") or 0) > sel.get("t", 0):
            k = str(op["id"])
            if k not in sel["anticipados"]:
                sel["anticipados"][k] = antic[ops.index(op["operacion"])]["salida"]
            r = resultado_real(op)
            real = {"id": op["id"], "en_curso": op.get("en_curso"), "estado": op.get("estado"), "salida": r,
                    "anticipado": sel["anticipados"][k], "coincide": None if r is None else r == sel["anticipados"][k],
                    "titulo_real": self._rellenar(((c.get("salidas") or {}).get(r) or gen.get(r) or {}).get("titulo"), o, d) if r else None}
        otras = []
        for k, s in (c.get("salidas") or {}).items():
            if k == a["salida"]:
                continue
            montar = (s.get("montar") or {}).get(direccion)
            otras.append({"salida": k, "titulo": self._rellenar(s.get("titulo", k), o, d),
                          "frase": self._rellenar(s.get("frase_publico", ""), o, d),
                          "montar": montar,
                          "pista": None if montar else s.get("pista") or ("elige la dirección hacia el sitio que ya atiende" if k == "nada"
                                                                          else "se llega desde otra situación del ambiente")})
        etapas = []
        if len(ops) > 1:
            for i, x in enumerate(antic):
                s = ((c.get("salidas") or {}).get(x["salida"]) or gen.get(x["salida"]) or {})
                etapas.append({"operacion": ops[i], "actual": i == actual, "salida": x["salida"],
                               "titulo": s.get("titulo", x["salida"]), "motivo": x.get("motivo")})
        out["seleccion"] = {
            "procedimiento": self._procedimiento(c, ops[actual], o, d),
            "caso": sel["caso"], "nombre": c["nombre"], "seccion": c.get("seccion", ""), "que_es": c.get("que_es", ""),
            "direccion": direccion, "origen": o, "destino": d,
            "direcciones": ["%s_a_%s" % (x, y) for x in sitios for y in sitios if x != y],
            "anticipo": a, "salida": dict(sal, ves=ves, montar=(sal.get("montar") or {}).get(direccion)),
            "titulo_salida": sal.get("titulo", a["salida"]), "etapas": etapas, "otras": otras, "real": real,
            "url_flujo": next((p["url"] for p in (self.datos.get("plantillas") or []) if p.get("operacion") == ops[actual]), None),
        }
        return out

    # ── guion y escenarios ──────────────────────────────────────────────────
    def _procedimiento(self, c, operacion, o, d):
        """Los pasos del documento para el flujo en curso del caso, con quien
        hace cada uno y como."""
        p = (c.get("procedimientos") or {}).get(operacion)
        if not p:
            return None
        try:
            doc = procedimiento.pasos(p["seccion"])
        except OSError as e:
            return {"seccion": p["seccion"], "error": "no se pudo leer el procedimiento: %s" % e.__class__.__name__}
        if not doc:
            return {"seccion": p["seccion"], "error": "el documento no tiene pasos en el §%s" % p["seccion"]}
        anot = p.get("pasos") or {}
        return {
            "seccion": p["seccion"], "nombre": p.get("nombre", ""), "nota": self._rellenar(p.get("nota", ""), o, d),
            "pasos": [dict({"n": x["n"], "titulo": x["titulo"], "porque": x["explicacion"]},
                           **self._rellenar(anot.get(x["n"]) or {}, o, d)) for x in doc],
            "extras": self._rellenar(p.get("extras") or [], o, d),
        }

    @staticmethod
    def _bloqueo(v):
        op = v.get("operacion") or {}
        if op.get("en_curso"):
            return "Hay una operación de AAP en curso (flujo %s): un escenario la pisaría." % op.get("id")
        return None

    def _escenario_termino(self, clave, ok):
        nombre = self.escenarios.defs[clave]["nombre"]
        self.modelo.evento(("Escenario montado: %s" if ok else "El escenario «%s» no terminó bien") % nombre,
                           "ok" if ok else "critico", "escenario")

    def _paso_cumplido(self, i, titulo, manual):
        self.modelo.evento("Guion · paso %d %s: %s" % (i + 1, "marcado" if manual else "cumplido", titulo),
                           "ok", "guion")

    # ── Temenos ─────────────────────────────────────────────────────────────
    def _vigilar_temenos(self, c):
        """La linea de tiempo registra cuando Temenos deja de poder publicar y,
        cuando vuelve o se detiene, cuantas transacciones quedaron sin entregar.
        Cada encendido es un episodio propio: sus contadores empiezan en cero."""
        tm = self._tm
        mismo = bool(c) and c.get("desde") == tm.get("desde")
        if tm["falla_desde"] is not None and (not mismo or not c.get("ultimo_error")):
            vuelve = mismo
            perdidas = (c.get("errores", 0) if vuelve else tm["errores"]) - tm["falla_desde"]
            self.modelo.evento("Temenos %s · %d transacciones quedaron sin entregar"
                               % ("vuelve a publicar" if vuelve else "detenido", perdidas),
                               "ok" if vuelve else "cambio", "temenos")
            tm["falla_desde"] = None
        if c and c.get("ultimo_error") and tm["falla_desde"] is None:
            tm["falla_desde"] = tm["errores"] if mismo else 0
            self.modelo.evento("Temenos no logra publicar por el proxy de %s: %s" % (c["sitio"].upper(), c["ultimo_error"]),
                               "critico", "temenos")
        tm["desde"] = c.get("desde") if c else None
        tm["errores"] = c.get("errores", 0) if c else 0

    def sitio_temenos(self, pedido):
        """Por defecto, la micro-app del sitio activo: es el proxy que usaria el
        core bancario. Se puede forzar uno."""
        if pedido in self.lectores:
            return pedido
        v = json.loads(self.vista) if self.vista else {}
        return v.get("activo") or list(self.lectores)[0]

    def datos_temenos(self, s):
        return (self.datos["sitios"].get(s) or {}).get("temenos")


def manejador(rec, consola=False):
    """consola=True: la consola de la demo, la unica que puede mover el
    laboratorio. consola=False: la vista en vivo, que solo mira; es la que se
    proyecta, y desde ella nadie puede tocar nada."""
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "kafka-dr-demo"

        def log_message(self, fmt, *a):
            if os.environ.get("DEMO_DEBUG"):
                _log("http", fmt % a)

        def _responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
            datos = cuerpo if isinstance(cuerpo, bytes) else (
                cuerpo if isinstance(cuerpo, str) else json.dumps(cuerpo, ensure_ascii=False, default=str)).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(datos)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(datos)

        def _cuerpo(self):
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def do_GET(self):
            ruta = self.path.split("?")[0]
            if ruta == "/api/estado":
                return self._responder(200, rec.vista or "{}")
            if ruta == "/api/salud":
                return self._responder(200, {"version": rec.version, "fuentes": rec._salud()})
            if ruta == "/api/eventos":
                return self._sse()
            return self._estatico(ruta)

        def _sse(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            visto = -1
            try:
                while not rec.parar.is_set():
                    with rec.cambio:
                        if rec.version == visto:
                            rec.cambio.wait(timeout=15)
                        version, vista = rec.version, rec.vista
                    if version != visto and vista:
                        self.wfile.write(("event: estado\ndata: %s\n\n" % vista).encode())
                        visto = version
                    else:
                        self.wfile.write(b": latido\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        def _estatico(self, ruta):
            if ruta in ("/", ""):
                ruta = "/consola.html" if consola else "/index.html"
            if not consola and ruta == "/consola.html":
                return self._responder(404, {"error": "la consola está en su propio puerto"})
            real = os.path.realpath(os.path.join(WEB, ruta.lstrip("/")))
            if not real.startswith(os.path.realpath(WEB) + os.sep) or not os.path.isfile(real):
                return self._responder(404, {"error": "no existe"})
            tipo = mimetypes.guess_type(real)[0] or "application/octet-stream"
            if tipo.startswith("text/") or tipo in ("application/javascript", "image/svg+xml"):
                tipo += "; charset=utf-8"
            with open(real, "rb") as f:
                self._responder(200, f.read(), tipo)

        def do_POST(self):
            ruta = self.path.split("?")[0]
            # Solo la propia pagina: un formulario o un fetch de otro sitio no
            # puede mandar esta cabecera sin una consulta previa que aca no se
            # responde. Estas acciones escriben en el laboratorio.
            if not consola:
                return self._responder(403, {"error": "la vista en vivo solo mira; las acciones se hacen desde la consola"})
            if self.headers.get("X-Demo") != "1":
                return self._responder(403, {"error": "solo desde la consola de la demo"})
            try:
                c = self._cuerpo()
                if ruta.startswith("/api/escenarios/"):
                    if not c.get("confirmado"):
                        return self._responder(400, {"error": "falta confirmar"})
                    r = rec.escenarios.ejecutar(ruta.rsplit("/", 1)[1], c.get("parametros"),
                                                bloqueo=rec._bloqueo(rec._ultima))
                    rec.modelo.evento("Montando el escenario: %s" % r["nombre"], "cambio", "escenario")
                    return self._responder(200, r)
                if ruta == "/api/demo/caso":
                    caso = c.get("caso")
                    if caso and caso not in ((rec.pj.get("casos_demo") or {}).get("casos") or {}):
                        return self._responder(400, {"error": "caso desconocido"})
                    rec.demo.update({"caso": caso, "direccion": c.get("direccion"), "t": time.time(), "vistos": {}})
                    if caso:
                        nombre = rec.pj["casos_demo"]["casos"][caso]["nombre"]
                        rec.modelo.evento("Caso de uso en demostración: %s" % nombre, "info", "guion")
                    return self._responder(200, {"ok": True})
                if ruta == "/api/guion":
                    rec.guion.accion(c.get("accion"), c.get("indice"))
                    if c.get("accion") == "iniciar":
                        rec.modelo.evento("Guion de la demo iniciado", "info", "guion")
                    return self._responder(200, {"ok": True})
                if ruta == "/api/temenos/alternar":
                    if rec.temenos.estado()["continuo"]:
                        rec.temenos.detener_continuo()
                        rec.modelo.evento("Temenos detenido", "cambio", "temenos")
                        return self._responder(200, {"continuo": None})
                    d = rec.cfg["temenos"].get("por_defecto") or {}
                    s = rec.sitio_temenos(d.get("sitio"))
                    rec.temenos.iniciar_continuo(s, d.get("por_segundo", 5), rec.datos_temenos)
                    rec.modelo.evento("Temenos escribiendo: %s tx/s por el proxy de %s" % (d.get("por_segundo", 5), s.upper()),
                                      "cambio", "temenos")
                    return self._responder(200, {"continuo": rec.temenos.estado()["continuo"]})
                if ruta == "/api/temenos/lote":
                    s = rec.sitio_temenos(c.get("sitio"))
                    r = rec.temenos.enviar(s, rec.datos_temenos(s), c.get("cantidad", 10))
                    return self._responder(200, dict(r, sitio=s))
                if ruta == "/api/temenos/continuo":
                    if c.get("detener"):
                        if rec.temenos.estado()["continuo"]:
                            rec.temenos.detener_continuo()
                            rec.modelo.evento("Temenos detenido", "cambio", "temenos")
                        return self._responder(200, {"continuo": None})
                    s = rec.sitio_temenos(c.get("sitio"))
                    rec.temenos.iniciar_continuo(s, c.get("por_segundo", 5), rec.datos_temenos)
                    t = rec.temenos.estado()["continuo"]
                    rec.modelo.evento("Temenos escribiendo: %s tx/s por el proxy de %s" % (t["por_segundo"], s.upper()),
                                      "cambio", "temenos")
                    return self._responder(200, {"continuo": t})
            except ValueError as e:
                return self._responder(409, {"error": str(e)})
            except Exception as e:
                return self._responder(502, {"error": describir_error(e) if not isinstance(e, RuntimeError) else str(e)})
            return self._responder(404, {"error": "no existe"})

    return H


def main():
    cfg = cargar_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=cfg["servidor"]["host"])
    ap.add_argument("--puerto", type=int, default=cfg["servidor"]["puerto"])
    ap.add_argument("--puerto-consola", type=int,
                    default=cfg["servidor"].get("puerto_consola", cfg["servidor"]["puerto"] + 1))
    args = ap.parse_args()
    proyecto = cargar_proyecto(cfg)
    rec = Recolector(cfg, proyecto)
    rec.puertos = {"vivo": args.puerto, "consola": args.puerto_consola}
    rec.arrancar()
    # El mismo recolector para las dos: ven exactamente el mismo estado.
    vivo = ThreadingHTTPServer((args.host, args.puerto), manejador(rec, consola=False))
    cons = ThreadingHTTPServer((args.host, args.puerto_consola), manejador(rec, consola=True))
    for s in (vivo, cons):
        s.daemon_threads = True
    threading.Thread(target=cons.serve_forever, daemon=True, name="consola").start()
    _log("demo Kafka DR (pareja %s): en vivo http://%s:%s · consola http://%s:%s"
         % (cfg["pareja"], args.host, args.puerto, args.host, args.puerto_consola))
    try:
        vivo.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        rec.parar.set()
        rec.temenos.detener_continuo()


if __name__ == "__main__":
    main()
