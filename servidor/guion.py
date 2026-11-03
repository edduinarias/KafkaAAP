"""El guion de la demo: los pasos en orden, y cuando se cumple cada uno.

La pagina marca un paso como hecho cuando ve que se cumplio -un escenario
montado, una operacion de AAP terminada bien-, y pasa al siguiente. Tambien se
puede saltar o volver a mano.
"""
import time


def cumple(c, e):
    """Evalua una condicion del guion o de un escenario contra el estado que
    arma el modelo."""
    if not c:
        return False
    sit = e.get("sitios") or {}
    S = (e.get("pareja") or {}).get("sitios") or list(sit)
    if isinstance(c, dict):
        op = e.get("operacion") or {}
        return (op.get("id") is not None and op.get("id") > c.get("_desde_op", -1)
                and op.get("estado") == "successful" and op.get("transicion") == c.get("operacion")
                and (not c.get("direccion") or op.get("direccion") == c["direccion"]))
    if c == "normal":
        reps = {r["clave"]: r.get("estado") for r in e.get("replicaciones") or []}
        a, b = S[0], S[1]
        return (e.get("activo") == a
                and all((sit.get(s) or {}).get("rol") in ("activo", "en_espera") for s in S)
                and reps.get("%s_%s" % (a, b)) == "ACTIVO" and reps.get("%s_%s" % (b, a)) == "PASIVO"
                and all(((sit.get(s) or {}).get("proxy") or {}).get("destino") == a for s in S))
    t = (e.get("temenos") or {}).get("continuo") or {}
    op = e.get("operacion") or {}
    if c == "temenos_encendido":
        return bool(t)
    if c == "temenos_fallando":
        return bool(t) and bool(t.get("ultimo_error") or t.get("errores"))
    if c == "temenos_sin_errores":
        return bool(t) and not t.get("ultimo_error") and t.get("enviados", 0) > 0
    if c == "contenido_distinto":
        cc = e.get("contenido") or {}
        return bool(cc.get("medido")) and cc.get("igual") is False
    if c == "aprobacion_pendiente":
        return bool(op.get("visible") and op.get("en_curso") and (op.get("fases") or [{}, {}])[1].get("estado") == "esperando")
    if c == "operacion_en_curso":
        return bool(op.get("visible") and op.get("en_curso"))
    if c == "garantia_reducida":
        return bool(op.get("visible") and op.get("garantia"))
    if c.startswith("situacion_"):
        return (e.get("situacion") or {}).get("nivel") == c[len("situacion_"):]
    reps = {r["clave"]: r for r in e.get("replicaciones") or []}
    if c.startswith("replica_") and c.count("_") >= 3:   # replica_<o>_<d>_<ESTADO>
        o, d, est = c[len("replica_"):].split("_", 2)
        return (reps.get("%s_%s" % (o, d)) or {}).get("estado") == est
    if c.startswith("copiando_"):
        return bool((reps.get(c[len("copiando_"):]) or {}).get("copiando"))
    if c.startswith("proxies_a_"):
        s = c[len("proxies_a_"):]
        return all(((sit.get(x) or {}).get("proxy") or {}).get("destino") == s for x in S)
    if c.startswith("apps_"):
        s, est = c[len("apps_"):].split("_", 1)
        cons = (sit.get(s) or {}).get("consumidor") or {}
        return cons.get("estado") == "procesando" if est == "procesando" else cons.get("replicas", 1) == 0
    if c == "temenos_detenido":
        return not t
    if c == "contenido_igual":
        return bool((e.get("contenido") or {}).get("igual"))
    if c == "consumidores_desfasados":
        # La posicion de los consumidores todavia no llego al otro sitio: la
        # validacion de un failover lo frenaria (N21).
        d = [(sit.get(x) or {}).get("datos") or {} for x in S]
        return all(x.get("vigente") for x in d) and len({x.get("atraso") for x in d}) > 1
    if c == "a_medias":
        return bool(e.get("desalineados"))
    if c == "replica_pausada":
        return any(r.get("estado") == "PAUSADO" for r in e.get("replicaciones") or [])
    for s in S:
        if c == s + "_caido":
            return (sit.get(s) or {}).get("rol") == "caido"
        if c == s + "_sirviendo":
            return (sit.get(s) or {}).get("rol") in ("activo", "en_espera")
        if c == "activo_" + s:
            return e.get("activo") == s
    return False


