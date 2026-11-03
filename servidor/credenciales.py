"""Identidad y vencimiento de los tokens de cada sitio. Nunca su valor."""
import base64
import datetime as dt
import hashlib
import json

from fuentes import describir_error


def _vence_jwt(tok):
    """Un token de cuenta de servicio es un JWT: el vencimiento esta en su
    carga, que se lee sin verificar la firma (solo para mostrarlo)."""
    try:
        carga = tok.split(".")[1] + "=" * (-len(tok.split(".")[1]) % 4)
        exp = json.loads(base64.urlsafe_b64decode(carga)).get("exp")
        return dt.datetime.fromtimestamp(exp, dt.timezone.utc).isoformat() if exp else None
    except Exception:
        return None


def credencial_sitio(nombre, api, token, http):
    out = {"nombre": nombre.upper(), "archivo": token.ruta.split("/")[-1], "cargado": token.existe(), "valido": False}
    if not out["cargado"]:
        out["error"] = "no hay token en el archivo"
        return out
    try:
        tok = token.valor()
        u = http.json(api.rstrip("/") + "/apis/user.openshift.io/v1/users/~", tok, timeout=6)
        out.update({"valido": True, "identidad": (u.get("metadata") or {}).get("name")})
        if tok.startswith("sha256~"):
            # OpenShift guarda el token por el hash de su valor: sha256~ +
            # base64url(sha256(valor sin el prefijo)).
            obj = "sha256~" + base64.urlsafe_b64encode(
                hashlib.sha256(tok[len("sha256~"):].encode()).digest()).decode().rstrip("=")
            d = http.json(api.rstrip("/") + "/apis/oauth.openshift.io/v1/useroauthaccesstokens/" + obj, tok, timeout=6)
            creado = dt.datetime.fromisoformat(d["metadata"]["creationTimestamp"].replace("Z", "+00:00"))
            if d.get("expiresIn"):
                out["vence"] = (creado + dt.timedelta(seconds=d["expiresIn"])).isoformat()
        else:
            out["vence"] = _vence_jwt(tok)
    except Exception as e:
        out["error"] = describir_error(e)
    return out
