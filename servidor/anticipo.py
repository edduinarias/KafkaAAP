"""Que va a decidir la automatizacion, con el estado de ahora.

Las mismas reglas que kafka_decide, sobre el mismo contrato: que transicion
elige, si el destino ya atiende, si es una reanudacion, si el punto de partida
se cumple y que controles previos fallarian. Es una anticipacion: la decision
real es la de AAP, y la consola compara las dos cuando se lanza el flujo.
"""
import time

from guion import cumple

# Cada control previo del contrato, evaluado con lo que ve la pagina. Devuelve
# None si pasa, o el motivo si fallaria.
def _controles(nombre, o, d, v):
    sa, sb = v["sitios"][o], v["sitios"][d]
    da, db = sa.get("datos") or {}, sb.get("datos") or {}
    O, D = o.upper(), d.upper()
    if nombre == "sitio_b_alcanzable":
        return None if sb["alcanzable"] else "%s no responde" % D
    if nombre in ("sitio_b_kafka_ready", "sitio_b_sirviendo"):
        return None if sb["kafka"]["sirviendo"] else "el Kafka de %s no responde: primero hay que reponerlo" % D
    if nombre == "sitio_a_sirviendo":
        return None if sa["kafka"]["sirviendo"] else "el Kafka de %s no responde" % O
    if nombre == "sitio_a_no_sirve":
        return None if not sa["kafka"]["sirviendo"] else "el Kafka de %s responde: no es una contingencia" % O
    if nombre in ("sitio_b_sin_under_replicated", "sitio_a_sin_under_replicated"):
        x, X = (db, D) if nombre.startswith("sitio_b") else (da, O)
        return None if not x.get("sub_replicadas") else "%s tiene particiones sub-replicadas" % X
    if nombre == "replicacion_al_dia":
        if not (da.get("vigente") and db.get("vigente")):
            return "no se puede medir el contenido de los dos sitios"
        falta = (da.get("retenidos") or 0) - (db.get("retenidos") or 0)
        return None if falta <= 0 else "a %s le faltan %d mensajes de %s" % (D, falta, O)
    if nombre == "consumidores_al_dia":
        if not (da.get("vigente") and db.get("vigente")):
            return "no se puede medir la posición de los consumidores"
        if (da.get("atraso") or 0) != (db.get("atraso") or 0):
            return ("la posición de los consumidores no llegó a %s (%s sin consumir en %s, %s en %s): "
                    "reprocesarían mensajes" % (D, db.get("atraso"), D, da.get("atraso"), O))
        return None
    if nombre == "proxy_destino_b_resuelve":
        return None if (sa.get("proxy") or {}).get("resuelto") is not False else "el proxy de %s no resuelve su destino" % O
    return None


def _activo_por_replica(v):
    enc = [r for r in v["replicaciones"] if r.get("estado") in ("ACTIVO", "PAUSADO")]
    return enc[0]["origen"] if len(enc) == 1 else None


def _estado_replica(v, clave):
    e = next((r.get("estado") for r in v["replicaciones"] if r["clave"] == clave), None)
    return "ACTIVO" if e == "PAUSADO" else e   # pausada sigue con replicas: 1


