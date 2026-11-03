"""La operacion en curso, leida de AAP: el flujo, sus nodos, el plan aprobado y
cada paso con su resultado real.

No lanza ni aprueba nada. La automatizacion vive en AAP; esto la mira.
"""
import json
import time
import urllib.parse

import yaml

from fuentes import Token, describir_error, leer_env_aap

# Los roles que ejecutan las acciones del plan. Cada accion empieza cuando el
# job valida los argumentos de su rol: es el unico evento que marca el inicio
# aunque dos acciones seguidas usen el mismo rol (por ejemplo dos escalados).
ROLES_ACCION = {"mm2_state", "proxy_target", "app_scale", "resync_control", "mm2_lifecycle", "topic_align"}

# Las tareas de primer nivel de aplicar.yml marcan en que fase va el job.
FASES_APLICAR = [
    ("Descubrir estado actual", "revalidando"),
    ("Revalidar la transicion", "revalidando"),
    ("Ejecutar cada accion del plan, en el orden declarado", "ejecutando"),
    ("Descubrir estado final", "verificando"),
    ("Verificar estado final", "verificando"),
    ("Avisar el resultado verificado", "notificando"),
    ("Establecer donde quedo el ambiente", "fallo"),
    ("Avisar que la ejecucion se detuvo", "fallo"),
]


def _msg(res):
    m = (res or {}).get("msg")
    if isinstance(m, list):
        m = " ".join(str(x) for x in m if str(x).strip())
    return str(m).strip() if m else ""