class Guion:
    def __init__(self, definicion):
        self.pasos = definicion.get("pasos", [])
        self.activo = False
        self.indice = 0
        self.hechos = {}          # indice -> hora en que se cumplio
        self.desde_op = -1        # ultima operacion vista al empezar el paso actual
        self.ultima_op = -1
        self.vistos = {}          # indice -> indices de "ves" ya observados
        self.actos = {int(k): v for k, v in (definicion.get("actos") or {}).items()}
        self.al_cumplir = None    # callback(indice, titulo)

    # ── memoria entre reinicios ─────────────────────────────────────────────
    def exportar(self):
        return {"activo": self.activo, "indice": self.indice, "desde_op": self.desde_op,
                "hechos": {str(k): v for k, v in self.hechos.items()},
                "vistos": {str(k): sorted(v) for k, v in self.vistos.items()}}

    def importar(self, d):
        if not d:
            return
        self.activo = bool(d.get("activo"))
        self.indice = min(int(d.get("indice", 0)), max(len(self.pasos) - 1, 0))
        self.desde_op = int(d.get("desde_op", -1))
        self.hechos = {int(k): v for k, v in (d.get("hechos") or {}).items()}
        self.vistos = {int(k): set(v) for k, v in (d.get("vistos") or {}).items()}
        if not self.activo:
            self.vistos = {}
            # Un guion detenido no muestra pasos de una corrida anterior: confunde.
            self.indice, self.hechos = 0, {}

    # ── acciones de la persona ──────────────────────────────────────────────
    def accion(self, que, indice=None):
        if que == "iniciar":
            self.activo, self.indice, self.hechos, self.vistos = True, 0, {}, {}
            self.desde_op = self.ultima_op
        elif que == "terminar":
            self.activo, self.indice, self.hechos, self.vistos = False, 0, {}, {}
        elif que == "listo":
            self._cumplir(self.indice, manual=True)
        elif que == "ir" and indice is not None and 0 <= int(indice) < len(self.pasos):
            self.activo = True
            self.indice = int(indice)
            self.hechos = {k: v for k, v in self.hechos.items() if k < self.indice}
            self.vistos = {k: v for k, v in self.vistos.items() if k < self.indice}
            self.desde_op = self.ultima_op
        else:
            raise ValueError("acción del guion desconocida")

    def _cumplir(self, i, manual=False):
        self.hechos[i] = time.time()
        if self.al_cumplir:
            self.al_cumplir(i, self.pasos[i]["titulo"], manual)
        if i + 1 < len(self.pasos):
            self.indice = i + 1
            self.desde_op = self.ultima_op
        else:
            self.activo = False

    # ── evaluacion en cada vuelta ───────────────────────────────────────────
    def evaluar(self, e, enlaces):
        """e: el estado que arma el modelo. enlaces: operacion -> URL del flujo
        en AAP. Devuelve lo que la pagina muestra del guion."""
        op = e.get("operacion") or {}
        if op.get("id") is not None:
            self.ultima_op = max(self.ultima_op, op["id"])
        if self.activo and self.pasos:
            p = self.pasos[self.indice]
            visto = self.vistos.setdefault(self.indice, set())
            for j, v in enumerate(p.get("ves", [])):
                if j not in visto and cumple(v.get("si"), e):
                    visto.add(j)
            conds = [dict(c, _desde_op=self.desde_op) if isinstance(c, dict) else c for c in p.get("hecho_si", [])]
            if conds and all(cumple(c, e) for c in conds):
                self._cumplir(self.indice)
        out = []
        for i, p in enumerate(self.pasos):
            estado = "hecho" if i in self.hechos else ("actual" if self.activo and i == self.indice else "pendiente")
            vistos = self.vistos.get(i, set())
            item = {"indice": i, "titulo": p["titulo"], "acto": p.get("acto", 1), "caso": p.get("caso"),
                    "tarda": p.get("tarda"), "dices": (p.get("dices") or "").strip(), "amplia": p.get("amplia") or [],
                    "haces": (p.get("haces") or "").strip(), "por_dentro": (p.get("por_dentro") or "").strip(),
                    "ves": [{"texto": v["texto"], "visto": j in vistos} for j, v in enumerate(p.get("ves", []))],
                    "estado": estado, "hecho_t": self.hechos.get(i), "manual": not p.get("hecho_si"),
                    "escenario": p.get("escenario"), "temenos": p.get("temenos"), "aap": None, "avisos": [],
                    "operacion": None}
            if p.get("aap"):
                a = p["aap"]
                item["aap"] = {"operacion": a["operacion"], "direccion": a.get("direccion"),
                               "url": enlaces.get(a["operacion"])}
                # La operacion de AAP de este paso, si ya se lanzo: para decir
                # en que va o por que se freno, sin tener que mirar AAP.
                if estado == "actual" and op.get("id") is not None and op["id"] > self.desde_op:
                    item["operacion"] = {"id": op["id"], "estado": op.get("estado"), "en_curso": op.get("en_curso"),
                                         "situacion": None}
            if estado == "actual":
                item["avisos"] = [a["texto"] for a in p.get("avisos", []) if cumple(a["si"], e)]
            out.append(item)
        return {"activo": self.activo, "indice": self.indice, "total": len(self.pasos),
                "hechos": len(self.hechos), "pasos": out,
                "actos": {str(k): v for k, v in self.actos.items()}}
