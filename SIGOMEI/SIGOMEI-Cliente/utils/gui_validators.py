# utils/gui_validators.py
# Validaciones ligeras del lado del cliente (RNF-06).
# Solo verifican formato/tipo antes de enviar al servidor.
# Las reglas de negocio (RN-01..RN-08) SIEMPRE se validan en el servidor.

import re
from datetime import date


def validar_correo(correo: str) -> str | None:
    """Retorna mensaje de error o None si es válido."""
    patron = r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$"
    if not correo or not re.match(patron, correo.strip()):
        return "Correo electrónico inválido."
    return None


def validar_password(password: str) -> str | None:
    """RF-30: mínimo 8 caracteres, 1 mayúscula, 1 número, 1 carácter especial."""
    if len(password) < 8:
        return "La contraseña debe tener mínimo 8 caracteres."
    if not re.search(r"[A-Z]", password):
        return "La contraseña debe contener al menos una mayúscula."
    if not re.search(r"\d", password):
        return "La contraseña debe contener al menos un número."
    if not re.search(r"[^a-zA-Z0-9]", password):
        return "La contraseña debe contener al menos un carácter especial."
    return None


def validar_rfc(rfc: str) -> str | None:
    patron = r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$"
    if not rfc or not re.match(patron, rfc.strip().upper()):
        return "RFC inválido (ej. MERC850101ABC)."
    return None


def validar_telefono(tel: str) -> str | None:
    if not tel or not re.match(r"^\d{10}$", tel.strip()):
        return "Teléfono inválido (10 dígitos)."
    return None


def validar_fecha(fecha_str: str) -> str | None:
    """Verifica formato YYYY-MM-DD."""
    try:
        date.fromisoformat(fecha_str.strip())
        return None
    except ValueError:
        return "Fecha inválida. Use el formato YYYY-MM-DD."


def validar_fechas_odm(fecha_prog: str, fecha_cierre: str) -> str | None:
    """Verificación básica cliente: cierre > programada."""
    err_p = validar_fecha(fecha_prog)
    if err_p:
        return f"Fecha programada: {err_p}"
    err_c = validar_fecha(fecha_cierre)
    if err_c:
        return f"Fecha estimada de cierre: {err_c}"
    if fecha_cierre <= fecha_prog:
        return "La fecha estimada de cierre debe ser posterior a la fecha programada."
    return None


def validar_decimal_positivo(valor: str) -> str | None:
    try:
        v = float(valor)
        if v <= 0:
            return "El valor debe ser mayor a 0."
        return None
    except (ValueError, TypeError):
        return "El valor debe ser numérico."


def validar_no_vacio(valor: str, nombre_campo: str = "Campo") -> str | None:
    if not valor or not valor.strip():
        return f"{nombre_campo} es obligatorio."
    return None


def recopilar_errores(**campos) -> list[str]:
    """Recibe {nombre: resultado_validacion} y retorna lista de errores no nulos."""
    return [msg for msg in campos.values() if msg is not None]