def anticipar(operacion, direccion, v, contrato, pareja_clave, pareja, describir):
    """describir(accion, plan) -> (titulo, tecnico), el mismo del modelo."""
    o, d = direccion.split("_a_")
    O, D = o.upper(), d.upper()
    sit = v["sitios"]
    plan = {"sitio_a": o, "sitio_b": d, "mm_hacia_b": "%s_%s" % (o, d), "mm_hacia_a": "%s_%s" % (d, o)}
    out = {"operacion": operacion, "direccion": direccion, "origen": o, "destino": d, "avisos": [], "fallas": []}

    cands = [t for t in contrato.get("transiciones", [])
             if t["operacion"] == operacion and pareja_clave in t.get("aplica_a", [])]
    sirve = bool(sit[o]["kafka"]["sirviendo"])
    con = [t for t in cands if "sitio_a_sirviendo" in (t.get("desde") or {}) and t["desde"]["sitio_a_sirviendo"] == sirve]
    sin = [t for t in cands if "sitio_a_sirviendo" not in (t.get("desde") or {})]
    if not cands:
        out.update(salida="no_construida", motivo="el contrato todavía no declara %s para la pareja %s" % (operacion, pareja_clave))
        return out
    t = (con or sin or [None])[0]
    if not t:
        out.update(salida="no_aplica", motivo="el contrato no declara %s para este estado" % operacion)
        return out
    out["transicion"] = t["id"]

    # Cada accion del plan, aplicada o no, con el estado de ahora.
    def aplicada(a):
        rol = a.get("rol")
        if rol == "mm2_state":
            k = plan["mm_hacia_b"] if a.get("sentido") == "hacia_b" else plan["mm_hacia_a"]
            return _estado_replica(v, k) == a.get("estado")
        if rol == "proxy_target":
            s = o if a.get("sitio") == "sitio_a" else d
            dst = o if a.get("destino") == "sitio_a" else d
            return ((sit[s].get("proxy") or {}).get("destino")) == dst
        if rol == "app_scale":
            s = o if a.get("sitio") == "sitio_a" else d
            apps = (pareja.get("aplicaciones") or {}).get(s) or []
            cons = sit[s].get("consumidor") or {}
            return bool(apps) and cons.get("replicas") == int(apps[0]["replicas"][a.get("estado")])
        return None
    estados = [aplicada(a) for a in t.get("acciones", [])]
    out["acciones"] = [{"titulo": describir(a, plan)[0], "aplicada": e} for a, e in zip(t.get("acciones", []), estados)]

    desal = v.get("desalineados") or []
    activo = _activo_por_replica(v)
    reanudar = bool(desal) and True in estados and False in estados
    nada = (not reanudar and t.get("objetivo_cumplido_si") == "destino_es_el_activo" and d == activo)

    if nada:
        coherente = not desal and all(x["alcanzable"] and x["kafka"]["sirviendo"] for x in sit.values())
        if not coherente:
            out.update(salida="detiene", motivo="%s ya atiende, pero el estado no es coherente: no lo da por bueno" % D)
            return out
        out.update(salida="nada", motivo="%s ya atiende la operación" % D)
        return out

    if reanudar:
        da, db = sit[o].get("datos") or {}, sit[d].get("datos") or {}
        if da.get("vigente") and db.get("vigente"):
            falta = (da.get("retenidos") or 0) - (db.get("retenidos") or 0)
            if falta > 0:
                out.update(salida="detiene", motivo="completar dejaría %d mensajes varados en %s: la dirección inversa (%s_a_%s) los conserva"
                           % (falta, O, d, o))
                return out
        elif not (t.get("garantia") or {}).get("reducida"):
            out.update(salida="detiene", motivo="no se puede medir el contenido de los dos sitios para reanudar")
            return out
    else:
        desde = t.get("desde") or {}
        problemas = []
        if desde.get("activo") == "sitio_a" and activo != o:
            problemas.append("hoy atiende %s, no %s" % ((activo or "?").upper(), O))
        mms = desde.get("mirrormakers") or {}
        for sentido, k in (("hacia_b", plan["mm_hacia_b"]), ("hacia_a", plan["mm_hacia_a"])):
            if sentido in mms and _estado_replica(v, k) != mms[sentido]:
                ko, kd = k.split("_")
                problemas.append("la réplica %s → %s debería estar %s" % (ko.upper(), kd.upper(), mms[sentido]))
        if problemas:
            out.update(salida="no_aplica", motivo="; ".join(problemas))
            return out

    # Controles previos y condiciones de ejecucion que se pueden anticipar.
    for nombre in t.get("prechecks", []):
        m = _controles(nombre, o, d, v)
        if m:
            out["fallas"].append(m)
    temenos = (v.get("temenos") or {}).get("continuo")
    if any(a.get("rol") == "resync_control" and a.get("accion") == "exigir_quietud" for a in t.get("acciones", [])) and temenos:
        out["fallas"].append("la carga no está detenida: Temenos sigue escribiendo")
    if "replicacion_al_dia" in t.get("prechecks", []) and temenos:
        out["avisos"].append("con Temenos escribiendo, la validación probablemente la frene (N20): conviene detenerlo")
    if out["fallas"]:
        out.update(salida="detiene", motivo=out["fallas"][0])
        return out
    out.update(salida="reanudacion" if reanudar else t["id"],
               motivo=("faltan %d de %d acciones" % (estados.count(False), len([e for e in estados if e is not None])))
               if reanudar else (t.get("descripcion") or "").strip())
    return out


def resultado_real(op):
    """La salida que de verdad tuvo una operacion de AAP, en los mismos terminos."""
    if not op or not op.get("visible"):
        return None
    if op["fases"][0]["estado"] == "fallo":
        return "detiene"
    if op.get("nada_que_hacer"):
        return "nada"
    if op.get("reanudacion"):
        return "reanudacion"
    return op.get("transicion")