class LectorAAP:
    def __init__(self, cfg, proyecto, http):
        env = leer_env_aap(cfg["aap"]["env"])
        self.api = env["AAP_API"].rstrip("/")
        self.url = (env.get("AAP_URL") or proyecto.get("aap_url") or "").rstrip("/")
        self.gateway = self.api.split("/api/")[0]
        self.token = Token(env["AAP_TOKEN_FILE"])
        self.prefijo = cfg["aap"]["prefijo_flujos"]
        self.ruta_aprobaciones = proyecto.get("aap_ruta_aprobaciones", "/execution/administration/workflow-approvals")
        self.http = http
        self.eventos = {}          # job -> {"ultimo": counter, "lista": [...]}
        self.trabajos = {}         # job -> detalle cacheado cuando ya termino
        self._plantillas = None
        self._plantillas_t = 0

    def _get(self, ruta, timeout=8):
        return self.http.json(self.api + ruta, self.token.valor(), timeout=timeout)

    # ── plantillas de flujo: que operaciones estan cableadas ────────────────
    def plantillas(self):
        if self._plantillas is None or time.time() - self._plantillas_t > 120:
            r = self._get("/workflow_job_templates/?page_size=100&name__startswith=" + urllib.parse.quote(self.prefijo))
            out = []
            for w in r.get("results", []):
                try:
                    ev = yaml.safe_load(w.get("extra_vars") or "") or {}
                except Exception:
                    ev = {}
                out.append({"id": w["id"], "nombre": w["name"], "operacion": ev.get("operacion"),
                            "descripcion": w.get("description", ""),
                            "url": "%s/execution/templates/workflow-job-template/%s/details" % (self.url, w["id"])})
            self._plantillas, self._plantillas_t = out, time.time()
        return self._plantillas

    # ── eventos de un job, incrementales ────────────────────────────────────
    def _eventos(self, job, terminado):
        reg = self.eventos.setdefault(job, {"ultimo": 0, "lista": [], "completo": False})
        if reg["completo"]:
            return reg["lista"]
        ruta = "/jobs/%s/job_events/?order_by=counter&page_size=200&counter__gt=%s" % (job, reg["ultimo"])
        while ruta:
            r = self._get(ruta)
            for e in r.get("results", []):
                ed = e.get("event_data") or {}
                res = ed.get("res") or {}
                reg["lista"].append({
                    "c": e["counter"], "ev": e["event"], "tarea": e.get("task") or ed.get("task") or "",
                    "rol": e.get("role") or ed.get("role") or "", "t": e.get("created"),
                    "fallo": bool(e.get("failed")) and not ed.get("ignore_errors"),
                    "msg": _msg(res)[:600],
                })
                reg["ultimo"] = max(reg["ultimo"], e["counter"])
            sig = r.get("next")
            ruta = sig.split("/v2", 1)[1] if sig else None
        if terminado:
            reg["completo"] = True
        return reg["lista"]

    def _trabajo(self, job_id):
        if job_id in self.trabajos:
            return dict(self.trabajos[job_id])
        j = self._get("/jobs/%s/" % job_id)
        d = {"id": job_id, "estado": j.get("status"), "inicio": j.get("started"), "fin": j.get("finished"),
             "duracion": j.get("elapsed"), "artefactos": j.get("artifacts") or {},
             "url": "%s/execution/jobs/playbook/%s/output" % (self.url, job_id)}
        if d["estado"] in ("successful", "failed", "error", "canceled"):
            self.trabajos[job_id] = dict(d)
        return d

    # ── la operacion ────────────────────────────────────────────────────────
    def leer(self):
        r = self._get("/workflow_jobs/?order_by=-id&page_size=1&name__startswith=" + urllib.parse.quote(self.prefijo))
        if not r.get("results"):
            return None
        w = r["results"][0]
        try:
            ev = json.loads(w.get("extra_vars") or "{}")
        except Exception:
            ev = {}
        op = {"id": w["id"], "flujo": w["name"], "estado": w["status"], "inicio": w.get("started"),
              "fin": w.get("finished"), "duracion": w.get("elapsed"),
              "operacion": ev.get("operacion"), "direccion": ev.get("direccion"), "pareja": ev.get("pareja"),
              "url": "%s/execution/jobs/workflow/%s/output" % (self.url, w["id"]),
              "url_aprobaciones": self.url + self.ruta_aprobaciones,
              "preflight": None, "aprobacion": None, "aplicar": None, "plan": None}
        nodos = self._get("/workflow_jobs/%s/workflow_nodes/?page_size=20" % w["id"]).get("results", [])
        for n in nodos:
            j = (n.get("summary_fields") or {}).get("job") or {}
            if not j:
                continue
            if j.get("type") == "workflow_approval":
                op["aprobacion"] = self._aprobacion(j["id"])
            elif j.get("name", "").endswith("Preflight"):
                op["preflight"] = self._preflight(j["id"])
                op["plan"] = op["preflight"]["artefactos"].get("wf_kafka_plan")
            elif j.get("name", "").endswith("Aplicar"):
                op["aplicar"] = self._aplicar(j["id"], op["plan"])
        for k in ("preflight", "aplicar"):
            if op[k]:
                op[k].pop("artefactos", None)
        return op

    def _aprobacion(self, aid):
        a = self._get("/workflow_approvals/%s/" % aid)
        quien = ((a.get("summary_fields") or {}).get("approved_or_denied_by") or {}).get("username")
        estado = a.get("status")
        return {"id": aid, "nombre": a.get("name"), "estado": estado,
                "resultado": "aprobada" if estado == "successful" else "denegada" if estado == "failed"
                             else "vencida" if a.get("timed_out") else "pendiente" if estado in ("pending", "running") else estado,
                "por": quien, "creada": a.get("created"), "resuelta": a.get("finished")}

    def _preflight(self, job_id):
        d = self._trabajo(job_id)
        evs = self._eventos(job_id, d["estado"] in ("successful", "failed", "error", "canceled"))
        prechecks, propuesta = [], None
        # Una tarea con bucle publica un evento por elemento y otro de resumen
        # ("One or more items failed"): con los elementos alcanza.
        con_items = {e["tarea"] for e in evs if e["ev"] in ("runner_item_on_ok", "runner_item_on_failed")}
        for e in evs:
            if e["ev"] in ("runner_on_ok", "runner_on_failed") and e["tarea"] in con_items:
                continue
            if e["tarea"].startswith("Precheck ") and e["ev"] in ("runner_on_ok", "runner_on_failed", "runner_item_on_ok", "runner_item_on_failed"):
                prechecks.append({"nombre": e["tarea"][len("Precheck "):], "ok": not e["fallo"], "msg": e["msg"]})
            if e["tarea"] == "Mostrar la propuesta" and e["ev"] == "runner_on_ok":
                propuesta = e["msg"]
        d.update({"prechecks": prechecks, "propuesta": propuesta, "fallo": self._primer_fallo(evs)})
        return d

    @staticmethod
    def _primer_fallo(evs):
        for e in evs:
            if e["fallo"] and e["ev"] in ("runner_on_failed", "runner_item_on_failed"):
                return {"tarea": e["tarea"], "msg": e["msg"]}
        return None

    def _aplicar(self, job_id, plan):
        d = self._trabajo(job_id)
        evs = self._eventos(job_id, d["estado"] in ("successful", "failed", "error", "canceled"))
        acciones = [{"indice": i, "rol": a.get("rol"), "estado": "pendiente", "mensajes": [], "reintentos": 0}
                    for i, a in enumerate((plan or {}).get("acciones", []))]
        fase, actual, verificacion = "esperando", -1, []
        nombres_fase = dict(FASES_APLICAR)
        for e in evs:
            if e["ev"] == "playbook_on_task_start" and not e["rol"] and e["tarea"] in nombres_fase:
                fase = nombres_fase[e["tarea"]]
                if fase != "ejecutando" and 0 <= actual < len(acciones) and acciones[actual]["estado"] == "en_curso":
                    acciones[actual]["estado"] = "hecho"
                continue
            if fase == "ejecutando" and e["rol"] in ROLES_ACCION and e["ev"] == "playbook_on_task_start" \
                    and e["tarea"].startswith("Validating arguments"):
                if 0 <= actual < len(acciones) and acciones[actual]["estado"] == "en_curso":
                    acciones[actual]["estado"] = "hecho"
                actual += 1
                if actual < len(acciones):
                    acciones[actual]["estado"] = "en_curso"
                continue
            if fase == "ejecutando" and 0 <= actual < len(acciones):
                a = acciones[actual]
                if e["ev"] == "runner_retry":
                    a["reintentos"] += 1
                elif e["ev"] in ("runner_on_ok", "runner_item_on_ok") and e["msg"] and e["msg"] != "All assertions passed":
                    a["mensajes"].append(e["msg"])
                    a["mensajes"] = a["mensajes"][-3:]
                elif e["fallo"]:
                    a["estado"] = "fallo"
                    a["mensajes"].append(e["msg"])
            if fase == "verificando" and e["rol"] == "kafka_decide" and e["ev"] in ("runner_on_ok", "runner_item_on_ok", "runner_on_failed", "runner_item_on_failed") \
                    and e["msg"] and e["msg"] != "All assertions passed" and not e["tarea"].startswith("Validating"):
                verificacion.append({"ok": not e["fallo"], "msg": e["msg"]})
        if d["estado"] == "successful":
            for a in acciones:
                if a["estado"] in ("en_curso", "pendiente") and fase in ("verificando", "notificando"):
                    a["estado"] = "hecho"
        d.update({"fase": fase, "acciones": acciones, "verificacion": verificacion[-12:],
                  "fallo": self._primer_fallo(evs)})
        return d

    # ── identidad y vencimiento del token de AAP ────────────────────────────
    def credencial(self):
        out = {"nombre": "AAP", "cargado": self.token.existe(), "valido": False}
        try:
            me = self._get("/me/").get("results", [{}])[0]
            out.update({"valido": True, "identidad": me.get("username")})
            toks = self.http.json(self.gateway + "/api/gateway/v1/tokens/?page_size=50", self.token.valor()).get("results", [])
            vencen = sorted(t["expires"] for t in toks if t.get("expires"))
            if vencen:
                out["vence"] = vencen[0]
                out["nota"] = "el más próximo a vencer de los tokens del usuario"
        except Exception as e:
            out["error"] = describir_error(e)
        return out
