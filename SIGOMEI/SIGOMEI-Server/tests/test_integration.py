# tests/test_integration.py
# Suite de Pruebas de Integración para SIGOMEI
#
# Estrategia: se levanta el SIGOMEISocketServer en un hilo de fondo conectado
# a la BD MySQL de prueba local. Cada prueba abre una conexión TCP real,
# envía JSON por línea y verifica la respuesta completa contra la BD.
#
# Capas ejercidas:  socket → _dispatch_line → _dispatch → ServiceLayer → MySQLRepository → BD
#
# Requisito previo:
#   1. Tener MySQL corriendo en localhost.
#   2. Crear la BD de prueba:   CREATE DATABASE sigomei_test;
#   3. Aplicar el esquema:      mysql -u root -p sigomei_test < db/sigomei_db.sql
#   4. Ajustar DB_TEST_CONFIG abajo con tus credenciales.
#
# Ejecución:
#   cd SIGOMEI-Server
#   python -m pytest tests/test_integration.py -v

import json
import socket
import threading
import time
import unittest
import uuid

import bcrypt
import mysql.connector

from communication.socket_server import SIGOMEISocketServer
from repository.repository import MySQLRepository

# ─── Configuración de la BD de prueba ────────────────────────────────────────
# ¡IMPORTANTE! Usa una base de datos dedicada para pruebas, NUNCA la de producción.

DB_TEST_CONFIG = {
    "host":     "127.0.0.1",
    "user":     "root",
    "password": "yamil2014",   # <-- cambia esto
    "database": "sigomei_test",  # <-- BD exclusiva para pruebas
    "port":     3306,
}

# ─── Helpers de bajo nivel ───────────────────────────────────────────────────

def _enviar_y_recibir(host: str, port: int, request: dict) -> dict:
    """Abre una conexión TCP, envía un mensaje JSON-line y devuelve la respuesta."""
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
        datos = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            datos += chunk
            if b"\n" in datos:
                break
    linea = datos.split(b"\n")[0]
    return json.loads(linea.decode("utf-8"))


def _hacer_login(host: str, port: int, correo: str, password_hash_sha256: str) -> str:
    """Realiza LOGIN y devuelve el token de sesión."""
    resp = _enviar_y_recibir(host, port, {
        "action": "LOGIN",
        "payload": {"correo": correo, "password_hash": password_hash_sha256},
    })
    assert resp["status"] == "OK", f"Login fallido: {resp}"
    return resp["data"]["token"]


# ─── Clase base con fixture de BD y servidor ─────────────────────────────────

