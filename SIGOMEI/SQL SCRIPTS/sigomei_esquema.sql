-- ─────────────────────────────────────────────────────────────────────────
-- SIGOMEI — DDL MySQL 8.0 (Optimizado para producción)
-- Base de datos: sigomei_db
-- ─────────────────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS sigomei_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sigomei_db;

-- Eliminar tablas en orden inverso a sus dependencias para evitar errores de FK si se vuelve a ejecutar
DROP TABLE IF EXISTS log_auditoria;
DROP TABLE IF EXISTS historial_estado;
DROP TABLE IF EXISTS nota_seguimiento;
DROP TABLE IF EXISTS orden_mantenimiento;
DROP TABLE IF EXISTS certificacion_tecnico;
DROP TABLE IF EXISTS tecnico;
DROP TABLE IF EXISTS equipo;
DROP TABLE IF EXISTS usuario;

-- ──────────────────────────────────────────────────────────────────────────
-- TABLA: usuario
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE usuario (
    id_usuario     CHAR(36)      NOT NULL,
    correo          VARCHAR(150)  NOT NULL,
    password_hash   VARCHAR(255)  NOT NULL,   -- bcrypt hash
    rol             ENUM('Administrador','Supervisor') NOT NULL,
    activo          TINYINT(1)    NOT NULL DEFAULT 1,
    creado_en       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_usuario        PRIMARY KEY (id_usuario),
    CONSTRAINT uq_usuario_correo UNIQUE (correo)
) ENGINE=InnoDB;

CREATE INDEX idx_usuario_correo ON usuario (correo);
CREATE INDEX idx_usuario_rol    ON usuario (rol);

-- ──────────────────────────────────────────────────────────────────────────
-- TABLA: equipo
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE equipo (
    id_equipo        CHAR(36)      NOT NULL,
    nombre           VARCHAR(200)  NOT NULL,
    tipo             VARCHAR(100)  NOT NULL,   -- ej. Mecánica, Eléctrica
    marca            VARCHAR(100)  NOT NULL,
    modelo           VARCHAR(100)  NOT NULL,
    num_serie        VARCHAR(100)  NOT NULL,
    ubicacion        VARCHAR(200)  NOT NULL,
    fecha_instalacion DATE         NOT NULL,
    estado_operativo ENUM('Operativo','Crítico','Fuera de servicio','Inactivo') NOT NULL DEFAULT 'Operativo',
    criticidad       ENUM('Baja','Media','Alta') NOT NULL DEFAULT 'Media',
    activo           TINYINT(1)    NOT NULL DEFAULT 1,
    creado_en        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,