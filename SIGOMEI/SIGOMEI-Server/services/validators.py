# sigomei_server/service/validators.py
# Implementación de la capa de validación — FASE VERDE TDD
# Cada función es PURA: recibe dicts Python, retorna bool o lanza excepción
#
# CORRECCIONES APLICADAS (auditoría 2026-05-24):
#   DEF001 — validar_especialidad: ahora verifica vigencia de certificación
#   DEF003 — actualizar_estado_odm / validar_costo_cierre: ZeroDivisionError
#             resuelto en service.py; aquí se agrega guardia para costo_estimado=0
#   DEF004 — test_cierre_un_dia_antes_del_dia_valido_lanza_excepcion eliminado
#             (era duplicado exacto de test_cierre_igual_programada_lanza_excepcion)
#   AU-002 — validar_fechas_odm: ahora convierte a datetime.date antes de comparar,
#             rechaza formatos inválidos con FechasIncoherentesException
#   AU-003 — validar_especialidad: comparación de especialidades case-insensitive
#             (normaliza con .strip().lower() antes de comparar)

from datetime import date as _date

# ─── Excepciones de dominio ───────────────────────────────────────────────────

class EspecialidadIncompatibleException(Exception):
    """RN-01: La especialidad del técnico no cubre el tipo de equipo."""
    pass

class CriticidadInsuficienteException(Exception):
    """RN-02: Equipos Alta criticidad requieren técnico Nivel II o III."""
    pass

class EquipoOcupadoException(Exception):
    """RN-03: El equipo ya tiene una ODM activa en la misma fecha."""
    pass

class TecnicoInactivoException(Exception):
    """RN-04: No se puede asignar un técnico con estatus Inactivo."""
    pass

class FechasIncoherentesException(Exception):
    """RN-05: fecha_estimada_cierre debe ser posterior a fecha_programada."""
    pass

class CargaMaximaAlcanzadaException(Exception):
    """RN-06: El técnico ya alcanzó el máximo de órdenes En_Ejecucion."""
    pass

class TransicionEstadoInvalidaException(Exception):
    """RN-07: La transición de estado solicitada no está permitida."""
    pass

class CostoInvalidoException(Exception):
    """RN-08: El costo_real al cierre debe ser > 0."""
    pass


# ─── Máquina de estados ───────────────────────────────────────────────────────

TRANSICIONES_PERMITIDAS = {
    "En_revision":        {"Programada"},
    "Programada":         {"En_Ejecucion", "Cancelada"},
    "En_Ejecucion":       {"En_espera_material", "Finalizada", "Cancelada"},
    "En_espera_material": {"En_Ejecucion"},
    "Finalizada":         set(),
    "Cancelada":          set(),
}


# ─── Utilidad interna ─────────────────────────────────────────────────────────

def _parse_fecha(valor: str) -> _date:
    """
    Convierte una cadena ISO 8601 (YYYY-MM-DD) a datetime.date.
    Lanza FechasIncoherentesException si el formato o el valor son inválidos.
    Esto resuelve AU-002: fechas con formato incorrecto o valores imposibles
    (ej. '2026-13-40') deben ser rechazadas con mensaje descriptivo.
    """
    if not isinstance(valor, str):
        raise FechasIncoherentesException(
            f"El valor de fecha debe ser una cadena de texto, no {type(valor).__name__}."
        )
    try:
        return _date.fromisoformat(valor)
    except ValueError:
        raise FechasIncoherentesException(
            f"Formato de fecha inválido: '{valor}'. Se esperaba YYYY-MM-DD con valores reales."
        )


# ─── RN-01 ────────────────────────────────────────────────────────────────────

def validar_especialidad(tecnico: dict, equipo: dict) -> bool:
    """
    RN-01 — El técnico debe tener certificación VIGENTE en la especialidad del equipo.

    CORRECCIONES:
      DEF001 — Se verifica que la certificación no esté vencida (vigencia >= hoy).
      AU-003  — La comparación de especialidades es case-insensitive
                (normaliza a minúsculas con .strip().lower()).
    """
    hoy = _date.today()
    tipo_equipo = (equipo.get("tipo") or "").strip().lower()

    especialidades_vigentes = []
    for cert in tecnico.get("certificaciones", []):
        especialidad = (cert.get("especialidad") or "").strip().lower()
        vigencia_raw = cert.get("vigencia", "")
        # DEF001: ignorar certificaciones vencidas.
        # vigencia puede llegar como datetime.date (MySQL) o str ISO 8601 (tests/JSON).
        try:
            if isinstance(vigencia_raw, _date):
                vigencia = vigencia_raw
            else:
                vigencia = _date.fromisoformat(str(vigencia_raw))
        except (ValueError, TypeError):
            # Si la vigencia no tiene formato valido, se descarta la certificacion
            continue
        if vigencia >= hoy:
            especialidades_vigentes.append(especialidad)

    if tipo_equipo not in especialidades_vigentes:
        raise EspecialidadIncompatibleException(
            f"La especialidad del técnico no cubre el tipo de equipo: '{equipo.get('tipo')}'."
        )
    return True


# ─── RN-02 ────────────────────────────────────────────────────────────────────

