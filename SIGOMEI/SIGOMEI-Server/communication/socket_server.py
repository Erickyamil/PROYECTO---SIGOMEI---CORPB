# communication/socket_server.py
# Servidor de sockets TCP/JSON de SIGOMEI.
# Usa logging en lugar de print(); las excepciones internas se registran
# con logger.exception() (que incluye el traceback en el log de disco)
# pero nunca envían trazas crudas al cliente.

import json
import logging
import socket
import threading
from datetime import date, datetime
from decimal import Decimal

from services.service import ServiceLayer

logger = logging.getLogger("sigomei.server")

_ACTION_ALIASES = {
    "CREAR_ODM":              "crear_odm",
    "ACTUALIZAR_ESTADO_ODM":  "actualizar_estado_odm",
    "OBTENER_ODM":            "obtener_odm",
    "LISTAR_ODMS":            "listar_odms",
    "FILTRAR_ODMS":           "filtrar_odms",
    "REASIGNAR_TECNICO_ODM":  "reasignar_tecnico_odm",
    "AGREGAR_NOTA_ODM":       "agregar_nota_odm",
    "RESUMEN_COSTOS":         "resumen_costos",
    "CREAR_TECNICO":          "crear_tecnico",
    "ACTUALIZAR_TECNICO":     "actualizar_tecnico",
    "CAMBIAR_ESTATUS_TECNICO":"cambiar_estatus_tecnico",
    "OBTENER_TECNICO":        "obtener_tecnico",
    "BUSCAR_TECNICOS":        "buscar_tecnicos",
    "CARGA_TECNICO":          "carga_tecnico",
    "CREAR_EQUIPO":           "crear_equipo",
    "ACTUALIZAR_EQUIPO":      "actualizar_equipo",
    "BAJA_EQUIPO":            "baja_equipo",
    "ELIMINAR_EQUIPO":        "eliminar_equipo",
    "OBTENER_EQUIPO":         "obtener_equipo",
    "LISTAR_EQUIPOS":         "listar_equipos",
    "HISTORIAL_EQUIPO":       "historial_equipo",
    "REPORTE_DESEMPENO":      "reporte_desempeno",
    "REPORTE_EQUIPOS_CRITICOS":"reporte_equipos_criticos",
    "EXPORTAR_CSV":           "exportar_csv",
}