class IntegrationTestBase(unittest.TestCase):
    """
    Levanta el servidor con BD real en setUp y lo detiene en tearDown.
    Limpia e inserta datos semilla antes de cada test para garantizar aislamiento.
    """

    HOST = "127.0.0.1"
    PORT = 19000   # Puerto distinto al de producción para no colisionar

    # ── Datos semilla conocidos ───────────────────────────────────────────────

    PASSWORD_SHA256 = "a" * 64
    CORREO_SUPER    = "super@sigomei.mx"
    ID_USUARIO      = "u-test-super-001"
    ID_TECNICO_1    = "T-001"
    ID_EQUIPO_1     = "e-001"

    # ── Helpers de BD ─────────────────────────────────────────────────────────

    def _get_conn(self):
        return mysql.connector.connect(**DB_TEST_CONFIG)

    def _limpiar_bd(self):
        conn = self._get_conn()
        cur = conn.cursor()
        tablas = [
            "log_auditoria", "historial_estado", "nota_seguimiento",
            "orden_mantenimiento", "certificacion_tecnico",
            "tecnico", "equipo", "usuario",
        ]
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for tabla in tablas:
            cur.execute(f"DELETE FROM {tabla}")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        cur.close()
        conn.close()

    def _insertar_semillas(self):
        conn = self._get_conn()
        cur = conn.cursor()

        # Usuario supervisor con contraseña conocida
        password_bcrypt = bcrypt.hashpw(
            self.PASSWORD_SHA256.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        cur.execute(
            "INSERT INTO usuario (id_usuario, correo, password_hash, rol, activo) "
            "VALUES (%s, %s, %s, 'Supervisor', 1)",
            (self.ID_USUARIO, self.CORREO_SUPER, password_bcrypt),
        )

        # Técnico activo con certificación Mecánica nivel II
        cur.execute(
            "INSERT INTO tecnico (id_tecnico, nombre, rfc, telefono, correo, "
            "fecha_ingreso, estatus, activo) "
            "VALUES (%s, 'Carlos Mendoza', 'MERC850101ABC', '9211234567', "
            "'carlos@sigomei.mx', '2020-01-10', 'Activo', 1)",
            (self.ID_TECNICO_1,),
        )
        cur.execute(
            "INSERT INTO certificacion_tecnico (id_cert, id_tecnico, especialidad, nivel, vigencia) "
            "VALUES (%s, %s, 'Mecánica', 'II', '2030-12-31')",
            (str(uuid.uuid4()), self.ID_TECNICO_1),
        )

        # Equipo activo de criticidad Alta tipo Mecánica
        cur.execute(
            "INSERT INTO equipo (id_equipo, nombre, tipo, marca, modelo, num_serie, "
            "ubicacion, fecha_instalacion, criticidad, activo) "
            "VALUES (%s, 'Compresor Norte', 'Mecánica', 'Atlas', 'GA55', "
            "'SER-TEST-001', 'Planta 1', '2021-03-15', 'Alta', 1)",
            (self.ID_EQUIPO_1,),
        )

        conn.commit()
        cur.close()
        conn.close()

    def _contar_filas(self, tabla: str, where: str = "1=1") -> int:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {tabla} WHERE {where}")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count

    def _fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        conn = self._get_conn()
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    # ── Fixture de servidor ───────────────────────────────────────────────────

    def setUp(self):
        self._limpiar_bd()
        self._insertar_semillas()
        self.repo = MySQLRepository(DB_TEST_CONFIG)
        self.servidor = SIGOMEISocketServer(self.HOST, self.PORT, self.repo)
        self._hilo = threading.Thread(
            target=self.servidor.iniciar, daemon=True, name="test-server"
        )
        self._hilo.start()
        time.sleep(0.15)

    def tearDown(self):
        self.servidor._shutdown.set()
        self._hilo.join(timeout=2)
        self._limpiar_bd()

    def _login(self) -> str:
        return _hacer_login(self.HOST, self.PORT, self.CORREO_SUPER, self.PASSWORD_SHA256)

    def _send(self, request: dict) -> dict:
        return _enviar_y_recibir(self.HOST, self.PORT, request)


# ══════════════════════════════════════════════════════════════════════════════
# 1. CONECTIVIDAD Y PROTOCOLO
# ══════════════════════════════════════════════════════════════════════════════

class TestConectividadProtocolo(IntegrationTestBase):

    def test_ping_responde_pong(self):
        """El servidor responde a 'ping' sin autenticación."""
        resp = self._send({"action": "ping"})
        self.assertEqual(resp["status"], "OK")
        self.assertEqual(resp["message"], "pong")

    def test_json_invalido_devuelve_err_bad_request(self):
        """Línea que no es JSON válido retorna ERR_BAD_REQUEST."""
        with socket.create_connection((self.HOST, self.PORT), timeout=5) as sock:
            sock.sendall(b"esto no es json\n")
            datos = sock.recv(4096)
        resp = json.loads(datos.split(b"\n")[0])
        self.assertEqual(resp["status"], "ERR_BAD_REQUEST")

    def test_accion_desconocida_devuelve_err_bad_request(self):
        """Acción inexistente retorna ERR_BAD_REQUEST."""
        token = self._login()
        resp = self._send({"action": "ACCION_INVENTADA", "token": token, "payload": {}})
        self.assertEqual(resp["status"], "ERR_BAD_REQUEST")

    def test_accion_protegida_sin_token_devuelve_err_auth(self):
        """Acción protegida sin token retorna ERR_AUTH."""
        resp = self._send({"action": "LISTAR_ODMS", "payload": {}})
        self.assertEqual(resp["status"], "ERR_AUTH")

    def test_token_invalido_devuelve_err_auth(self):
        """Token inventado no autoriza acceso."""
        resp = self._send({"action": "LISTAR_ODMS", "token": "token-falso-xyz", "payload": {}})
        self.assertEqual(resp["status"], "ERR_AUTH")

    def test_alias_mayusculas_y_snake_case_son_equivalentes(self):
        """LISTAR_ODMS y listar_odms producen la misma respuesta."""
        token = self._login()
        resp_alias  = self._send({"action": "LISTAR_ODMS",  "token": token, "payload": {}})
        resp_nativo = self._send({"action": "listar_odms",  "token": token, "payload": {}})
        self.assertEqual(resp_alias["status"],  "OK")
        self.assertEqual(resp_nativo["status"], "OK")


# ══════════════════════════════════════════════════════════════════════════════
# 2. AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════════════════════

class TestAutenticacion(IntegrationTestBase):

    def test_login_exitoso_devuelve_token_y_rol(self):
        """Login válido devuelve status OK, token y rol."""
        resp = self._send({
            "action": "LOGIN",
            "payload": {"correo": self.CORREO_SUPER, "password_hash": self.PASSWORD_SHA256},
        })
        self.assertEqual(resp["status"], "OK")
        self.assertIn("token", resp["data"])
        self.assertEqual(resp["data"]["rol"], "Supervisor")

    def test_login_password_incorrecta_devuelve_err_auth(self):
        """Contraseña equivocada retorna ERR_AUTH."""
        resp = self._send({
            "action": "LOGIN",
            "payload": {"correo": self.CORREO_SUPER, "password_hash": "b" * 64},
        })
        self.assertEqual(resp["status"], "ERR_AUTH")

    def test_login_usuario_inexistente_devuelve_err_auth(self):
        """Correo no registrado retorna ERR_AUTH."""
        resp = self._send({
            "action": "LOGIN",
            "payload": {"correo": "nadie@sigomei.mx", "password_hash": "a" * 64},
        })
        self.assertEqual(resp["status"], "ERR_AUTH")

    def test_logout_invalida_token(self):
        """Después del LOGOUT el token es rechazado."""
        token = self._login()
        resp_antes = self._send({"action": "LISTAR_ODMS", "token": token, "payload": {}})
        self.assertEqual(resp_antes["status"], "OK")

        self._send({"action": "LOGOUT", "token": token})

        resp_despues = self._send({"action": "LISTAR_ODMS", "token": token, "payload": {}})
        self.assertEqual(resp_despues["status"], "ERR_AUTH")

    def test_dos_sesiones_simultaneas_independientes(self):
        """Dos logins producen tokens distintos y ambos funcionan."""
        token_1 = self._login()
        token_2 = self._login()
        self.assertNotEqual(token_1, token_2)
        self.assertEqual(self._send({"action": "LISTAR_ODMS", "token": token_1, "payload": {}})["status"], "OK")
        self.assertEqual(self._send({"action": "LISTAR_ODMS", "token": token_2, "payload": {}})["status"], "OK")


# ══════════════════════════════════════════════════════════════════════════════
# 3. FLUJOS DE ÓRDENES DE MANTENIMIENTO (ODM)
# ══════════════════════════════════════════════════════════════════════════════

class TestODMFlujos(IntegrationTestBase):

    def setUp(self):
        super().setUp()
        self.token = self._login()

    def _payload_odm(self, **overrides) -> dict:
        base = {
            "id_equipo": self.ID_EQUIPO_1,
            "id_tecnico": self.ID_TECNICO_1,
            "nota_original": "Mantenimiento preventivo semestral",
            "fecha_programada": "2026-06-10",
            "fecha_estimada_cierre": "2026-06-12",
            "costo_estimado": 8500.00,
        }
        base.update(overrides)
        return base

    # ── Creación ──────────────────────────────────────────────────────────────

    def test_crear_odm_exitosa_persiste_en_bd(self):
        """Crear ODM válida retorna OK y el registro aparece en la BD."""
        resp = self._send({
            "action": "CREAR_ODM",
            "token": self.token,
            "payload": self._payload_odm(),
        })
        self.assertEqual(resp["status"], "OK")
        id_odm = resp["data"]["id_odm"]

        # Verificar que existe en BD
        fila = self._fetch_one(
            "SELECT id_odm, estado FROM orden_mantenimiento WHERE id_odm = %s", (id_odm,)
        )
        self.assertIsNotNone(fila)
        self.assertEqual(fila["estado"], "En_revision")

    def test_crear_odm_tecnico_inexistente_devuelve_err_not_found(self):
        """Técnico que no existe en BD retorna ERR_NOT_FOUND."""
        resp = self._send({
            "action": "CREAR_ODM",
            "token": self.token,
            "payload": self._payload_odm(id_tecnico="T-INEXISTENTE"),
        })
        self.assertEqual(resp["status"], "ERR_NOT_FOUND")
        self.assertEqual(self._contar_filas("orden_mantenimiento"), 0)

    def test_crear_odm_equipo_inexistente_devuelve_err_not_found(self):
        """Equipo que no existe en BD retorna ERR_NOT_FOUND."""
        resp = self._send({
            "action": "CREAR_ODM",
            "token": self.token,
            "payload": self._payload_odm(id_equipo="e-INEXISTENTE"),
        })
        self.assertEqual(resp["status"], "ERR_NOT_FOUND")

    def test_crear_odm_tecnico_inactivo_devuelve_err_business(self):
        """RN-04: Técnico Inactivo no puede ser asignado; no se crea registro."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE tecnico SET estatus = 'Inactivo' WHERE id_tecnico = %s",
            (self.ID_TECNICO_1,)
        )
        conn.commit()
        cur.close()
        conn.close()

        resp = self._send({
            "action": "CREAR_ODM",
            "token": self.token,
            "payload": self._payload_odm(),
        })
        self.assertEqual(resp["status"], "ERR_BUSINESS")
        self.assertEqual(self._contar_filas("orden_mantenimiento"), 0)

    # ── Consultas ─────────────────────────────────────────────────────────────

    def test_obtener_odm_existente(self):
        """OBTENER_ODM con id válido retorna los datos de la orden."""
        resp_crear = self._send({
            "action": "CREAR_ODM", "token": self.token, "payload": self._payload_odm()
        })
        id_odm = resp_crear["data"]["id_odm"]

        resp = self._send({
            "action": "OBTENER_ODM",
            "token": self.token,
            "payload": {"id_odm": id_odm},
        })
        self.assertEqual(resp["status"], "OK")
        self.assertEqual(resp["data"]["id_odm"], id_odm)

    def test_obtener_odm_inexistente_devuelve_err_not_found(self):
        """OBTENER_ODM con id desconocido retorna ERR_NOT_FOUND."""
        resp = self._send({
            "action": "OBTENER_ODM",
            "token": self.token,
            "payload": {"id_odm": "ODM-INEXISTENTE"},
        })
        self.assertEqual(resp["status"], "ERR_NOT_FOUND")

    def test_listar_odms_devuelve_registros_creados(self):
        """LISTAR_ODMS refleja las ODMs efectivamente guardadas en BD."""
        self._send({"action": "CREAR_ODM", "token": self.token, "payload": self._payload_odm()})
        resp = self._send({"action": "LISTAR_ODMS", "token": self.token, "payload": {}})
        self.assertEqual(resp["status"], "OK")
        self.assertGreaterEqual(len(resp["data"]), 1)

    # ── Transiciones de estado ────────────────────────────────────────────────

    def test_actualizar_estado_transicion_valida_persiste_en_bd(self):
        """RN-07: En_revision → Programada actualiza el estado en BD."""
        id_odm = self._send({
            "action": "CREAR_ODM", "token": self.token, "payload": self._payload_odm()
        })["data"]["id_odm"]

        resp = self._send({
            "action": "ACTUALIZAR_ESTADO_ODM",
            "token": self.token,
            "payload": {"id_odm": id_odm, "nuevo_estado": "Programada"},
        })
        self.assertEqual(resp["status"], "OK")

        fila = self._fetch_one(
            "SELECT estado FROM orden_mantenimiento WHERE id_odm = %s", (id_odm,)
        )
        self.assertEqual(fila["estado"], "Programada")

    def test_actualizar_estado_transicion_invalida_devuelve_err_business(self):
        """RN-07: En_revision → Finalizada es transición prohibida."""
        id_odm = self._send({
            "action": "CREAR_ODM", "token": self.token, "payload": self._payload_odm()
        })["data"]["id_odm"]

        resp = self._send({
            "action": "ACTUALIZAR_ESTADO_ODM",
            "token": self.token,
            "payload": {"id_odm": id_odm, "nuevo_estado": "Finalizada"},
        })
        self.assertEqual(resp["status"], "ERR_BUSINESS")

        # El estado no cambió en BD
        fila = self._fetch_one(
            "SELECT estado FROM orden_mantenimiento WHERE id_odm = %s", (id_odm,)
        )
        self.assertEqual(fila["estado"], "En_revision")

    def test_finalizar_odm_persiste_costos_en_bd(self):
        """RN-08: Finalizar ODM guarda costo_real y variacion_porcentual en BD."""
        # Avanzar hasta En_Ejecucion
        id_odm = self._send({
            "action": "CREAR_ODM", "token": self.token, "payload": self._payload_odm(costo_estimado=10000.0)
        })["data"]["id_odm"]
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": self.token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "Programada"}})
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": self.token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "En_Ejecucion"}})

        resp = self._send({
            "action": "ACTUALIZAR_ESTADO_ODM",
            "token": self.token,
            "payload": {"id_odm": id_odm, "nuevo_estado": "Finalizada", "costo_real": 12000.0},
        })
        self.assertEqual(resp["status"], "OK")

        fila = self._fetch_one(
            "SELECT estado, costo_real, variacion_porcentual FROM orden_mantenimiento WHERE id_odm = %s",
            (id_odm,)
        )
        self.assertEqual(fila["estado"], "Finalizada")
        self.assertAlmostEqual(float(fila["costo_real"]), 12000.0, places=1)
        self.assertAlmostEqual(float(fila["variacion_porcentual"]), 20.0, places=1)

    def test_finalizar_odm_sin_costo_real_devuelve_err_business(self):
        """RN-08: Finalizar sin costo_real retorna ERR_BUSINESS."""
        id_odm = self._send({
            "action": "CREAR_ODM", "token": self.token, "payload": self._payload_odm()
        })["data"]["id_odm"]
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": self.token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "Programada"}})
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": self.token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "En_Ejecucion"}})

        resp = self._send({
            "action": "ACTUALIZAR_ESTADO_ODM",
            "token": self.token,
            "payload": {"id_odm": id_odm, "nuevo_estado": "Finalizada"},
        })
        self.assertEqual(resp["status"], "ERR_BUSINESS")

    # ── Notas y reasignación ─────────────────────────────────────────────────

    def test_agregar_nota_odm_persiste_en_bd(self):
        """AGREGAR_NOTA_ODM crea el registro de nota en BD."""
        id_odm = self._send({
            "action": "CREAR_ODM", "token": self.token, "payload": self._payload_odm()
        })["data"]["id_odm"]

        resp = self._send({
            "action": "AGREGAR_NOTA_ODM",
            "token": self.token,
            "payload": {"id_odm": id_odm, "nota_adicional": "Revisión completada."},
        })
        self.assertEqual(resp["status"], "OK")
        self.assertGreater(
            self._contar_filas("nota_seguimiento", f"id_odm = '{id_odm}'"), 0
        )

    def test_agregar_nota_vacia_devuelve_err_business(self):
        """Una nota en blanco no debe guardarse en BD."""
        id_odm = self._send({
            "action": "CREAR_ODM", "token": self.token, "payload": self._payload_odm()
        })["data"]["id_odm"]

        resp = self._send({
            "action": "AGREGAR_NOTA_ODM",
            "token": self.token,
            "payload": {"id_odm": id_odm, "nota_adicional": "   "},
        })
        self.assertEqual(resp["status"], "ERR_BUSINESS")
        self.assertEqual(self._contar_filas("nota_seguimiento", f"id_odm = '{id_odm}'"), 0)

    def test_reasignar_tecnico_odm_exitoso(self):
        """REASIGNAR_TECNICO_ODM actualiza id_tecnico en BD."""
        # Insertar segundo técnico
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tecnico (id_tecnico, nombre, rfc, telefono, correo, "
            "fecha_ingreso, estatus, activo) "
            "VALUES ('T-002', 'Ana Pérez', 'PELA900201XYZ', '9219876543', "
            "'ana@sigomei.mx', '2022-05-01', 'Activo', 1)"
        )
        cur.execute(
            "INSERT INTO certificacion_tecnico (id_cert, id_tecnico, especialidad, nivel, vigencia) "
            "VALUES (%s, 'T-002', 'Mecánica', 'II', '2030-12-31')",
            (str(uuid.uuid4()),)
        )
        conn.commit()
        cur.close()
        conn.close()

        id_odm = self._send({
            "action": "CREAR_ODM", "token": self.token, "payload": self._payload_odm()
        })["data"]["id_odm"]

        resp = self._send({
            "action": "REASIGNAR_TECNICO_ODM",
            "token": self.token,
            "payload": {"id_odm": id_odm, "id_tecnico_nuevo": "T-002"},
        })
        self.assertEqual(resp["status"], "OK")

        fila = self._fetch_one(
            "SELECT id_tecnico FROM orden_mantenimiento WHERE id_odm = %s", (id_odm,)
        )
        self.assertEqual(fila["id_tecnico"], "T-002")

    def test_reasignar_tecnico_en_odm_terminal_devuelve_err_business(self):
        """No se puede reasignar técnico en una ODM Cancelada."""
        id_odm = self._send({
            "action": "CREAR_ODM", "token": self.token, "payload": self._payload_odm()
        })["data"]["id_odm"]
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": self.token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "Programada"}})
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": self.token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "Cancelada"}})

        resp = self._send({
            "action": "REASIGNAR_TECNICO_ODM",
            "token": self.token,
            "payload": {"id_odm": id_odm, "id_tecnico_nuevo": self.ID_TECNICO_1},
        })
        self.assertEqual(resp["status"], "ERR_BUSINESS")


# ══════════════════════════════════════════════════════════════════════════════
# 4. FLUJOS DE TÉCNICOS
# ══════════════════════════════════════════════════════════════════════════════

class TestTecnicosFlujos(IntegrationTestBase):

    def setUp(self):
        super().setUp()
        self.token = self._login()

    def test_crear_tecnico_persiste_en_bd(self):
        """CREAR_TECNICO inserta el registro en BD y retorna el id generado."""
        resp = self._send({
            "action": "CREAR_TECNICO",
            "token": self.token,
            "payload": {
                "nombre": "Ana Pérez López",
                "rfc": "PELA900201XYZ",
                "telefono": "9219876543",
                "correo": "ana@sigomei.mx",
                "fecha_ingreso": "2024-01-15",
            },
        })
        self.assertEqual(resp["status"], "OK")
        id_tecnico = resp["data"]["id_tecnico"]
        fila = self._fetch_one(
            "SELECT nombre FROM tecnico WHERE id_tecnico = %s", (id_tecnico,)
        )
        self.assertIsNotNone(fila)

    def test_crear_tecnico_rfc_duplicado_devuelve_err_business(self):
        """RF-35: RFC ya registrado retorna ERR_BUSINESS sin insertar."""
        resp = self._send({
            "action": "CREAR_TECNICO",
            "token": self.token,
            "payload": {
                "nombre": "Clon Mendoza",
                "rfc": "MERC850101ABC",   # mismo RFC que T-001 de la semilla
                "telefono": "9210000000",
                "correo": "clon@sigomei.mx",
                "fecha_ingreso": "2025-01-01",
            },
        })
        self.assertEqual(resp["status"], "ERR_BUSINESS")
        self.assertEqual(self._contar_filas("tecnico"), 1)  # sólo el de semilla

    def test_obtener_tecnico_existente(self):
        """OBTENER_TECNICO con id válido retorna sus datos."""
        resp = self._send({
            "action": "OBTENER_TECNICO",
            "token": self.token,
            "payload": {"id_tecnico": self.ID_TECNICO_1},
        })
        self.assertEqual(resp["status"], "OK")
        self.assertEqual(resp["data"]["id_tecnico"], self.ID_TECNICO_1)

    def test_obtener_tecnico_inexistente_devuelve_err_not_found(self):
        """OBTENER_TECNICO con id desconocido retorna ERR_NOT_FOUND."""
        resp = self._send({
            "action": "OBTENER_TECNICO",
            "token": self.token,
            "payload": {"id_tecnico": "T-FANTASMA"},
        })
        self.assertEqual(resp["status"], "ERR_NOT_FOUND")

    def test_cambiar_estatus_tecnico_persiste_en_bd(self):
        """CAMBIAR_ESTATUS_TECNICO actualiza el campo estatus en BD."""
        resp = self._send({
            "action": "CAMBIAR_ESTATUS_TECNICO",
            "token": self.token,
            "payload": {"id_tecnico": self.ID_TECNICO_1, "nuevo_estatus": "Inactivo"},
        })
        self.assertEqual(resp["status"], "OK")
        fila = self._fetch_one(
            "SELECT estatus FROM tecnico WHERE id_tecnico = %s", (self.ID_TECNICO_1,)
        )
        self.assertEqual(fila["estatus"], "Inactivo")

    def test_carga_tecnico_devuelve_lista(self):
        """CARGA_TECNICO retorna las ODMs asociadas al técnico."""
        resp = self._send({
            "action": "CARGA_TECNICO",
            "token": self.token,
            "payload": {"id_tecnico": self.ID_TECNICO_1},
        })
        self.assertEqual(resp["status"], "OK")
        self.assertIsInstance(resp["data"], list)


# ══════════════════════════════════════════════════════════════════════════════
# 5. FLUJOS DE EQUIPOS INDUSTRIALES
# ══════════════════════════════════════════════════════════════════════════════

class TestEquiposFlujos(IntegrationTestBase):

    def setUp(self):
        super().setUp()
        self.token = self._login()

    def test_crear_equipo_persiste_en_bd(self):
        """CREAR_EQUIPO inserta el registro en BD."""
        resp = self._send({
            "action": "CREAR_EQUIPO",
            "token": self.token,
            "payload": {
                "nombre": "Motor Eléctrico B2",
                "tipo": "Eléctrica",
                "marca": "Siemens",
                "modelo": "1LE7",
                "num_serie": "SER-NEW-999",
                "ubicacion": "Planta 2",
                "fecha_instalacion": "2023-03-01",
                "criticidad": "Media",
            },
        })
        self.assertEqual(resp["status"], "OK")
        id_equipo = resp["data"]["id_equipo"]
        fila = self._fetch_one("SELECT nombre FROM equipo WHERE id_equipo = %s", (id_equipo,))
        self.assertIsNotNone(fila)

    def test_crear_equipo_serie_duplicada_devuelve_err_business(self):
        """RF-31: Número de serie duplicado retorna ERR_BUSINESS."""
        resp = self._send({
            "action": "CREAR_EQUIPO",
            "token": self.token,
            "payload": {
                "nombre": "Clon Compresor",
                "tipo": "Mecánica",
                "marca": "Atlas",
                "modelo": "GA55",
                "num_serie": "SER-TEST-001",   # mismo que el de semilla
                "ubicacion": "Planta 3",
                "fecha_instalacion": "2023-01-01",
                "criticidad": "Baja",
            },
        })
        self.assertEqual(resp["status"], "ERR_BUSINESS")
        self.assertEqual(self._contar_filas("equipo"), 1)

    def test_obtener_equipo_existente(self):
        """OBTENER_EQUIPO con id válido retorna sus datos."""
        resp = self._send({
            "action": "OBTENER_EQUIPO",
            "token": self.token,
            "payload": {"id_equipo": self.ID_EQUIPO_1},
        })
        self.assertEqual(resp["status"], "OK")
        self.assertEqual(resp["data"]["id_equipo"], self.ID_EQUIPO_1)

    def test_baja_equipo_sin_historial_es_eliminacion_fisica(self):
        """RF-08: Equipo sin ODMs se elimina físicamente de BD."""
        resp = self._send({
            "action": "BAJA_EQUIPO",
            "token": self.token,
            "payload": {"id_equipo": self.ID_EQUIPO_1},
        })
        self.assertEqual(resp["status"], "OK")
        self.assertEqual(resp["data"]["tipo_baja"], "fisica")
        self.assertEqual(self._contar_filas("equipo", f"id_equipo = '{self.ID_EQUIPO_1}'"), 0)

    def test_baja_equipo_con_historial_es_baja_logica(self):
        """Equipo con ODMs finalizadas recibe baja lógica (activo = 0)."""
        # Crear y finalizar una ODM para generar historial
        token = self.token
        id_odm = self._send({
            "action": "CREAR_ODM", "token": token,
            "payload": {
                "id_equipo": self.ID_EQUIPO_1, "id_tecnico": self.ID_TECNICO_1,
                "nota_original": "Historial", "fecha_programada": "2026-06-10",
                "fecha_estimada_cierre": "2026-06-12", "costo_estimado": 5000.0,
            }
        })["data"]["id_odm"]
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "Programada"}})
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "En_Ejecucion"}})
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "Finalizada", "costo_real": 5500.0}})

        resp = self._send({
            "action": "BAJA_EQUIPO", "token": token,
            "payload": {"id_equipo": self.ID_EQUIPO_1},
        })
        self.assertEqual(resp["status"], "OK")
        self.assertEqual(resp["data"]["tipo_baja"], "logica")

        fila = self._fetch_one(
            "SELECT activo FROM equipo WHERE id_equipo = %s", (self.ID_EQUIPO_1,)
        )
        self.assertEqual(fila["activo"], 0)

    def test_baja_equipo_con_odms_activas_devuelve_err_business(self):
        """Equipo con ODMs activas no puede darse de baja."""
        self._send({
            "action": "CREAR_ODM", "token": self.token,
            "payload": {
                "id_equipo": self.ID_EQUIPO_1, "id_tecnico": self.ID_TECNICO_1,
                "nota_original": "ODM activa", "fecha_programada": "2026-06-10",
                "fecha_estimada_cierre": "2026-06-12", "costo_estimado": 5000.0,
            }
        })

        resp = self._send({
            "action": "BAJA_EQUIPO", "token": self.token,
            "payload": {"id_equipo": self.ID_EQUIPO_1},
        })
        self.assertEqual(resp["status"], "ERR_BUSINESS")
        # El equipo sigue activo en BD
        fila = self._fetch_one("SELECT activo FROM equipo WHERE id_equipo = %s", (self.ID_EQUIPO_1,))
        self.assertEqual(fila["activo"], 1)

    def test_historial_equipo_inexistente_devuelve_err_not_found(self):
        """HISTORIAL_EQUIPO con id desconocido retorna ERR_NOT_FOUND."""
        resp = self._send({
            "action": "HISTORIAL_EQUIPO",
            "token": self.token,
            "payload": {"id_equipo": "e-FANTASMA"},
        })
        self.assertEqual(resp["status"], "ERR_NOT_FOUND")


# ══════════════════════════════════════════════════════════════════════════════
# 6. REPORTES Y EXPORTACIÓN
# ══════════════════════════════════════════════════════════════════════════════

class TestReportesFlujos(IntegrationTestBase):

    def setUp(self):
        super().setUp()
        self.token = self._login()

    def test_reporte_equipos_criticos_retorna_lista(self):
        """REPORTE_EQUIPOS_CRITICOS retorna status OK con una lista."""
        resp = self._send({
            "action": "REPORTE_EQUIPOS_CRITICOS",
            "token": self.token,
            "payload": {},
        })
        self.assertEqual(resp["status"], "OK")
        self.assertIsInstance(resp["data"], list)

    def test_exportar_csv_odms_devuelve_base64_decodificable(self):
        """EXPORTAR_CSV de odms retorna contenido Base64 válido con cabeceras CSV."""
        # Crear al menos una ODM para que el CSV tenga datos reales
        self._send({
            "action": "CREAR_ODM", "token": self.token,
            "payload": {
                "id_equipo": self.ID_EQUIPO_1, "id_tecnico": self.ID_TECNICO_1,
                "nota_original": "Para reporte", "fecha_programada": "2026-07-01",
                "fecha_estimada_cierre": "2026-07-03", "costo_estimado": 3000.0,
            }
        })

        resp = self._send({
            "action": "EXPORTAR_CSV",
            "token": self.token,
            "payload": {
                "tipo_reporte": "odms",
                "parametros": {"fecha_inicio": "2026-01-01", "fecha_fin": "2026-12-31"},
            },
        })
        self.assertEqual(resp["status"], "OK")
        self.assertIn("contenido_base64", resp["data"])

        import base64
        decoded = base64.b64decode(resp["data"]["contenido_base64"])
        self.assertIn(b"id_odm", decoded)

    def test_exportar_csv_tipo_invalido_devuelve_err_bad_request(self):
        """Tipo de reporte no soportado retorna ERR_BAD_REQUEST."""
        resp = self._send({
            "action": "EXPORTAR_CSV",
            "token": self.token,
            "payload": {"tipo_reporte": "tipo_inexistente", "parametros": {}},
        })
        self.assertEqual(resp["status"], "ERR_BAD_REQUEST")

    def test_reporte_desempeno_tecnico_existente(self):
        """REPORTE_DESEMPENO con técnico válido retorna OK."""
        resp = self._send({
            "action": "REPORTE_DESEMPENO",
            "token": self.token,
            "payload": {
                "id_tecnico": self.ID_TECNICO_1,
                "fecha_inicio": "2026-01-01",
                "fecha_fin": "2026-12-31",
            },
        })
        self.assertEqual(resp["status"], "OK")

    def test_resumen_costos_odm_finalizada(self):
        """RESUMEN_COSTOS sobre ODM Finalizada retorna los tres campos."""
        token = self.token
        id_odm = self._send({
            "action": "CREAR_ODM", "token": token,
            "payload": {
                "id_equipo": self.ID_EQUIPO_1, "id_tecnico": self.ID_TECNICO_1,
                "nota_original": "Para resumen", "fecha_programada": "2026-07-01",
                "fecha_estimada_cierre": "2026-07-05", "costo_estimado": 10000.0,
            }
        })["data"]["id_odm"]
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "Programada"}})
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "En_Ejecucion"}})
        self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": token,
                    "payload": {"id_odm": id_odm, "nuevo_estado": "Finalizada", "costo_real": 11000.0}})

        resp = self._send({
            "action": "RESUMEN_COSTOS",
            "token": token,
            "payload": {"id_odm": id_odm},
        })
        self.assertEqual(resp["status"], "OK")
        self.assertIn("costo_estimado", resp["data"])
        self.assertIn("costo_real", resp["data"])
        self.assertIn("variacion_pct", resp["data"])
        self.assertAlmostEqual(resp["data"]["variacion_pct"], 10.0, places=1)

    def test_resumen_costos_odm_no_finalizada_devuelve_err_business(self):
        """RESUMEN_COSTOS sobre ODM no Finalizada retorna ERR_BUSINESS."""
        id_odm = self._send({
            "action": "CREAR_ODM", "token": self.token,
            "payload": {
                "id_equipo": self.ID_EQUIPO_1, "id_tecnico": self.ID_TECNICO_1,
                "nota_original": "Abierta", "fecha_programada": "2026-07-01",
                "fecha_estimada_cierre": "2026-07-03", "costo_estimado": 5000.0,
            }
        })["data"]["id_odm"]

        resp = self._send({
            "action": "RESUMEN_COSTOS",
            "token": self.token,
            "payload": {"id_odm": id_odm},
        })
        self.assertEqual(resp["status"], "ERR_BUSINESS")


# ══════════════════════════════════════════════════════════════════════════════
# 7. FLUJOS ENCADENADOS (fin a fin dentro de una sesión)
# ══════════════════════════════════════════════════════════════════════════════

class TestFlujosEncadenados(IntegrationTestBase):

    def test_ciclo_vida_odm_completo(self):
        """
        Flujo: login → crear ODM → Programada → En_Ejecucion → Finalizar → resumen → logout.
        Verifica persistencia en BD en cada paso.
        """
        token = self._login()

        # 1. Crear ODM
        id_odm = self._send({
            "action": "CREAR_ODM", "token": token,
            "payload": {
                "id_equipo": self.ID_EQUIPO_1, "id_tecnico": self.ID_TECNICO_1,
                "nota_original": "Ciclo completo", "fecha_programada": "2026-07-01",
                "fecha_estimada_cierre": "2026-07-03", "costo_estimado": 5000.0,
            }
        })["data"]["id_odm"]
        self.assertIsNotNone(id_odm)

        # 2. En_revision → Programada
        self.assertEqual(
            self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": token,
                        "payload": {"id_odm": id_odm, "nuevo_estado": "Programada"}})["status"], "OK"
        )

        # 3. Programada → En_Ejecucion
        self.assertEqual(
            self._send({"action": "ACTUALIZAR_ESTADO_ODM", "token": token,
                        "payload": {"id_odm": id_odm, "nuevo_estado": "En_Ejecucion"}})["status"], "OK"
        )

        # 4. En_Ejecucion → Finalizada
        resp_final = self._send({
            "action": "ACTUALIZAR_ESTADO_ODM", "token": token,
            "payload": {"id_odm": id_odm, "nuevo_estado": "Finalizada", "costo_real": 5500.0},
        })
        self.assertEqual(resp_final["status"], "OK")

        # Verificar en BD
        fila = self._fetch_one(
            "SELECT estado, variacion_porcentual FROM orden_mantenimiento WHERE id_odm = %s",
            (id_odm,)
        )
        self.assertEqual(fila["estado"], "Finalizada")
        self.assertAlmostEqual(float(fila["variacion_porcentual"]), 10.0, places=1)

        # 5. Resumen de costos
        resp_resumen = self._send({
            "action": "RESUMEN_COSTOS", "token": token, "payload": {"id_odm": id_odm}
        })
        self.assertEqual(resp_resumen["status"], "OK")
        self.assertAlmostEqual(resp_resumen["data"]["variacion_pct"], 10.0, places=1)

        # 6. Logout
        self.assertEqual(self._send({"action": "LOGOUT", "token": token})["status"], "OK")

    def test_flujo_tecnico_crear_y_cambiar_estatus(self):
        """login → crear técnico → cambiar estatus a Inactivo → verificar en BD."""
        token = self._login()

        resp_crear = self._send({
            "action": "CREAR_TECNICO", "token": token,
            "payload": {
                "nombre": "Luis Gutiérrez",
                "rfc": "GULL890320MNO",
                "telefono": "9219876543",
                "correo": "luis@sigomei.mx",
                "fecha_ingreso": "2025-06-01",
            },
        })
        self.assertEqual(resp_crear["status"], "OK")
        id_tecnico = resp_crear["data"]["id_tecnico"]

        resp_estatus = self._send({
            "action": "CAMBIAR_ESTATUS_TECNICO", "token": token,
            "payload": {"id_tecnico": id_tecnico, "nuevo_estatus": "Inactivo"},
        })
        self.assertEqual(resp_estatus["status"], "OK")

        fila = self._fetch_one(
            "SELECT estatus FROM tecnico WHERE id_tecnico = %s", (id_tecnico,)
        )
        self.assertEqual(fila["estatus"], "Inactivo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
