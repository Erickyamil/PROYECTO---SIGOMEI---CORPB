# db/connection.py
# Módulo de conexión a MySQL — centraliza la creación de conexiones

import mysql.connector
from config import DB_CONFIG


def get_connection():
    """Retorna una nueva conexión a MySQL usando la configuración global."""
    return mysql.connector.connect(**DB_CONFIG)