class SIGOMEISocketServer:
    def __init__(self, host: str, port: int, repository):
        self.host = host
        self.port = port
        self.service = ServiceLayer(repository)
        self._shutdown = threading.Event()
        self._sessions: dict = {}
        self._sessions_lock = threading.Lock()

    def iniciar(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen()
            server.settimeout(1.0)
            logger.info("SIGOMEI socket server escuchando en %s:%s", self.host, self.port)
            logger.info("Protocolo: JSON por linea. Accion 'ping' para probar conectividad.")
            logger.info("Pulsa Ctrl+C para detener.")

            while not self._shutdown.is_set():
                try:
                    client, address = server.accept()
                except socket.timeout:
                    continue
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client, address),
                    daemon=True,
                    name=f"client-{address[0]}:{address[1]}",
                )
                thread.start()

    def _handle_client(self, client: socket.socket, address) -> None:
        addr_str = f"{address[0]}:{address[1]}"
        logger.info("Cliente conectado: %s", addr_str)
        with client:
            buffer = b""
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    response = self._dispatch_line(line, addr_str)
                    encoded = json.dumps(response, default=_json_default) + "\n"
                    client.sendall(encoded.encode("utf-8"))
        logger.info("Cliente desconectado: %s", addr_str)

    def _dispatch_line(self, line: bytes, addr_str: str = "") -> dict:
        try:
            request = json.loads(line.decode("utf-8"))
            return self._dispatch(request)
        except json.JSONDecodeError as exc:
            logger.warning("JSON invalido desde %s: %s", addr_str, exc)
            return {"status": "ERR_BAD_REQUEST",
                    "message": f"JSON invalido: {exc}", "data": None}
        except KeyError as exc:
            logger.warning("Campo requerido faltante desde %s: %s", addr_str, exc)
            return {"status": "ERR_BAD_REQUEST",
                    "message": f"Campo requerido faltante: {exc}", "data": None}
        except Exception as exc:
            # logger.exception registra el traceback completo en el log de disco
            # pero el cliente solo recibe un mensaje genérico (sin traza cruda).
            logger.exception("Error interno procesando peticion de %s: %s", addr_str, exc)
            return {"status": "ERR_INTERNAL",
                    "message": "Error interno del servidor. Consulte la bitacora.",
                    "data": None}

    def _dispatch(self, request: dict) -> dict:
        action = request.get("action") or request.get("cmd")
        action = _ACTION_ALIASES.get(action, action)
        payload = request.get("payload") or {}
        id_usuario = self._id_usuario_de_request(request, payload)

        if action == "ping":
            return {"status": "OK", "message": "pong", "data": None}
        if action == "LOGIN":
            return self._login(payload)
        if action == "LOGOUT":
            return self._logout(request.get("token"))

        if self._requiere_auth(action) and not id_usuario:
            return {"status": "ERR_AUTH",
                    "message": "Sesion invalida o expirada.", "data": None}

        handlers = {
            "crear_odm":             lambda: self.service.crear_odm(payload, id_usuario),
            "actualizar_estado_odm": lambda: self.service.actualizar_estado_odm(
                payload["id_odm"], payload["nuevo_estado"],
                id_usuario, payload.get("costo_real")),
            "obtener_odm":           lambda: self.service.obtener_odm(payload["id_odm"]),
            "listar_odms":           self.service.listar_odms,
            "filtrar_odms":          lambda: self.service.filtrar_odms(
                payload.get("fecha_inicio"), payload.get("fecha_fin"), payload.get("estado")),
            "reasignar_tecnico_odm": lambda: self.service.reasignar_tecnico_odm(
                payload["id_odm"], payload["id_tecnico_nuevo"], id_usuario),
            "agregar_nota_odm":      lambda: self.service.agregar_nota_odm(
                payload["id_odm"], payload["nota_adicional"], id_usuario),
            "resumen_costos":        lambda: self.service.resumen_costos(payload["id_odm"]),
            "crear_tecnico":         lambda: self.service.crear_tecnico(payload),
            "actualizar_tecnico":    lambda: self.service.actualizar_tecnico(payload),
            "cambiar_estatus_tecnico": lambda: self.service.cambiar_estatus_tecnico(
                payload["id_tecnico"], payload["nuevo_estatus"]),
            "obtener_tecnico":       lambda: self.service.obtener_tecnico(payload["id_tecnico"]),
            "buscar_tecnicos":       lambda: self.service.buscar_tecnicos(payload),
            "carga_tecnico":         lambda: self.service.carga_tecnico(payload["id_tecnico"]),
            "crear_equipo":          lambda: self.service.crear_equipo(payload),
            "actualizar_equipo":     lambda: self.service.actualizar_equipo(payload),
            "baja_equipo":           lambda: self.service.baja_equipo(payload["id_equipo"]),
            "eliminar_equipo":       lambda: self.service.eliminar_equipo(payload["id_equipo"]),
            "obtener_equipo":        lambda: self.service.obtener_equipo(payload["id_equipo"]),
            "listar_equipos":        lambda: self.service.listar_equipos(payload),
            "historial_equipo":      lambda: self.service.historial_equipo(payload["id_equipo"]),
            "reporte_desempeno":     lambda: self.service.reporte_desempeno(
                payload["id_tecnico"], payload["fecha_inicio"], payload["fecha_fin"]),
            "reporte_equipos_criticos": self.service.reporte_equipos_criticos,
            "exportar_csv":          lambda: self.service.exportar_csv(
                payload["tipo_reporte"], payload.get("parametros") or {}),
        }

        handler = handlers.get(action)
        if not handler:
            logger.warning("Accion no soportada: %s", action)
            return {"status": "ERR_BAD_REQUEST",
                    "message": f"Accion no soportada: {action}", "data": None}
        return handler()

    # ── Sesiones ──────────────────────────────────────────────────────────────

    def _login(self, payload: dict) -> dict:
        response = self.service.verificar_credenciales(
            payload["correo"], payload["password_hash"])
        if response.get("status") == "OK" and response.get("data"):
            data = response["data"]
            with self._sessions_lock:
                self._sessions[data["token"]] = {
                    "id_usuario": data["id_usuario"],
                    "rol": data["rol"],
                }
            logger.info("Login exitoso: usuario=%s rol=%s", data["id_usuario"], data["rol"])
        else:
            logger.warning("Intento de login fallido para correo='%s'",
                           payload.get("correo", "?"))
        return response

    def _logout(self, token: str | None) -> dict:
        if token:
            with self._sessions_lock:
                session = self._sessions.pop(token, None)
            if session:
                logger.info("Logout: usuario=%s", session.get("id_usuario"))
        return {"status": "OK", "message": "Sesion cerrada.", "data": None}

    def _id_usuario_de_request(self, request: dict, payload: dict) -> str | None:
        token = request.get("token")
        if token:
            with self._sessions_lock:
                session = self._sessions.get(token)
            if session:
                return session["id_usuario"]
        return request.get("id_usuario") or payload.get("id_usuario")

    def _requiere_auth(self, action: str) -> bool:
        return action not in {"ping", "LOGIN"}


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
