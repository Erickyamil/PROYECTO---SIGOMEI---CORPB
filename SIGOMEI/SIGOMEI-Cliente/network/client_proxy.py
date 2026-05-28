# network/client_proxy.py
# Capa de comunicación del cliente — abstrae los sockets TCP/JSON
# El resto de la GUI NUNCA usa sockets directamente; solo llama a este proxy.

import socket
import json
import threading
import time

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9000
TIMEOUT_SEGUNDOS = 10
MAX_REINTENTOS = 3
PAUSA_REINTENTO = 5   # segundos entre intentos


class ClientProxy:
    """
    Único punto de acceso a la red en el cliente.
    Gestiona conexión, serialización JSON, reconexión automática (RF-51)
    y el token de sesión activo.
    """

    def __init__(self, host: str = SERVER_HOST, port: int = SERVER_PORT):
        self.host = host
        self.port = port
        self.token: str | None = None
        self._lock = threading.Lock()      # Un socket no es thread-safe
        self._sock: socket.socket | None = None
        self._conectado = False

    # ──────────────────────────────────────────────────────────────────────────
    # Conexión / reconexión
    # ──────────────────────────────────────────────────────────────────────────

    def conectar(self) -> bool:
        """Establece la conexión TCP. Retorna True si tuvo éxito."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(TIMEOUT_SEGUNDOS)
            self._sock.connect((self.host, self.port))
            self._conectado = True
            return True
        except (socket.error, OSError):
            self._conectado = False
            return False

    def desconectar(self):
        """Cierra la conexión limpiamente."""
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._conectado = False
        self.token = None

    def _reconectar(self) -> bool:
        """RF-51: Reintenta hasta MAX_REINTENTOS veces con pausa entre intentos."""
        for intento in range(1, MAX_REINTENTOS + 1):
            print(f"[Proxy] Reintento {intento}/{MAX_REINTENTOS}...")
            self.desconectar()
            if self.conectar():
                print("[Proxy] Reconexión exitosa.")
                return True
            time.sleep(PAUSA_REINTENTO)
        return False

    @property
    def conectado(self) -> bool:
        return self._conectado

    # ──────────────────────────────────────────────────────────────────────────
    # Envío / recepción de mensajes (protocolo del Documento de Diseño E2)
    # ──────────────────────────────────────────────────────────────────────────

    def _enviar_peticion(self, cmd: str, payload: dict) -> dict:
        """
        Serializa la petición como JSON + \\n, la envía y lee la respuesta.
        Intenta reconectarse automáticamente si la conexión se perdió.
        """
        mensaje = {
            "cmd": cmd,
            "token": self.token,
            "payload": payload
        }
        datos = (json.dumps(mensaje, ensure_ascii=False) + "\n").encode("utf-8")

        with self._lock:
            for intento in range(MAX_REINTENTOS + 1):
                try:
                    if not self._conectado:
                        if not self.conectar():
                            continue
                    self._sock.sendall(datos)
                    respuesta_raw = self._recibir_respuesta()
                    return json.loads(respuesta_raw)
                except (socket.timeout,):
                    return {"status": "ERR_TIMEOUT",
                            "message": "Sin respuesta del servidor en 10 s. Verifique la red.",
                            "data": None}
                except (socket.error, OSError, BrokenPipeError):
                    self._conectado = False
                    if intento < MAX_REINTENTOS:
                        time.sleep(PAUSA_REINTENTO)
                        self.conectar()
                    else:
                        return {"status": "ERR_TIMEOUT",
                                "message": "Conexión con el servidor perdida. Verifique la red.",
                                "data": None}

    def _recibir_respuesta(self) -> str:
        """Lee bytes del socket hasta encontrar el delimitador \\n."""
        buffer = b""
        while True:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise socket.error("Conexión cerrada por el servidor.")
            buffer += chunk
            if b"\n" in buffer:
                linea, _ = buffer.split(b"\n", 1)
                return linea.decode("utf-8")

    # ──────────────────────────────────────────────────────────────────────────
    # API pública — un método por comando del protocolo (Sección 3.2 del E2)
    # ──────────────────────────────────────────────────────────────────────────

    def login(self, correo: str, password_hash: str) -> dict:
        resp = self._enviar_peticion("LOGIN", {
            "correo": correo,
            "password_hash": password_hash
        })
        if resp.get("status") == "OK" and resp.get("data"):
            self.token = resp["data"].get("token")
        return resp

    def logout(self) -> dict:
        resp = self._enviar_peticion("LOGOUT", {})
        self.token = None
        return resp

    # ── Equipos ──────────────────────────────────────────────────────────────

    def crear_equipo(self, payload: dict) -> dict:
        return self._enviar_peticion("CREAR_EQUIPO", payload)

    def actualizar_equipo(self, payload: dict) -> dict:
        return self._enviar_peticion("ACTUALIZAR_EQUIPO", payload)

    def baja_equipo(self, id_equipo: str) -> dict:
        return self._enviar_peticion("BAJA_EQUIPO", {"id_equipo": id_equipo})

    def eliminar_equipo(self, id_equipo: str) -> dict:
        return self._enviar_peticion("ELIMINAR_EQUIPO", {"id_equipo": id_equipo})

    def listar_equipos(self, filtros: dict = None) -> dict:
        return self._enviar_peticion("LISTAR_EQUIPOS", filtros or {})

    def obtener_equipo(self, id_equipo: str) -> dict:
        return self._enviar_peticion("OBTENER_EQUIPO", {"id_equipo": id_equipo})

    def historial_equipo(self, id_equipo: str) -> dict:
        return self._enviar_peticion("HISTORIAL_EQUIPO", {"id_equipo": id_equipo})

    # ── Técnicos ─────────────────────────────────────────────────────────────

    def crear_tecnico(self, payload: dict) -> dict:
        return self._enviar_peticion("CREAR_TECNICO", payload)

    def actualizar_tecnico(self, payload: dict) -> dict:
        return self._enviar_peticion("ACTUALIZAR_TECNICO", payload)

    def cambiar_estatus_tecnico(self, id_tecnico: str, nuevo_estatus: str) -> dict:
        return self._enviar_peticion("CAMBIAR_ESTATUS_TECNICO", {
            "id_tecnico": id_tecnico,
            "nuevo_estatus": nuevo_estatus
        })

    def buscar_tecnicos(self, especialidad: str = None, nivel_cert: str = None) -> dict:
        payload = {}
        if especialidad:
            payload["especialidad"] = especialidad
        if nivel_cert:
            payload["nivel_cert"] = nivel_cert
        return self._enviar_peticion("BUSCAR_TECNICOS", payload)

    def obtener_tecnico(self, id_tecnico: str) -> dict:
        return self._enviar_peticion("OBTENER_TECNICO", {"id_tecnico": id_tecnico})

    def carga_tecnico(self, id_tecnico: str) -> dict:
        return self._enviar_peticion("CARGA_TECNICO", {"id_tecnico": id_tecnico})

    # ── Órdenes de Mantenimiento ──────────────────────────────────────────────

    def obtener_odm(self, id_odm: str) -> dict:
        return self._enviar_peticion("OBTENER_ODM", {"id_odm": id_odm})

    def crear_odm(self, payload: dict) -> dict:
        return self._enviar_peticion("CREAR_ODM", payload)

    def actualizar_estado_odm(self, payload: dict) -> dict:
        return self._enviar_peticion("ACTUALIZAR_ESTADO_ODM", payload)

    def reasignar_tecnico_odm(self, id_odm: str, id_tecnico_nuevo: str) -> dict:
        return self._enviar_peticion("REASIGNAR_TECNICO_ODM", {
            "id_odm": id_odm,
            "id_tecnico_nuevo": id_tecnico_nuevo
        })

    def agregar_nota_odm(self, id_odm: str, nota_adicional: str) -> dict:
        return self._enviar_peticion("AGREGAR_NOTA_ODM", {
            "id_odm": id_odm,
            "nota_adicional": nota_adicional
        })

    def filtrar_odms(self, fecha_inicio: str, fecha_fin: str, estado: str = None) -> dict:
        payload = {"fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin}
        if estado:
            payload["estado"] = estado
        return self._enviar_peticion("FILTRAR_ODMS", payload)

    # ── Reportes ──────────────────────────────────────────────────────────────

    def resumen_costos(self, id_odm: str) -> dict:
        return self._enviar_peticion("RESUMEN_COSTOS", {"id_odm": id_odm})

    def reporte_desempeno(self, id_tecnico: str, fecha_inicio: str, fecha_fin: str) -> dict:
        return self._enviar_peticion("REPORTE_DESEMPENO", {
            "id_tecnico": id_tecnico,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin
        })

    def reporte_equipos_criticos(self) -> dict:
        return self._enviar_peticion("REPORTE_EQUIPOS_CRITICOS", {})

    def exportar_csv(self, tipo_reporte: str, parametros: dict = None) -> dict:
        return self._enviar_peticion("EXPORTAR_CSV", {
            "tipo_reporte": tipo_reporte,
            "parametros": parametros or {}
        })
