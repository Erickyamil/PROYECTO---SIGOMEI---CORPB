# config.py
# Lee la configuración desde server.properties (si existe) y luego
# desde variables de entorno (las variables de entorno tienen prioridad).
# Nunca contiene credenciales embebidas.

import logging
import os
from pathlib import Path

# ── 1. Cargar server.properties si existe ────────────────────────────────────

def _cargar_properties(ruta: str = "server.properties") -> None:
    """
    Parsea un archivo clave=valor e inyecta cada par en os.environ
    SOLO si la variable no está ya definida en el entorno del proceso.
    Las líneas que empiezan por '#' o están vacías se ignoran.
    """
    path = Path(ruta)
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            if "=" not in linea:
                continue
            clave, _, valor = linea.partition("=")
            clave = clave.strip()
            valor = valor.strip()
            # Las variables de entorno del SO tienen prioridad
            if clave and clave not in os.environ:
                os.environ[clave] = valor


_cargar_properties()


# ── 2. Helpers ────────────────────────────────────────────────────────────────

def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


# ── 3. Parámetros de conexión a BD ───────────────────────────────────────────

DB_CONFIG = {
    "host":     os.getenv("SIGOMEI_DB_HOST",     "127.0.0.1"),
    "user":     os.getenv("SIGOMEI_DB_USER",     "root"),
    "password": os.getenv("SIGOMEI_DB_PASSWORD", ""),
    "database": os.getenv("SIGOMEI_DB_NAME",     "sigomei_db"),
    "port":     _int_env("SIGOMEI_DB_PORT",      3306),
}

SERVER_HOST = os.getenv("SIGOMEI_SERVER_HOST", "127.0.0.1")
SERVER_PORT = _int_env("SIGOMEI_SERVER_PORT",  9000)


# ── 4. Configuración de la bitácora ──────────────────────────────────────────

def configurar_logging() -> logging.Logger:
    """
    Configura el logger raíz de SIGOMEI.
    - Siempre escribe a la consola (StreamHandler).
    - Si SIGOMEI_LOG_FILE está definido, también escribe a disco (RotatingFileHandler).
    Retorna el logger listo para usar.
    """
    nivel_str  = os.getenv("SIGOMEI_LOG_LEVEL", "INFO").upper()
    nivel      = getattr(logging, nivel_str, logging.INFO)
    log_file   = os.getenv("SIGOMEI_LOG_FILE", "").strip()

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(threadName)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger("sigomei")
    logger.setLevel(nivel)
    logger.handlers.clear()          # evitar duplicados si se llama dos veces

    # Consola
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Archivo (rotativo: máx 5 MB, 3 respaldos)
    if log_file:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.info("Bitacora activa → %s  (nivel %s)", log_file, nivel_str)
    else:
        logger.info("Bitacora solo en consola (SIGOMEI_LOG_FILE no configurado).")

    return logger
