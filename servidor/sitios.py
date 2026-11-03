"""Lectura de un sitio: la API de Kubernetes y las metricas del exporter de Kafka.

Nada de esto ejecuta comandos dentro de los brokers. Los offsets salen del
exporter de Kafka que el ambiente ya tiene desplegado, leido por el proxy de la
API de Kubernetes: no agrega carga a los brokers (hallazgo N19).
"""
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from fuentes import describir_error

MARCA_SIMULACRO = "simulacro-caida-kafka"   # la que pone simular-caida-kafka.sh


def _q(s):
    return urllib.parse.quote(s, safe="")


class LectorSitio:
    def __init__(self, nombre, pareja, api_versions, token, http):
        self.nombre = nombre
        self.pareja = pareja
        self.cfg = pareja["sitios"][nombre]
        self.api = self.cfg["api"].rstrip("/")
        self.ns = self.cfg["namespace"]
        self.kafka = self.cfg["kafka"]
        self.av = api_versions
        self.token = token
        self.http = http
        self._exporter = None        # (pod, puerto) cacheado
        self._temenos = {}            # datos de la micro-app productora, cacheados

    # ── utilidades ──────────────────────────────────────────────────────────
    def _get(self, ruta, timeout=6):
        return self.http.json(self.api + ruta, self.token.valor(), timeout=timeout)

    def _pods(self, ns, selector):
        r = self._get("/api/v1/namespaces/%s/pods?labelSelector=%s" % (ns, _q(selector)))
        out = []
        for p in r.get("items", []):
            cs = [c for c in p.get("status", {}).get("containerStatuses", [])]
            principal = cs[0] if cs else {}
            espera = (principal.get("state", {}).get("waiting") or {}).get("reason")
            ultimo = ((principal.get("lastState") or {}).get("terminated") or {}).get("reason")
            out.append({
                "nombre": p["metadata"]["name"],
                "fase": p.get("status", {}).get("phase", "?"),
                "listo": bool(cs) and all(c.get("ready") for c in cs),
                "reinicios": sum(c.get("restartCount", 0) for c in cs),
                "motivo": espera,
                "ultimo_fin": ultimo,
            })
        return sorted(out, key=lambda x: x["nombre"])

    @staticmethod
    def _condicion(obj, tipo):
        for c in obj.get("status", {}).get("conditions", []) or []:
            if c.get("type") == tipo:
                return c.get("status") == "True"
        return None

    # ── lectura del sitio ───────────────────────────────────────────────────
    def leer(self):
        t0 = time.time()
        out = {"nombre": self.nombre, "alcanzable": False, "errores": {}}
        try:
            self.http.json(self.api + "/version", self.token.valor(), timeout=4)
            out["alcanzable"] = True
        except Exception as e:
            out["errores"]["api"] = describir_error(e)
            out["latencia_ms"] = int((time.time() - t0) * 1000)
            return out

        # Las partes son independientes y se piden a la vez: en serie, un sitio
        # tardaba 5,5 s en leerse, demasiado para una pagina en vivo.
        partes = {
            "brokers": lambda: self._pods(
                self.ns, "strimzi.io/cluster=%s,strimzi.io/broker-role=true" % self.kafka),
            "caida_simulada": self._caida_simulada,
            "proxy": self._proxy,
            "aplicaciones": self._aplicaciones,
            "replicaciones": self._replicaciones,
            "temenos": self._leer_temenos,
        }
        with ThreadPoolExecutor(max_workers=len(partes)) as ex:
            futuros = {clave: ex.submit(fn) for clave, fn in partes.items()}
            for clave, f in futuros.items():
                try:
                    out[clave] = f.result()
                except Exception as e:
                    out["errores"][clave] = describir_error(e)
        out["latencia_ms"] = int((time.time() - t0) * 1000)
        return out

    def _caida_simulada(self):
        r = self._get("/apis/kafka.strimzi.io/%s/namespaces/%s/kafkanodepools?labelSelector=%s"
                      % (self.av["kafka"].split("/")[-1], self.ns, _q("strimzi.io/cluster=" + self.kafka)))
        return any(MARCA_SIMULACRO in str(np.get("spec", {}).get("template", {})) for np in r.get("items", []))

    def _proxy(self):
        px = self.pareja.get("proxy", {}).get(self.nombre)
        if not px:
            return None
        grupo, version = self.av["kroxylicious"].split("/")
        vkc = self._get("/apis/%s/%s/namespaces/%s/virtualkafkaclusters/%s" % (grupo, version, px["namespace"], px["vkc"]))
        svc = (vkc.get("spec", {}).get("targetKafkaServiceRef") or {}).get("name")
        destino = next((s for s, n in px.get("destinos", {}).items() if n == svc), None)
        return {"vkc": px["vkc"], "servicio": svc, "destino": destino,
                "resuelto": self._condicion(vkc, "ResolvedRefs")}

    def _aplicaciones(self):
        out = []
        for app in self.pareja.get("aplicaciones", {}).get(self.nombre, []):
            d = self._get("/apis/apps/v1/namespaces/%s/deployments/%s" % (app["namespace"], app["nombre"]))
            out.append({"nombre": app["nombre"],
                        "replicas": d.get("spec", {}).get("replicas", 0),
                        "listas": d.get("status", {}).get("readyReplicas", 0) or 0})
        return out

    def _replicaciones(self):
        """Los MirrorMaker que VIVEN en este sitio, que es el destino de su copia."""
        grupo, version = self.av["mirrormaker2"].split("/")
        out = {}
        for clave, mm in self.pareja.get("mirrormakers", {}).items():
            if mm["sitio"] != self.nombre:
                continue
            origen, destino = clave.split("_")
            dato = {"clave": clave, "nombre": mm["name"], "origen": origen, "destino": destino,
                    "vive_en": self.nombre, "existe": False}
            try:
                cr = self._get("/apis/%s/%s/namespaces/%s/kafkamirrormaker2s/%s" % (grupo, version, mm["namespace"], mm["name"]))
            except Exception as e:
                if "404" in describir_error(e):
                    dato["estado"] = "AUSENTE"
                    out[clave] = dato
                    continue
                raise
            spec = cr.get("spec", {})
            mirrors = spec.get("mirrors") or [{}]
            pausa = (mirrors[0].get("sourceConnector") or {}).get("state", "running")
            replicas = int(spec.get("replicas", 0) or 0)
            conectores = [{"nombre": c.get("name", "").split(".")[-1].replace("Mirror", "").replace("Connector", ""),
                           "estado": (c.get("connector") or {}).get("state", "?")}
                          for c in cr.get("status", {}).get("connectors", []) or []]
            if replicas == 0:
                estado = "PASIVO"
            elif pausa in ("paused", "stopped"):
                estado = "PAUSADO"
            else:
                estado = "ACTIVO"
            dato.update({"existe": True, "replicas": replicas, "conector_origen": pausa,
                         "estado": estado, "conectores": conectores,
                         "listo": self._condicion(cr, "Ready")})
            try:
                dato["connect"] = self._pods(mm["namespace"], "strimzi.io/cluster=%s,strimzi.io/kind=KafkaMirrorMaker2" % mm["name"])
            except Exception as e:
                dato["connect_error"] = describir_error(e)
            out[clave] = dato
        return out

    # ── el simulador de Temenos ─────────────────────────────────────────────
    def _leer_temenos(self):
        tcfg = self.pareja.get("_temenos_cfg") or {}
        app = tcfg.get("app", "kafka-producer-app")
        try:
            d = self._get("/apis/apps/v1/namespaces/%s/deployments/%s" % (self.ns, app))
        except Exception:
            return None
        env = {e["name"]: e.get("value") for e in d["spec"]["template"]["spec"]["containers"][0].get("env", [])}
        if "host" not in self._temenos:
            try:
                ruta = self._get("/apis/route.openshift.io/v1/namespaces/%s/routes/%s" % (self.ns, tcfg.get("ruta", app)))
                tls = bool(ruta.get("spec", {}).get("tls"))
                self._temenos["host"] = ("https://" if tls else "http://") + ruta["spec"]["host"]
            except Exception:
                self._temenos["host"] = None
        return {"app": app, "replicas": d.get("spec", {}).get("replicas", 0),
                "listas": d.get("status", {}).get("readyReplicas", 0) or 0,
                "url": self._temenos.get("host"), "bootstrap": env.get("KAFKA_BOOTSTRAP_SERVERS"),
                "topico": env.get("DEFAULT_TOPIC")}

    # ── metricas del exporter ───────────────────────────────────────────────
    def leer_metricas(self):
        out = {"medido": False}
        try:
            if not self._exporter:
                pods = self._get("/api/v1/namespaces/%s/pods?labelSelector=%s"
                                 % (self.ns, _q("strimzi.io/name=%s-kafka-exporter" % self.kafka)))
                vivos = [p for p in pods.get("items", []) if p.get("status", {}).get("phase") == "Running"]
                if not vivos:
                    out["error"] = "exporter sin pod corriendo"
                    return out
                p = vivos[0]
                puertos = [pt.get("containerPort") for c in p["spec"]["containers"] for pt in c.get("ports", [])]
                self._exporter = (p["metadata"]["name"], 9404 if 9404 in puertos else puertos[0])
            pod, puerto = self._exporter
            texto = self.http.texto("%s/api/v1/namespaces/%s/pods/%s:%s/proxy/metrics"
                                    % (self.api, self.ns, pod, puerto), self.token.valor(), timeout=8)
        except Exception as e:
            self._exporter = None   # el pod pudo cambiar: se vuelve a buscar
            out["error"] = describir_error(e)
            return out
        return self._parsear(texto)

    _LINEA = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+([-+0-9.eE]+|NaN)')
    _ETIQ = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')

    def _parsear(self, texto):
        topicos = set(self.pareja.get("topicos_aplicacion", []))
        grupos = set(self.pareja.get("grupos_consumo", []))
        t = {tp: {"particiones": {}} for tp in topicos}
        g = {gr: {} for gr in grupos}
        brokers, sub = None, 0
        for linea in texto.splitlines():
            m = self._LINEA.match(linea)
            if not m:
                continue
            nombre, etiq, valor = m.group(1), dict(self._ETIQ.findall(m.group(2) or "")), m.group(3)
            if valor == "NaN":
                continue
            v = float(valor)
            if nombre == "kafka_brokers":
                brokers = int(v)
            elif nombre in ("kafka_topic_partition_current_offset", "kafka_topic_partition_oldest_offset") \
                    and etiq.get("topic") in topicos:
                clave = "fin" if nombre.endswith("current_offset") else "inicio"
                t[etiq["topic"]]["particiones"].setdefault(etiq["partition"], {})[clave] = int(v)
            elif nombre == "kafka_topic_partition_under_replicated_partition" and etiq.get("topic") in topicos:
                sub += int(v)
            elif nombre in ("kafka_consumergroup_current_offset", "kafka_consumergroup_lag") \
                    and etiq.get("consumergroup") in grupos and etiq.get("topic") in topicos:
                clave = "posicion" if nombre.endswith("current_offset") else "atraso"
                gg = g[etiq["consumergroup"]].setdefault(etiq["topic"], {"posicion": 0, "atraso": 0})
                gg[clave] += int(v)
        for tp, d in t.items():
            ps = d["particiones"].values()
            d["fin"] = sum(p.get("fin", 0) for p in ps)
            d["inicio"] = sum(p.get("inicio", 0) for p in ps)
            # Lo comparable entre sitios: fin de log menos principio (hallazgo N12).
            d["retenidos"] = d["fin"] - d["inicio"]
        return {"medido": brokers is not None and brokers > 0, "brokers": brokers,
                "topicos": t, "grupos": g, "sub_replicadas": sub}
