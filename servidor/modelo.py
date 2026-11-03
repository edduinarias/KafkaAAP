"""El estado de la demo en lenguaje funcional, y su linea de tiempo.

Recibe lo que leyeron los recolectores y devuelve lo que la pagina muestra:
quien atiende, que replica hacia donde, si los dos sitios tienen el mismo
contenido, en que va la operacion y cada cambio dicho en palabras.
"""
import datetime as dt
import time
from collections import deque

RUIDO = {"All assertions passed", "All items completed", "The arg spec validation passed", "ok", ""}
FINALES = ("successful", "failed", "error", "canceled")
TITULOS_SITIO = {"co": "Centro de Operaciones", "ca": "Centro Alterno"}
ESTADO_REPLICA = {"ACTIVO": "activa", "PASIVO": "en espera", "PAUSADO": "pausada", "AUSENTE": "no existe"}


def _iso(t=None):
    return dt.datetime.fromtimestamp(t or time.time(), dt.timezone.utc).isoformat()


def _ts(iso):
    try:
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _esperas(n):
    """Los reintentos de un until son comprobaciones de que el cambio quedo
    aplicado, no fallas: se dicen asi."""
    return "%d %s hasta quedar listo" % (n + 1, "comprobación" if n == 0 else "comprobaciones")


def _limpio(msg):
    m = (msg or "").replace("\\n", " ").replace("\n", " ")
    m = " ".join(m.split())
    return None if m in RUIDO or m.startswith("Validating arguments") else m


