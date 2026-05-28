# tests/test_service.py
# Suite de Pruebas Unitarias Expandida para la Capa de Servicio usando Mocks

import unittest
from unittest.mock import MagicMock

import bcrypt

from services.service import ServiceLayer

class TestServiceLayer(unittest.TestCase):
    def setUp(self):
        """Este método se ejecuta automáticamente antes de CADA caso de prueba."""
        self.mock_repo = MagicMock()
        self.service = ServiceLayer(self.mock_repo)

        # Datos semilla para simulaciones
        self.tecnico_valido = {
            "id_tecnico": "t-001",
            "nombre": "Carlos Mendoza Ruiz",
            "rfc": "MERC850101ABC",
            "estatus": "Activo",
            "certificaciones": [{"especialidad": "Mecánica", "nivel": "II", "vigencia": "2027-12-31"}]
        }
        self.equipo_valido = {
            "id_equipo": "e-001",
            "nombre": "Compresor Norte",
            "tipo": "Mecánica",
            "criticidad": "Alta"
        }
        self.payload_odm = {
            "id_equipo": "e-001",
            "id_tecnico": "t-001",
            "nota_original": "Mantenimiento preventivo semestral",
            "fecha_programada": "2026-06-10",
            "fecha_estimada_cierre": "2026-06-12",
            "costo_estimado": 8500.00
        }

    def test_verificar_credenciales_exitoso(self):
        password_hash_sha256 = "a" * 64
        password_bcrypt = bcrypt.hashpw(
            password_hash_sha256.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")
        self.mock_repo.obtener_usuario_por_correo.return_value = {
            "id_usuario": "u-0002-super",
            "correo": "super@sigomei.mx",
            "password_hash": password_bcrypt,
            "rol": "Supervisor",
            "activo": 1,
        }

        respuesta = self.service.verificar_credenciales(
            "super@sigomei.mx",
            password_hash_sha256,
        )

        self.assertEqual(respuesta["status"], "OK")
        self.assertEqual(respuesta["data"]["id_usuario"], "u-0002-super")
        self.assertEqual(respuesta["data"]["rol"], "Supervisor")

    def test_verificar_credenciales_invalidas(self):
        password_bcrypt = bcrypt.hashpw(
            ("a" * 64).encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")
        self.mock_repo.obtener_usuario_por_correo.return_value = {
            "id_usuario": "u-0002-super",
            "correo": "super@sigomei.mx",
            "password_hash": password_bcrypt,
            "rol": "Supervisor",
            "activo": 1,
        }

        respuesta = self.service.verificar_credenciales(
            "super@sigomei.mx",
            "b" * 64,
        )

        self.assertEqual(respuesta["status"], "ERR_AUTH")

    def test_verificar_credenciales_usuario_no_existe(self):
        self.mock_repo.obtener_usuario_por_correo.return_value = {}

        respuesta = self.service.verificar_credenciales(
            "nadie@sigomei.mx",
            "a" * 64,
        )

        self.assertEqual(respuesta["status"], "ERR_AUTH")

    # ──────────────────────────────────────────────────────────────────────────
    # PRUEBAS: DOMINIO ÓRDENES DE MANTENIMIENTO (ODM)
    # ──────────────────────────────────────────────────────────────────────────

    def test_crear_odm_exitoso(self):
        """Verifica que si los datos cumplen las RN, la orden se guarda en el repositorio."""
        self.mock_repo.obtener_tecnico.return_value = self.tecnico_valido
        self.mock_repo.obtener_equipo.return_value = self.equipo_valido
        self.mock_repo.listar_odms_activas.return_value = []
        self.mock_repo.guardar_odm.return_value = "new-odm-uuid"

        respuesta = self.service.crear_odm(self.payload_odm, id_usuario_creador="u-0002-super")
        
        self.assertEqual(respuesta["status"], "OK")
        self.assertEqual(respuesta["data"]["id_odm"], "new-odm-uuid")
        self.mock_repo.guardar_odm.assert_called_once()

    def test_crear_odm_tecnico_no_existe(self):
        """Verifica el control de errores si se intenta usar un ID de técnico inexistente."""
        self.mock_repo.obtener_tecnico.return_value = {}  # No encontrado

        respuesta = self.service.crear_odm(self.payload_odm, id_usuario_creador="u-0002-super")
        self.assertEqual(respuesta["status"], "ERR_NOT_FOUND")

    def test_crear_odm_error_regla_de_negocio(self):
        """Verifica que si una validación falla (ej. Técnico Inactivo), frena el guardado."""
        tecnico_inactivo = self.tecnico_valido.copy()
        tecnico_inactivo["estatus"] = "Inactivo"

        self.mock_repo.obtener_tecnico.return_value = tecnico_inactivo
        self.mock_repo.obtener_equipo.return_value = self.equipo_valido
        self.mock_repo.listar_odms_activas.return_value = []

        respuesta = self.service.crear_odm(self.payload_odm, id_usuario_creador="u-0002-super")
        self.assertEqual(respuesta["status"], "ERR_BUSINESS")
        self.mock_repo.guardar_odm.assert_not_called()

    def test_actualizar_estado_transicion_invalida(self):
        """RN-07: Verifica que la máquina de estados bloquee pasos ilegales (Finalizada -> Programada)."""
        odm_mock = {"id_odm": "odm-001", "estado": "Finalizada", "costo_estimado": 5000.00}
        self.mock_repo.obtener_odm.return_value = odm_mock

        respuesta = self.service.actualizar_estado_odm("odm-001", "Programada", id_usuario="u-0002-super")
        self.assertEqual(respuesta["status"], "ERR_BUSINESS")
        self.mock_repo.actualizar_estado_simple.assert_not_called()

    def test_actualizar_estado_finalizar_con_exito(self):
        """RF-55 / RN-08: Cerrar una orden calcula la variación porcentual de costos."""
        odm_mock = {"id_odm": "odm-002", "estado": "En_Ejecucion", "costo_estimado": 10000.00}
        self.mock_repo.obtener_odm.return_value = odm_mock

        # El costo estimado era 10,000; cerramos con costo real de 12,000 (+20.0% de variación)
        respuesta = self.service.actualizar_estado_odm(
            id_odm="odm-002", 
            nuevo_estado="Finalizada", 
            id_usuario="u-0002-super", 
            costo_real=12000.00
        )
        self.assertEqual(respuesta["status"], "OK")
        self.mock_repo.actualizar_estado_y_costo.assert_called_once_with(
            "odm-002", "Finalizada", 12000.00, 20.0, "u-0002-super"
        )

    def test_obtener_odm_no_encontrada(self):
        self.mock_repo.obtener_odm.return_value = None
        respuesta = self.service.obtener_odm("id-inexistente")
        self.assertEqual(respuesta["status"], "ERR_NOT_FOUND")

    def test_listar_odms(self):
        self.mock_repo.listar_todas_las_odms.return_value = [{"id_odm": "1"}]
        respuesta = self.service.listar_odms()
        self.assertEqual(respuesta["status"], "OK")
        self.assertEqual(len(respuesta["data"]), 1)

    # ──────────────────────────────────────────────────────────────────────────
    # PRUEBAS: DOMINIO TÉCNICOS
    # ──────────────────────────────────────────────────────────────────────────

    def test_crear_tecnico_exitoso(self):
        self.mock_repo.existe_rfc_tecnico.return_value = False
        self.mock_repo.guardar_tecnico.return_value = "t-new-uuid"

        payload_tecnico = {"nombre": "Ana Pérez", "rfc": "PETA900201XYZ"}
        respuesta = self.service.crear_tecnico(payload_tecnico)
        self.assertEqual(respuesta["status"], "OK")
        self.assertEqual(respuesta["data"]["id_tecnico"], "t-new-uuid")

    def test_crear_tecnico_rfc_duplicado(self):
        """RF-35: Unicidad - No permite registrar si el RFC ya existe."""
        self.mock_repo.existe_rfc_tecnico.return_value = True

        payload_tecnico = {"nombre": "Ana Pérez", "rfc": "PETA900201XYZ"}
        respuesta = self.service.crear_tecnico(payload_tecnico)
        self.assertEqual(respuesta["status"], "ERR_BUSINESS")

    def test_cambiar_estatus_tecnico(self):
        self.mock_repo.obtener_tecnico.return_value = {"id_tecnico": "t-001"}
        respuesta = self.service.cambiar_estatus_tecnico("t-001", "Inactivo")
        self.assertEqual(respuesta["status"], "OK")
        self.mock_repo.actualizar_estatus_tecnico.assert_called_once_with("t-001", "Inactivo")

    # ──────────────────────────────────────────────────────────────────────────
    # PRUEBAS: DOMINIO EQUIPOS INDUSTRIALES
    # ──────────────────────────────────────────────────────────────────────────

    def test_crear_equipo_exitoso(self):
        self.mock_repo.existe_num_serie_equipo.return_value = False
        self.mock_repo.guardar_equipo.return_value = "e-new-uuid"

        payload_equipo = {"nombre": "Motor", "num_serie": "SER-999"}
        respuesta = self.service.crear_equipo(payload_equipo)
        self.assertEqual(respuesta["status"], "OK")

    def test_crear_equipo_serie_duplicado(self):
        """RF-31: Unicidad - Evita registrar dos números de serie iguales."""
        self.mock_repo.existe_num_serie_equipo.return_value = True

        payload_equipo = {"nombre": "Motor", "num_serie": "SER-999"}
        respuesta = self.service.crear_equipo(payload_equipo)
        self.assertEqual(respuesta["status"], "ERR_BUSINESS")

    def test_baja_equipo_exitoso(self):
        """RF-08: La baja de un equipo ejecuta una desactivación lógica."""
        self.mock_repo.obtener_equipo.return_value = {"id_equipo": "e-001"}
        respuesta = self.service.baja_equipo("e-001")
        self.assertEqual(respuesta["status"], "OK")
        self.mock_repo.marcar_inactivo_equipo.assert_called_once_with("e-001")