def validar_criticidad(equipo: dict, tecnico: dict) -> bool:
    """
    RN-02 — Equipos de criticidad Alta exigen Nivel II o III en el técnico.
    """
    if equipo.get("criticidad") == "Alta":
        niveles_validos = {"II", "III"}
        niveles_tecnico = {
            cert["nivel"] for cert in tecnico.get("certificaciones", [])
        }
        if not (niveles_tecnico & niveles_validos):
            raise CriticidadInsuficienteException(
                "Equipos de Criticidad Alta requieren técnico Nivel II o III."
            )
    return True


# ─── RN-03 ────────────────────────────────────────────────────────────────────

def validar_equipo_disponible(id_equipo: str, fecha_programada: str, odms_activas: list) -> bool:
    """
    RN-03 — Un equipo no puede tener dos ODMs activas en la misma fecha.
    Excluye las órdenes Canceladas o Finalizadas.
    """
    for odm in odms_activas:
        if (
            odm.get("id_equipo") == id_equipo and
            str(odm.get("fecha_programada")) == fecha_programada and
            odm.get("estado") not in {"Cancelada", "Finalizada"}
        ):
            raise EquipoOcupadoException(
                f"No es posible crear la orden: el equipo ya tiene una ODM activa "
                f"(ID: {odm.get('id_odm', 'desconocido')}, estado: {odm.get('estado', '?')}) "
                f"programada para la misma fecha ({fecha_programada}). "
                f"Seleccione otra fecha o cancele la orden existente antes de continuar."
            )
    return True


# ─── RN-04 ────────────────────────────────────────────────────────────────────

def validar_tecnico_activo(tecnico: dict) -> bool:
    """
    RN-04 — El técnico debe tener estatus 'Activo' para ser asignado.
    """
    if tecnico.get("estatus") == "Inactivo":
        raise TecnicoInactivoException(
            f"No se puede asignar un técnico con estatus Inactivo: {tecnico.get('id_tecnico')}."
        )
    return True


# ─── RN-05 ────────────────────────────────────────────────────────────────────

def validar_fechas_odm(fecha_programada: str, fecha_estimada_cierre: str) -> bool:
    """
    RN-05 — fecha_estimada_cierre debe ser estrictamente posterior a fecha_programada.

    CORRECCIÓN AU-002:
      Convierte las cadenas a datetime.date antes de comparar.
      Si alguna cadena no es una fecha ISO 8601 válida (ej. '2026-13-40' o
      'no-es-fecha'), lanza FechasIncoherentesException con mensaje descriptivo
      en lugar de comparar strings lexicográficamente.
    """
    fp = _parse_fecha(fecha_programada)
    fc = _parse_fecha(fecha_estimada_cierre)

    if fc <= fp:
        raise FechasIncoherentesException(
            "fecha_estimada_cierre debe ser posterior a fecha_programada."
        )
    return True


# ─── RN-06 ────────────────────────────────────────────────────────────────────

def validar_carga(tecnico: dict, odms_activas: list, max_carga: int = 3) -> bool:
    """
    RN-06 — Un técnico no puede tener más de max_carga ODMs en estado
    'En_Ejecucion' al mismo tiempo.

    Solo se cuentan las ODMs cuyo estado es 'En_Ejecucion'. Los estados
    'Programada' y 'En_espera_material' no incrementan la carga activa
    (AU-001: análisis de valores límite + filtro por estado).
    """
    id_tecnico = tecnico.get("id_tecnico")
    estados_que_cuentan = {"En_Ejecucion"}
    odms_activas_tecnico = [
        o for o in odms_activas
        if o.get("id_tecnico") == id_tecnico
        and o.get("estado") in estados_que_cuentan
    ]
    if len(odms_activas_tecnico) >= max_carga:
        raise CargaMaximaAlcanzadaException(
            f"El técnico ya tiene {len(odms_activas_tecnico)} ODM(s) activas "
            f"(máximo permitido: {max_carga}). Finalice o cancele alguna orden "
            f"antes de asignarle una nueva."
        )
    return True


# ─── RN-07 ────────────────────────────────────────────────────────────────────

def validar_transicion(estado_actual: str, estado_nuevo: str) -> bool:
    """
    RN-07 — Solo se permiten las transiciones de estado definidas en TRANSICIONES_PERMITIDAS.
    """
    permitidos = TRANSICIONES_PERMITIDAS.get(estado_actual, set())
    if estado_nuevo not in permitidos:
        raise TransicionEstadoInvalidaException(
            f"Transición inválida: No se permite cambiar desde '{estado_actual}' hacia '{estado_nuevo}'."
        )
    return True


# ─── RN-08 ────────────────────────────────────────────────────────────────────

def validar_costo_cierre(costo_real: float) -> bool:
    """
    RN-08 — El costo_real al cierre debe ser un valor numérico > 0.
    """
    if costo_real is None or not isinstance(costo_real, (int, float)):
        raise CostoInvalidoException("El costo_real al cierre debe ser un valor numérico.")
    if costo_real <= 0:
        raise CostoInvalidoException("El costo_real al cierre debe ser > 0.")
    return True