class Modelo:
    def __init__(self, cfg, proyecto):
        self.cfg, self.pj = cfg, proyecto
        self.pareja_clave = cfg["pareja"]
        self.pareja = proyecto["parejas"][self.pareja_clave]
        self.sitios = list(self.pareja["sitios"].keys())
        n = int(cfg["historia_minutos"] * 60 / cfg["intervalos"]["vista"])
        self.historia = deque(maxlen=n)
        self.eventos = deque(maxlen=150)
        self.ultimo_dato = {}
        self.prev = None
        self.op_visto = None
        self.acumulado = {s: 0 for s in self.sitios}
        self.acumulado_desde = time.time()
        self.reinicios_visto = {}
        self.op_base = False          # la primera lectura de AAP es punto de partida, no un cambio
        self.recuperado = False

    # ── memoria entre reinicios ─────────────────────────────────────────────
    def exportar(self):
        return {"t": time.time(), "eventos": list(self.eventos), "historia": list(self.historia),
                "ultimo_dato": self.ultimo_dato}

    def importar(self, d, max_seg):
        """Lo que la pagina ya mostro sigue valiendo despues de un reinicio, si es
        reciente: la linea de tiempo, la historia de los graficos y el ultimo
        dato de cada sitio (marcado como viejo)."""
        if time.time() - float(d.get("t", 0)) > max_seg:
            return False
        self.eventos = deque(d.get("eventos", []), maxlen=self.eventos.maxlen)
        self.historia = deque(d.get("historia", []), maxlen=self.historia.maxlen)
        self.ultimo_dato = {s: v for s, v in (d.get("ultimo_dato") or {}).items() if s in self.sitios}
        self.recuperado = True
        return True

    # ── utilidades ──────────────────────────────────────────────────────────
    def evento(self, texto, nivel="info", grupo="ambiente"):
        """Para lo que pasa fuera del modelo: el guion, los escenarios."""
        self._evento(texto, nivel, grupo)

    def _evento(self, texto, nivel="info", grupo="ambiente", t=None):
        self.eventos.appendleft({"t": _iso(t), "texto": texto, "nivel": nivel, "grupo": grupo})

    @staticmethod
    def _S(s):
        return (s or "?").upper()

    def _ritmo(self, s, segundos=12, campo="_fin"):
        """Mensajes por segundo que entran al sitio (fin de log) o que consumen
        sus aplicaciones (posicion del grupo)."""
        if len(self.historia) < 2:
            return 0.0
        ahora = self.historia[-1]
        for h in reversed(self.historia):
            if ahora["t"] - h["t"] >= segundos:
                a, b = h.get(s + campo), ahora.get(s + campo)
                if a is None or b is None:
                    return 0.0
                return max(0.0, (b - a) / (ahora["t"] - h["t"]))
        return 0.0

    # ── un sitio ────────────────────────────────────────────────────────────
    def _sitio(self, s, d, m):
        d, m = d or {}, m or {}
        brokers = d.get("brokers") or []
        listos = sum(1 for b in brokers if b.get("listo"))
        topicos = m.get("topicos") or {}
        # Con el Kafka caido el exporter puede seguir respondiendo, pero sin
        # datos del topico: eso no es una medicion de cero mensajes.
        medido = bool(m.get("medido")) and bool(topicos) and all(t.get("particiones") for t in topicos.values())
        datos = None
        if medido and topicos:
            fin = sum(x.get("fin", 0) for x in topicos.values())
            inicio = sum(x.get("inicio", 0) for x in topicos.values())
            pos = atr = 0
            for gr in (m.get("grupos") or {}).values():
                for x in gr.values():
                    pos += x.get("posicion", 0)
                    atr += x.get("atraso", 0)
            datos = {"fin": fin, "inicio": inicio, "retenidos": fin - inicio, "posicion": pos,
                     "atraso": atr, "sub_replicadas": m.get("sub_replicadas", 0), "t": time.time(), "vigente": True}
            self.ultimo_dato[s] = datos
        elif s in self.ultimo_dato:
            datos = dict(self.ultimo_dato[s], vigente=False)
        apps = d.get("aplicaciones") or []
        cons = apps[0] if apps else None
        return {
            "clave": s, "etiqueta": self._S(s), "titulo": TITULOS_SITIO.get(s, ""),
            "leido": bool(d), "alcanzable": bool(d.get("alcanzable")),
            "kafka": {"brokers": brokers, "total": len(brokers), "listos": listos,
                      "sirviendo": None if not m else (bool(d.get("alcanzable")) and listos > 0),
                      "caida_simulada": bool(d.get("caida_simulada"))},
            "proxy": d.get("proxy"),
            "consumidor": None if not cons else {
                "nombre": cons["nombre"], "replicas": cons["replicas"], "listas": cons["listas"],
                "estado": "procesando" if cons["listas"] > 0 else ("arrancando" if cons["replicas"] > 0 else "detenido")},
            "datos": datos,
            "temenos": d.get("temenos"),
            "errores": dict(d.get("errores") or {}, **({"metricas": m["error"]} if m.get("error") else {})),
            "latencia_ms": d.get("latencia_ms"),
        }

    # ── el armado completo ──────────────────────────────────────────────────
    def armar(self, L):
        t = time.time()
        sitios = {s: self._sitio(s, L["sitios"].get(s), L["metricas"].get(s)) for s in self.sitios}
        punto = {"t": t}
        for s, v in sitios.items():
            dd = v["datos"] if v["datos"] and v["datos"]["vigente"] else None
            punto[s + "_ret"] = dd["retenidos"] if dd else None
            punto[s + "_fin"] = dd["fin"] if dd else None
            punto[s + "_atr"] = dd["atraso"] if dd else None
            punto[s + "_pos"] = dd["posicion"] if dd else None
        self.historia.append(punto)
        for s, v in sitios.items():
            if v["datos"]:
                v["datos"]["ritmo"] = round(self._ritmo(s), 1)
                v["datos"]["consumo"] = round(self._ritmo(s, campo="_pos"), 1)

        reps = {}
        for s in self.sitios:
            reps.update((L["sitios"].get(s) or {}).get("replicaciones") or {})
        replicaciones = []
        for clave, mm in self.pareja.get("mirrormakers", {}).items():
            r = dict(reps.get(clave) or {"clave": clave, "estado": "SIN_DATO", "nombre": mm["name"]})
            o, de = clave.split("_")
            r.update({"origen": o, "destino": de, "vive_en": mm["sitio"],
                      "titulo": "Réplica %s → %s" % (o.upper(), de.upper())})
            cx = (r.get("connect") or [{}])[0] if r.get("connect") else {}
            r["conectores_ok"] = bool(r.get("conectores")) and all(c["estado"] == "RUNNING" for c in r["conectores"])
            r["connect_estado"] = cx.get("motivo") or (("listo" if cx.get("listo") else cx.get("fase")) if cx else None)
            r["connect_reinicios"] = cx.get("reinicios", 0) if cx else 0
            ddest = sitios[de]["datos"]
            r["copiando"] = r.get("estado") == "ACTIVO" and bool(ddest and ddest.get("vigente") and ddest.get("ritmo", 0) > 0)
            r["texto"] = ESTADO_REPLICA.get(r.get("estado"), "sin dato")
            replicaciones.append(r)

        encendidas = [r for r in replicaciones if r.get("estado") in ("ACTIVO", "PAUSADO")]
        activo = encendidas[0]["origen"] if len(encendidas) == 1 else None
        if activo is None:
            dest = {(v.get("proxy") or {}).get("destino") for v in sitios.values()}
            if len(dest) == 1 and None not in dest:
                activo = dest.pop()
        for s, v in sitios.items():
            if not v["leido"] or (v["alcanzable"] and v["kafka"]["sirviendo"] is None):
                v["rol"] = "leyendo"
            elif not v["alcanzable"]:
                v["rol"] = "sin_conexion"
            elif not v["kafka"]["sirviendo"]:
                v["rol"] = "caido"
            elif s == activo:
                v["rol"] = "activo"
            else:
                v["rol"] = "en_espera"

        contenido = self._contenido(sitios)
        # Lo que no acompana al sitio que atiende: la misma regla que el
        # descubrimiento de la automatizacion (N23). Sin esto la pagina, como la
        # automatizacion antes, mostraba que un sitio atiende con el trafico en
        # el otro.
        desalineados = []
        if activo:
            for s, v in sitios.items():
                if not v["alcanzable"]:
                    continue
                d = (v.get("proxy") or {}).get("destino")
                if d and d != activo:
                    desalineados.append("el proxy de %s lleva al Kafka de %s" % (s.upper(), d.upper()))
                if s != activo and ((v.get("consumidor") or {}).get("replicas") or 0) > 0:
                    desalineados.append("las aplicaciones procesan en %s" % s.upper())
        estado = {"sitios": sitios, "replicaciones": replicaciones, "activo": activo, "contenido": contenido,
                  "desalineados": desalineados}
        operacion = self._operacion(L.get("operacion"), estado)
        situacion = self._situacion(sitios, replicaciones, activo, contenido, operacion, desalineados)
        self._linea_de_tiempo(estado, operacion, bool(L.get("aap_leido")))
        self.prev = estado

        return {
            "t": _iso(t),
            "pareja": {"clave": self.pareja_clave, "descripcion": self.pareja.get("descripcion", ""),
                       "sitios": self.sitios, "topicos": self.pareja.get("topicos_aplicacion", []),
                       "grupos": self.pareja.get("grupos_consumo", [])},
            **estado,
            "situacion": situacion,
            "operacion": operacion,
            "casos": self._casos(L.get("plantillas") or [], operacion),
            "credenciales": L.get("credenciales") or [],
            "temenos": L.get("temenos"),
            "historia": list(self.historia)[-480:],
            "eventos": list(self.eventos)[:60],
            "aap": {"url": L.get("aap_url"), "aprobaciones": L.get("aap_aprobaciones")},
            "salud": L.get("salud"),
        }

    def _contenido(self, sitios):
        a, b = self.sitios[0], self.sitios[1]
        da, db = sitios[a]["datos"], sitios[b]["datos"]
        if not (da and db and da["vigente"] and db["vigente"]):
            falta = [s.upper() for s in (a, b) if not (sitios[s]["datos"] and sitios[s]["datos"]["vigente"])]
            return {"medido": False, "texto": "Sin medición de %s" % " ni ".join(falta)}
        dif = da["retenidos"] - db["retenidos"]
        # Con carga entrando, lo que esta en camino entre un sitio y el otro no
        # es una diferencia: es la replicacion haciendo su trabajo. El margen
        # son unos segundos de ese ritmo; una diferencia real, como la ventana
        # de un crash, lo supera y se muestra como tal.
        ritmo = max(da.get("ritmo", 0), db.get("ritmo", 0))
        if dif != 0 and ritmo > 0 and abs(dif) <= ritmo * 4 + 2:
            return {"medido": True, "igual": None, "transito": True, "diferencia": abs(dif),
                    "texto": "Entrando a %s y %s: %d en camino de un sitio al otro" % (a.upper(), b.upper(), abs(dif))}
        if dif == 0:
            return {"medido": True, "igual": True, "diferencia": 0,
                    "texto": "%s y %s tienen el mismo contenido" % (a.upper(), b.upper())}
        mas, menos = (a, b) if dif > 0 else (b, a)
        return {"medido": True, "igual": False, "diferencia": abs(dif), "adelante": mas,
                "texto": "%s tiene %s mensajes que %s no" % (mas.upper(), f"{abs(dif):,}", menos.upper())}

    # ── la situacion en una frase ───────────────────────────────────────────
    def _situacion(self, sitios, reps, activo, contenido, op, desalineados=()):
        if op and op.get("en_curso"):
            if op["fases"][1]["estado"] == "esperando":
                return {"nivel": "espera", "titulo": "Esperando la aprobación de una persona",
                        "detalle": "%s · la automatización no avanza sin una firma en AAP" % op["nombre"]}
            return {"nivel": "en_curso", "titulo": "Operación en curso: %s" % op["nombre"],
                    "detalle": op.get("fase_texto") or ""}
        if op and op.get("visible") and op["estado"] in ("failed", "error", "canceled"):
            f = {x["clave"]: x["estado"] for x in op["fases"]}
            motivo = (op.get("fallo") or {}).get("msg") or ""
            if op["estado"] == "canceled":
                return {"nivel": "aviso", "titulo": "«%s» se canceló" % op["nombre"],
                        "detalle": "Se canceló desde AAP. Lo ejecutado antes de cancelar quedó aplicado."}
            if f["validacion"] == "fallo":
                return {"nivel": "aviso", "titulo": "La validación detuvo «%s» sin tocar nada" % op["nombre"],
                        "detalle": motivo[:220]}
            if f["aprobacion"] == "fallo":
                r = (op.get("aprobacion") or {}).get("resultado") or "no aprobada"
                return {"nivel": "aviso", "titulo": "«%s» no se ejecutó: aprobación %s" % (op["nombre"], r),
                        "detalle": "Sin aprobación, la automatización no modifica nada."}
            paso = next(((i, x) for i, x in enumerate(op["acciones"]) if x["estado"] == "fallo"), None)
            donde = " en el paso %d de %d: %s" % (paso[0] + 1, len(op["acciones"]), paso[1]["titulo"]) if paso else ""
            return {"nivel": "critico", "titulo": "«%s» se detuvo%s" % (op["nombre"], donde),
                    "detalle": "Lo ejecutado antes quedó aplicado y lo pendiente no se ejecutó. %s" % motivo[:160]}
        if desalineados and not (op and op.get("en_curso")):
            return {"nivel": "critico",
                    "titulo": "Estado a medias: la réplica dice que atiende %s, pero %s" % (activo.upper(), desalineados[0]),
                    "detalle": "Una operación quedó interrumpida. Relanzada desde AAP, la automatización la reanuda "
                               "si completarla no deja mensajes varados (N23)."}
        if any(v["rol"] == "leyendo" for v in sitios.values()):
            return {"nivel": "info", "titulo": "Leyendo el ambiente…", "detalle": "Primera lectura de los sitios en curso"}
        caidos = [s for s, v in sitios.items() if v["rol"] in ("caido", "sin_conexion")]
        if caidos:
            s = caidos[0]
            simulada = " (simulada)" if sitios[s]["kafka"]["caida_simulada"] else ""
            if s == activo:
                return {"nivel": "critico", "titulo": "Contingencia: el Kafka de %s no responde%s" % (s.upper(), simulada),
                        "detalle": "Es el sitio que atiende la operación. Corresponde el failover de contingencia."}
            return {"nivel": "aviso", "titulo": "El sitio en espera (%s) no responde%s" % (s.upper(), simulada),
                    "detalle": "%s sigue atendiendo, pero sin respaldo mientras %s no vuelva." % ((activo or "?").upper(), s.upper())}
        if activo is None:
            return {"nivel": "aviso", "titulo": "No se puede establecer qué sitio atiende",
                    "detalle": "Las réplicas y los proxies no son coherentes entre sí."}
        otro = [s for s in self.sitios if s != activo][0]
        pausada = [r for r in reps if r.get("estado") == "PAUSADO"]
        if pausada:
            return {"nivel": "aviso", "titulo": "%s atiende · la réplica hacia %s está pausada" % (activo.upper(), otro.upper()),
                    "detalle": "%s no recibe lo que entra en %s mientras siga pausada." % (otro.upper(), activo.upper())}
        principal = self.sitios[0]
        if activo == principal:
            t = "Operación normal · %s atiende, %s en espera" % (activo.upper(), otro.upper())
        else:
            t = "%s atiende la operación · %s en espera" % (activo.upper(), otro.upper())
        det = contenido["texto"] if contenido.get("medido") else contenido.get("texto", "")
        nivel = "ok" if (contenido.get("igual") or contenido.get("transito") or not contenido.get("medido")) else "info"
        return {"nivel": nivel, "titulo": t, "detalle": det}

    # ── la operacion de AAP, en palabras ────────────────────────────────────
    def _accion(self, a, plan):
        sa, sb = plan.get("sitio_a"), plan.get("sitio_b")
        S = lambda k: (sa if k == "sitio_a" else sb if k == "sitio_b" else k or "?").upper()
        rol = a.get("rol")
        if rol in ("mm2_state", "mm2_lifecycle"):
            k = plan.get("mm_hacia_b") if (a.get("sentido") or a.get("mm")) == "hacia_b" else plan.get("mm_hacia_a")
            o, d = (k or "?_?").split("_")
            mm = self.pareja.get("mirrormakers", {}).get(k, {}).get("name", k)
            if rol == "mm2_state":
                verbo = "Encender" if a.get("estado") == "ACTIVO" else "Apagar"
                return "%s la réplica %s → %s" % (verbo, o.upper(), d.upper()), "mm2_state · %s · replicas=%s" % (mm, 1 if a.get("estado") == "ACTIVO" else 0)
            verbo = "Eliminar" if a.get("accion") == "borrar" else "Recrear"
            return "%s la réplica %s → %s" % (verbo, o.upper(), d.upper()), "mm2_lifecycle · %s · %s" % (mm, a.get("accion"))
        if rol == "proxy_target":
            return "Apuntar el proxy de %s al Kafka de %s" % (S(a.get("sitio")), S(a.get("destino"))), "proxy_target · VirtualKafkaCluster, y espera a que el proxy en marcha rote con el destino nuevo"
        if rol == "app_scale":
            arr = a.get("estado") == "activo"
            return "%s las aplicaciones de %s" % ("Arrancar" if arr else "Detener", S(a.get("sitio"))), "app_scale · kafka-consumer-app → %s" % ("1 réplica" if arr else "0 réplicas")
        if rol == "resync_control":
            if a.get("accion") == "exigir_quietud":
                return "Comprobar que Temenos dejó de escribir en %s" % S(a.get("sitio")), "resync_control · fin de log medido dos veces"
            if a.get("accion") == "verificar_retoma":
                k = plan.get("mm_hacia_a") if a.get("mm") == "hacia_a" else plan.get("mm_hacia_b")
                o, d = (k or "?_?").split("_")
                return "Comprobar desde dónde retoma la réplica %s → %s" % (o.upper(), d.upper()), "resync_control · posición guardada contra lo retenido"
            de = S(a.get("desde"))
            hacia = (sb if a.get("desde") == "sitio_a" else sa or "?").upper()
            return "Esperar a que %s iguale el contenido de %s" % (hacia, de), "resync_control · criterio %s" % a.get("criterio", "igualdad")
        if rol == "topic_align":
            return "Descartar tópicos (%s) en %s" % (a.get("alcance"), S(a.get("sitio"))), "topic_align · por el API de Kafka"
        return rol or "?", ""

    def _esperado(self, plan, e):
        """El estado al que lleva la operacion, segun el contrato, contra lo que
        se ve ahora. Lo que el contrato no declara no se inventa."""
        t = next((x for x in self.pj["contrato"].get("transiciones", []) if x["id"] == plan.get("transicion")), None)
        if not t or plan.get("nada_que_hacer"):
            return []
        res = lambda k: plan.get(k) if k in ("sitio_a", "sitio_b") else k
        h, out = t.get("hasta") or {}, []
        if h.get("activo"):
            s = res(h["activo"])
            out.append({"texto": "%s atiende la operación" % self._S(s), "cumple": e["activo"] == s})
        reps = {r["clave"]: r for r in e["replicaciones"]}
        for sentido, est in (h.get("mirrormakers") or {}).items():
            k = plan.get("mm_" + sentido) or "?_?"
            o, d = k.split("_")
            out.append({"texto": "Réplica %s → %s %s" % (o.upper(), d.upper(), ESTADO_REPLICA.get(est, est)),
                        "cumple": (reps.get(k) or {}).get("estado") == est})
        if h.get("proxy_destino"):
            s = res(h["proxy_destino"])
            for x in self.sitios:
                out.append({"texto": "El proxy de %s envía al Kafka de %s" % (x.upper(), self._S(s)),
                            "cumple": ((e["sitios"][x].get("proxy") or {}).get("destino")) == s})
        apps = {}
        for a in plan.get("acciones", []):
            if a.get("rol") == "app_scale":
                apps[res(a.get("sitio"))] = a.get("estado")
        for s, est in apps.items():
            c = (e["sitios"].get(s) or {}).get("consumidor") or {}
            ok = (c.get("replicas", 0) > 0 and c.get("listas", 0) > 0) if est == "activo" else c.get("replicas", 1) == 0
            out.append({"texto": "Aplicaciones de %s %s" % (self._S(s), "procesando" if est == "activo" else "detenidas"), "cumple": ok})
        if any(a.get("rol") == "resync_control" and a.get("criterio", "igualdad") == "igualdad"
               and a.get("accion") == "esperar_igualdad" for a in plan.get("acciones", [])):
            out.append({"texto": "%s y %s con el mismo contenido" % tuple(x.upper() for x in self.sitios),
                        "cumple": bool(e["contenido"].get("igual"))})
        return out

    def _operacion(self, op, e):
        if not op:
            return None
        cat = (self.pj.get("catalogo") or {}).get("operaciones", {}).get(op.get("operacion"), {})
        plan = op.get("plan") or {}
        nombre = cat.get("nombre") or op.get("operacion") or op.get("flujo")
        variante = (cat.get("variantes") or {}).get(plan.get("transicion"))
        en_curso = op["estado"] not in FINALES
        fin = _ts(op.get("fin")) if op.get("fin") else None
        if not en_curso and fin and time.time() - fin > self.cfg["resultado_visible_minutos"] * 60:
            return {"visible": False, "id": op["id"], "nombre": nombre, "estado": op["estado"], "fin": op.get("fin"),
                    "operacion": op.get("operacion")}

        pf, ap, apl = op.get("preflight"), op.get("aprobacion"), op.get("aplicar")
        def est_job(j):
            if not j:
                return "pendiente"
            return {"successful": "hecho", "failed": "fallo", "error": "fallo", "canceled": "cancelado"}.get(j["estado"], "en_curso")
        f_val = est_job(pf) if pf else ("en_curso" if en_curso else "pendiente")
        if ap:
            f_apr = {"aprobada": "hecho", "denegada": "fallo", "vencida": "fallo", "pendiente": "esperando"}.get(ap["resultado"], "en_curso")
        else:
            f_apr = "pendiente" if f_val in ("pendiente", "en_curso", "hecho") else "omitido"
        f_eje = f_ver = "pendiente"
        if apl:
            fase = apl.get("fase")
            fallo_job = apl["estado"] in ("failed", "error")
            if fase in ("esperando", "revalidando", "ejecutando"):
                f_eje = "fallo" if fallo_job else "en_curso"
            elif fase in ("verificando", "notificando"):
                f_eje = "hecho"
                f_ver = "fallo" if fallo_job and fase == "verificando" else ("hecho" if fase == "notificando" or apl["estado"] == "successful" else "en_curso")
            elif fase == "fallo":
                f_eje = "fallo"
            if apl["estado"] == "successful":
                f_eje, f_ver = "hecho", "hecho"
        elif not en_curso and f_val == "fallo":
            f_apr = f_eje = f_ver = "omitido"
        if plan.get("nada_que_hacer"):
            f_eje = f_ver = "omitido"

        prechecks, vistos = [], set()
        for p in (pf or {}).get("prechecks", []):
            msg = _limpio(p["msg"])
            if not msg or (p["nombre"], msg) in vistos:
                continue
            vistos.add((p["nombre"], msg))
            prechecks.append({"nombre": p["nombre"], "ok": p["ok"], "msg": msg,
                              "funcional": (self.pj.get("catalogo") or {}).get("controles", {}).get(p["nombre"])})

        acciones = []
        ejec = {a["indice"]: a for a in (apl or {}).get("acciones", [])}
        for i, a in enumerate(plan.get("acciones", [])):
            titulo, tecnico = self._accion(a, plan)
            hecho = ejec.get(i, {})
            msgs = [m for m in (_limpio(x) for x in hecho.get("mensajes", [])) if m]
            acciones.append({"titulo": titulo, "tecnico": tecnico, "estado": hecho.get("estado", "pendiente"),
                             "reintentos": hecho.get("reintentos", 0), "dato": msgs[-1] if msgs else None})

        verificacion = [{"ok": v["ok"], "msg": m} for v in (apl or {}).get("verificacion", [])
                        for m in [_limpio(v["msg"])] if m]
        fases = [
            {"clave": "validacion", "titulo": "Validación", "subtitulo": "controles contra el estado real", "estado": f_val},
            {"clave": "aprobacion", "titulo": "Aprobación", "subtitulo": "una persona firma en AAP", "estado": f_apr},
            {"clave": "ejecucion", "titulo": "Ejecución", "subtitulo": "las acciones del plan, en orden", "estado": f_eje},
            {"clave": "verificacion", "titulo": "Verificación", "subtitulo": "el estado final contra el contrato", "estado": f_ver},
        ]
        actual = next((f for f in fases if f["estado"] in ("en_curso", "esperando")), None)
        paso = next(((i, a) for i, a in enumerate(acciones) if a["estado"] == "en_curso"), None)
        if actual and actual["clave"] == "ejecucion" and paso:
            fase_texto = "Paso %d de %d: %s" % (paso[0] + 1, len(acciones), paso[1]["titulo"])
        else:
            fase_texto = actual["titulo"] + " · " + actual["subtitulo"] if actual else ""
        fallo = (apl or {}).get("fallo") or (pf or {}).get("fallo")
        return {
            "visible": True, "id": op["id"], "en_curso": en_curso, "estado": op["estado"],
            "nombre": nombre, "variante": variante, "transicion": plan.get("transicion"),
            "descripcion": plan.get("descripcion"), "flujo": op["flujo"],
            "pareja": (op.get("pareja") or self.pareja_clave).upper(),
            "direccion": op.get("direccion"), "activo_final": plan.get("activo_final"),
            "inicio": op.get("inicio"), "fin": op.get("fin"), "url": op.get("url"),
            "url_aprobaciones": op.get("url_aprobaciones"),
            "aprobacion": ap, "garantia": {"titulo": plan.get("garantia_titulo"), "motivo": plan.get("garantia_motivo")} if plan.get("garantia_reducida") else None,
            "nada_que_hacer": bool(plan.get("nada_que_hacer")), "motivo_sin_cambios": plan.get("motivo_sin_cambios"),
            "operacion": op.get("operacion"), "reanudacion": bool(plan.get("reanudacion")),
            "aplicadas": plan.get("aplicadas") or [],
            "fases": fases, "fase_texto": fase_texto,
            "prechecks": prechecks, "acciones": acciones, "verificacion": verificacion[-8:],
            "fallo": {"tarea": fallo["tarea"], "msg": _limpio(fallo["msg"])} if fallo else None,
            "esperado": self._esperado(plan, e),
        }

    # ── la matriz de casos de uso, desde el contrato ───────────────────────
    def _casos(self, plantillas, op):
        """Filas: parejas. Columnas: casos. Cada celda lista las operaciones que
        el contrato declara para esa pareja y ese caso, con su flujo en AAP."""
        cat = self.pj.get("catalogo") or {}
        ops_cat = cat.get("operaciones") or {}
        parejas = list(dict.fromkeys(list(self.pj.get("parejas", {}).keys()) + list((cat.get("parejas") or {}).keys())))
        en_curso = op.get("operacion") if op and op.get("en_curso") else None
        filas = []
        for p in parejas:
            pc = (cat.get("parejas") or {}).get(p, {})
            celdas = []
            for c in cat.get("casos", []):
                ops = []
                for t in self.pj["contrato"].get("transiciones", []):
                    o = t["operacion"]
                    oc = ops_cat.get(o, {})
                    if p not in t.get("aplica_a", []) or oc.get("caso", o) != c["clave"] or oc.get("oculto"):
                        continue
                    if any(x["operacion"] == o for x in ops):
                        continue
                    flujo = next((w for w in plantillas if w.get("operacion") == o), None)
                    ops.append({"operacion": o, "nombre": oc.get("nombre", o), "etapa": oc.get("etapa"),
                                "proposito": oc.get("proposito", ""),
                                "estado": oc.get("estado", "cableado" if flujo else "declarado"),
                                "variantes": list((oc.get("variantes") or {}).values()),
                                "flujo": flujo["nombre"] if flujo else None, "url": flujo["url"] if flujo else None,
                                "en_curso": o == en_curso and p == self.pareja_clave})
                if not ops:
                    estado = "proximo"
                elif all(x["estado"] == "certificado" for x in ops):
                    estado = "certificado"
                else:
                    estado = "en_construccion"
                celdas.append({"caso": c["clave"], "nombre": c["nombre"], "proposito": c.get("proposito", ""),
                               "estado": estado, "operaciones": ops, "en_curso": any(x["en_curso"] for x in ops)})
            filas.append({"pareja": p, "nombre": pc.get("nombre", p.title()), "descripcion": pc.get("descripcion", ""),
                          "actual": p == self.pareja_clave, "celdas": celdas})
        return {"casos": cat.get("casos", []), "filas": filas}

    # ── la linea de tiempo: cada cambio, en palabras ────────────────────────
    def _linea_de_tiempo(self, nuevo, op, aap_leido):
        prev = self.prev
        if prev is None:
            self._evento(("La página se reinició y retomó la lectura de %s" if self.recuperado
                          else "Página conectada al ambiente: %s") % ", ".join(s.upper() for s in self.sitios), "info", "sistema")
        if aap_leido and not self.op_base:
            self.op_visto, self.op_base = self._foto_op(op), True
        elif self.op_base:
            self._eventos_op(op)
        if prev is None:
            return
        for s in self.sitios:
            a, b = prev["sitios"][s], nuevo["sitios"][s]
            S = s.upper()
            if not a["leido"] or a["kafka"]["sirviendo"] is None:
                continue   # la primera lectura completa de un sitio es su punto de partida
            if a["alcanzable"] and not b["alcanzable"]:
                self._evento("La API de %s dejó de responder" % S, "critico")
            elif not a["alcanzable"] and b["alcanzable"]:
                self._evento("La API de %s volvió a responder" % S, "ok")
            if a["kafka"]["caida_simulada"] != b["kafka"]["caida_simulada"]:
                self._evento(("Simulación de caída activada en %s" if b["kafka"]["caida_simulada"] else "Simulación de caída retirada en %s") % S,
                             "aviso", "simulacion")
            if a["kafka"]["sirviendo"] and not b["kafka"]["sirviendo"] and b["alcanzable"]:
                self._evento("El Kafka de %s dejó de responder (%d de %d brokers)" % (S, b["kafka"]["listos"], b["kafka"]["total"]), "critico")
            elif not a["kafka"]["sirviendo"] and b["kafka"]["sirviendo"]:
                self._evento("El Kafka de %s volvió a responder (%d brokers)" % (S, b["kafka"]["listos"]), "ok")
            pa, pb = (a.get("proxy") or {}).get("destino"), (b.get("proxy") or {}).get("destino")
            if pa and pb and pa != pb:
                self._evento("El proxy de %s ahora envía al Kafka de %s" % (S, pb.upper()), "cambio")
            ca, cb = a.get("consumidor") or {}, b.get("consumidor") or {}
            if ca and cb and ca.get("replicas") != cb.get("replicas"):
                self._evento(("Las aplicaciones de %s arrancaron" if cb["replicas"] > 0 else "Las aplicaciones de %s se detuvieron") % S, "cambio")
            # Mensajes que entran: se acumulan y se dicen una vez por minuto,
            # para que la carga no entierre los eventos que importan.
            fa = (a.get("datos") or {}).get("fin") if (a.get("datos") or {}).get("vigente") else None
            fb = (b.get("datos") or {}).get("fin") if (b.get("datos") or {}).get("vigente") else None
            if fa is not None and fb is not None and fb > fa:
                self.acumulado[s] += fb - fa
        if time.time() - self.acumulado_desde >= 60:
            partes = []
            for s in self.sitios:
                n = self.acumulado[s]
                if n:
                    partes.append(("entraron %s a %s" if s == nuevo["activo"] else "la réplica copió %s a %s")
                                  % (f"{n:,}", s.upper()))
            if partes:
                texto = "En el último minuto: " + " · ".join(partes)
                self._evento(texto[0].upper() + texto[1:], "dato", "datos")
            self.acumulado = {s: 0 for s in self.sitios}
            self.acumulado_desde = time.time()
        ra = {r["clave"]: r for r in prev["replicaciones"]}
        for r in nuevo["replicaciones"]:
            x = ra.get(r["clave"]) or {}
            if x.get("estado") and r.get("estado") != x.get("estado") and "SIN_DATO" not in (x.get("estado"), r.get("estado")):
                frases = {"ACTIVO": "se encendió", "PASIVO": "quedó en espera", "PAUSADO": "se pausó", "AUSENTE": "dejó de existir"}
                self._evento("La %s %s" % (r["titulo"][0].lower() + r["titulo"][1:], frases.get(r["estado"], r["estado"])), "cambio")
            k = r["clave"]
            if r.get("connect_reinicios", 0) > self.reinicios_visto.get(k, r.get("connect_reinicios", 0)):
                self._evento("El conector de la %s se reinició (%d reinicios)" % (r["titulo"][0].lower() + r["titulo"][1:], r["connect_reinicios"]), "aviso")
            self.reinicios_visto[k] = r.get("connect_reinicios", 0)
        # Durante una operacion el desalineo es de paso: entre mover la replica
        # y mover los proxies. Solo cuenta si queda asi sin operacion en curso.
        en_curso = bool(op and op.get("en_curso"))
        if nuevo.get("desalineados") and not prev.get("desalineados") and not en_curso:
            self._evento("Estado a medias: %s" % "; ".join(nuevo["desalineados"]), "critico")
        elif prev.get("desalineados") and not nuevo.get("desalineados") and not en_curso:
            self._evento("La réplica, los proxies y las aplicaciones vuelven a estar alineados", "ok")
        if prev["activo"] and nuevo["activo"] and prev["activo"] != nuevo["activo"]:
            self._evento("%s es ahora el sitio que atiende la operación" % nuevo["activo"].upper(), "cambio", "rol")
        if prev["contenido"].get("medido") and nuevo["contenido"].get("medido") \
                and prev["contenido"].get("igual") is False and nuevo["contenido"].get("igual"):
            self._evento(nuevo["contenido"]["texto"], "ok", "datos")

    @staticmethod
    def _foto_op(op):
        if not op or not op.get("visible"):
            return {"id": op.get("id") if op else None}
        return {"id": op["id"], "fases": [f["estado"] for f in op["fases"]],
                "acciones": [a["estado"] for a in op["acciones"]], "estado": op["estado"],
                "aprobacion": (op.get("aprobacion") or {}).get("resultado")}

    def _eventos_op(self, op):
        antes, ahora = self.op_visto or {}, self._foto_op(op)
        self.op_visto = ahora
        if not op or not op.get("visible"):
            return
        nombre = op["nombre"] + (" · " + op["variante"] if op.get("variante") else "")
        if ahora["id"] != antes.get("id"):
            self._evento("Se lanzó «%s» desde AAP (flujo %s)" % (op["nombre"], op["id"]), "operacion", "operacion")
            antes = {"fases": [None] * 4, "acciones": [None] * len(ahora.get("acciones", [])), "estado": None, "aprobacion": None}
        fa, fb = antes.get("fases") or [None] * 4, ahora["fases"]
        if fb[0] != fa[0]:
            if fb[0] == "hecho":
                ok = sum(1 for p in op["prechecks"] if p["ok"])
                self._evento("Validación superada: %d controles en verde%s" % (ok, (" · " + nombre) if op.get("variante") else ""), "ok", "operacion")
            elif fb[0] == "fallo":
                self._evento("La validación detuvo la operación: %s" % ((op.get("fallo") or {}).get("msg") or "ver AAP")[:140], "critico", "operacion")
        if ahora.get("aprobacion") != antes.get("aprobacion"):
            ap = op.get("aprobacion") or {}
            if ap.get("resultado") == "pendiente":
                self._evento("Esperando la aprobación de una persona en AAP", "espera", "operacion")
            elif ap.get("resultado") == "aprobada":
                self._evento("Aprobado por %s" % (ap.get("por") or "?"), "ok", "operacion")
            elif ap.get("resultado") in ("denegada", "vencida"):
                self._evento("Aprobación %s%s" % (ap["resultado"], (" por " + ap["por"]) if ap.get("por") else ""), "aviso", "operacion")
        aa = antes.get("acciones") or []
        for i, est in enumerate(ahora["acciones"]):
            previo = aa[i] if i < len(aa) else None
            if est == previo:
                continue
            ac = op["acciones"][i]
            if est == "en_curso":
                self._evento("En curso: %s" % ac["titulo"], "operacion", "operacion")
            elif est == "hecho":
                self._evento("Hecho: %s" % ac["titulo"] + (" · %s" % _esperas(ac["reintentos"]) if ac["reintentos"] else ""), "ok", "operacion")
            elif est == "fallo":
                self._evento("Falló: %s" % ac["titulo"], "critico", "operacion")
        if fb[3] == "hecho" and fa[3] != "hecho":
            self._evento("Estado final verificado contra el contrato", "ok", "operacion")
        if ahora["estado"] != antes.get("estado") and ahora["estado"] in FINALES:
            if ahora["estado"] == "successful":
                self._evento("«%s» terminó bien" % op["nombre"], "ok", "operacion")
            else:
                self._evento("«%s» terminó %s" % (op["nombre"], {"failed": "con falla", "canceled": "cancelada"}.get(ahora["estado"], ahora["estado"])), "critico", "operacion")
