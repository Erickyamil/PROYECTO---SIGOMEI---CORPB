# main_server.py
# Punto de entrada principal del servidor SIGOMEI.

import sys
import logging
import mysql.connector

from config import DB_CONFIG, SERVER_HOST, SERVER_PORT, configurar_logging
from communication.socket_server import SIGOMEISocketServer
from repository.repository import MySQLRepository

logger: logging.Logger  # se asigna en arrancar_servidor()


def _verificar_conexion_db() -> None:
    """Ping a MySQL al inicio para detectar credenciales/host incorrectos
    antes de aceptar peticiones."""
    logger.info(
        "Validando conexion a MySQL en %s:%s (usuario='%s', db='%s')...",
        DB_CONFIG["host"], DB_CONFIG["port"],
        DB_CONFIG["user"], DB_CONFIG["database"],
    )
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.ping(reconnect=False)
        conn.close()
        logger.info("Conexion a MySQL exitosa.")
    except mysql.connector.Error as e:
        logger.error("No se puede conectar a MySQL: %s", e)
        logger.error(
            "Sugerencias: verifique que MySQL este corriendo y configure las "
            "credenciales en server.properties o mediante variables de entorno:\n"
            "  SIGOMEI_DB_HOST, SIGOMEI_DB_USER, SIGOMEI_DB_PASSWORD, "
            "SIGOMEI_DB_NAME, SIGOMEI_DB_PORT"
        )
        sys.exit(1)


def arrancar_servidor():
    global logger
    logger = configurar_logging()

    logger.info("=" * 60)
    logger.info("  INICIALIZANDO SIGOMEI — Sistema de Gestion Industrial  ")
    logger.info("=" * 60)

    _verificar_conexion_db()

    logger.info("Preparando capa de persistencia MySQL...")
    try:
        repositorio_real = MySQLRepository(DB_CONFIG)
        servidor_red = SIGOMEISocketServer(
            host=SERVER_HOST,
            port=SERVER_PORT,
            repository=repositorio_real,
        )
        servidor_red.iniciar()
    except KeyboardInterrupt:
        logger.info("Servidor apagado con Ctrl+C.")
        sys.exit(0)
    except Exception as e:
        logger.exception("ERROR CRITICO AL INICIAR EL SERVIDOR: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    arrancar_servidor()
