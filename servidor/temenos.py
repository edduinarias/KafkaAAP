"""El simulador de Temenos: la micro-app productora que ya existe en cada sitio.

Publica por el proxy de su sitio, igual que el core bancario. No es parte de la
automatizacion: representa al cliente que produce las transacciones.
"""
import threading
import time
from collections import deque

from fuentes import describir_error


def _enmascarar(cuenta):
    """Las cuentas son sinteticas, pero en una demo para un banco no se muestran
    completas: se dejan el pais, el banco y los ultimos cuatro digitos."""
    c = str(cuenta or "")
    return (c[:4] + " •••• " + c[-4:]) if len(c) > 8 else c


class Temenos:
    def __init__(self, cfg, http):
        self.cfg = cfg
        self.http = http
        self.ultimas = deque(maxlen=40)
        self.totales = {}
        self.continuo = None         # {"sitio", "por_segundo", "desde", "enviados", "errores"}: transacciones
        self._hilo = None
        self._parar = threading.Event()
        self._lock = threading.Lock()

    def enviar(self, sitio, datos_sitio, cantidad):
        """Un lote por el proxy del sitio. datos_sitio es lo que leyo el lector
        del sitio: la URL de la app, su bootstrap y su topico."""
        t = datos_sitio or {}
        if not t.get("url"):
            raise RuntimeError("la micro-app de %s no tiene ruta" % sitio.upper())
        cantidad = max(1, min(int(cantidad), int(self.cfg["lote_maximo"])))
        r = self.http.post_json(t["url"].rstrip("/") + "/api/batch",
                                {"bootstrap": t["bootstrap"], "topic": t.get("topico") or self.cfg["topico"],
                                 "count": cantidad}, timeout=120)
        ahora = time.time()
        with self._lock:
            for x in (r.get("results") or [])[-12:]:
                p = x.get("payload") or {}
                self.ultimas.appendleft({"t": ahora, "sitio": sitio, "ok": bool(x.get("success", True)),
                                         "id": p.get("transaccionId") or x.get("key"),
                                         "tipo": p.get("tipoOperacion"), "canal": p.get("canal"),
                                         "monto": p.get("monto"), "moneda": p.get("moneda"),
                                         "origen": _enmascarar(p.get("cuentaOrigen")),
                                         "destino": _enmascarar(p.get("cuentaDestino")),
                                         "sistema": p.get("sistemaOrigen"),
                                         "latencia_ms": x.get("latency_ms")})
            self.totales[sitio] = self.totales.get(sitio, 0) + int(r.get("sent") or 0)
        fallas = [x.get("error") for x in (r.get("results") or []) if not x.get("success", True)]
        return {"enviados": r.get("sent"), "total": r.get("total") or cantidad, "ok": bool(r.get("success")),
                "error": fallas[0] if fallas else None}

    def iniciar_continuo(self, sitio, por_segundo, proveedor_sitio):
        self.detener_continuo()
        por_segundo = max(1, min(int(por_segundo), int(self.cfg["continuo_por_segundo_maximo"])))
        self._parar.clear()
        self.continuo = {"sitio": sitio, "por_segundo": por_segundo, "desde": time.time(), "enviados": 0, "errores": 0}

        def bucle():
            while not self._parar.is_set():
                t0 = time.time()
                try:
                    r = self.enviar(sitio, proveedor_sitio(sitio), por_segundo * 2)
                    ok, total = int(r.get("enviados") or 0), int(r.get("total") or 0)
                    self.continuo["enviados"] += ok
                    # La micro-app responde bien aunque no entregue: el resultado
                    # viene por transaccion. Medido con un proxy que no puede
                    # entregar: sent=0 y 'socket disconnected' en cada una. Lo que
                    # no se entrega no se reintenta: se cuenta y se pierde.
                    if ok < total:
                        self.continuo["errores"] += total - ok
                        self.continuo["ultimo_error"] = r.get("error") or "%d de %d sin entregar" % (total - ok, total)
                    else:
                        self.continuo["ultimo_error"] = None
                except Exception as e:
                    self.continuo["errores"] += por_segundo * 2
                    self.continuo["ultimo_error"] = describir_error(e)
                # Un lote cada 2 s; el lote ya tarda lo suyo.
                self._parar.wait(max(0.2, 2 - (time.time() - t0)))

        self._hilo = threading.Thread(target=bucle, daemon=True, name="temenos-continuo")
        self._hilo.start()

    def detener_continuo(self):
        self._parar.set()
        if self._hilo:
            self._hilo.join(timeout=5)
        self._hilo = None
        self.continuo = None

    def estado(self):
        with self._lock:
            return {"continuo": dict(self.continuo) if self.continuo else None,
                    "ultimas": list(self.ultimas)[:20], "totales": dict(self.totales)}
