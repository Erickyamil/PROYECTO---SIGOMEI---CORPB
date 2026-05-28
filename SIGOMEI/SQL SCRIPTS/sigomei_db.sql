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
    CONSTRAINT pk_equipo         PRIMARY KEY (id_equipo),
    CONSTRAINT uq_equipo_serie   UNIQUE (num_serie)
) ENGINE=InnoDB;

CREATE INDEX idx_equipo_tipo       ON equipo (tipo);
CREATE INDEX idx_equipo_criticidad ON equipo (criticidad);
CREATE INDEX idx_equipo_estado     ON equipo (estado_operativo);
CREATE INDEX idx_equipo_activo     ON equipo (activo);

-- ──────────────────────────────────────────────────────────────────────────
-- TABLA: tecnico
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE tecnico (
    id_tecnico     CHAR(36)     NOT NULL,
    nombre         VARCHAR(200) NOT NULL,
    rfc            CHAR(13)     NOT NULL,
    telefono       VARCHAR(20)  NOT NULL,
    correo         VARCHAR(150) NOT NULL,
    fecha_ingreso  DATE         NOT NULL,
    estatus        ENUM('Activo','Inactivo') NOT NULL DEFAULT 'Activo',
    activo         TINYINT(1)   NOT NULL DEFAULT 1,
    creado_en      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_tecnico        PRIMARY KEY (id_tecnico),
    CONSTRAINT uq_tecnico_rfc    UNIQUE (rfc),
    CONSTRAINT uq_tecnico_correo UNIQUE (correo)
) ENGINE=InnoDB;

CREATE INDEX idx_tecnico_estatus ON tecnico (estatus);
CREATE INDEX idx_tecnico_activo  ON tecnico (activo);

-- ──────────────────────────────────────────────────────────────────────────
-- TABLA: certificacion_tecnico
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE certificacion_tecnico (
    id_cert       CHAR(36)     NOT NULL,
    id_tecnico    CHAR(36)     NOT NULL,
    especialidad  VARCHAR(100) NOT NULL,
    nivel         ENUM('I','II','III')     NOT NULL,
    vigencia      DATE         NOT NULL,
    CONSTRAINT pk_cert          PRIMARY KEY (id_cert),
    CONSTRAINT fk_cert_tecnico  FOREIGN KEY (id_tecnico)
                                REFERENCES tecnico(id_tecnico)
                                ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_cert_tecnico     ON certificacion_tecnico (id_tecnico);
CREATE INDEX idx_cert_especialidad ON certificacion_tecnico (especialidad);
CREATE INDEX idx_cert_nivel        ON certificacion_tecnico (nivel);

-- ──────────────────────────────────────────────────────────────────────────
-- TABLA: orden_mantenimiento
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE orden_mantenimiento (
    id_odm               CHAR(36)       NOT NULL,
    id_equipo            CHAR(36)       NOT NULL,
    id_tecnico           CHAR(36)       NOT NULL,
    nota_original        TEXT           NOT NULL,
    fecha_creacion       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_programada     DATE           NOT NULL,
    fecha_inicio         DATE           NULL,
    fecha_estimada_cierre DATE          NOT NULL,
    fecha_cierre         DATE           NULL,
    costo_estimado       DECIMAL(12,2)  NOT NULL,
    costo_real           DECIMAL(12,2)  NULL,
    variacion_porcentual DECIMAL(6,2)   NULL,
    estado               ENUM('En_revision','Programada','En_Ejecucion','En_espera_material','Finalizada','Cancelada') NOT NULL DEFAULT 'En_revision',
    creado_por           CHAR(36)       NOT NULL,
    CONSTRAINT pk_odm          PRIMARY KEY (id_odm),
    CONSTRAINT uq_odm_equipo_fecha UNIQUE (id_equipo, fecha_programada),
    CONSTRAINT fk_odm_equipo   FOREIGN KEY (id_equipo) REFERENCES equipo(id_equipo) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_odm_tecnico  FOREIGN KEY (id_tecnico) REFERENCES tecnico(id_tecnico) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_odm_usuario  FOREIGN KEY (creado_por) REFERENCES usuario(id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT ck_costo_real   CHECK (costo_real IS NULL OR costo_real > 0)
) ENGINE=InnoDB;

CREATE INDEX idx_odm_equipo   ON orden_mantenimiento (id_equipo);
CREATE INDEX idx_odm_tecnico  ON orden_mantenimiento (id_tecnico);
CREATE INDEX idx_odm_estado   ON orden_mantenimiento (estado);
CREATE INDEX idx_odm_fecha_prog ON orden_mantenimiento (fecha_programada);
CREATE INDEX idx_odm_equipo_fecha_estado ON orden_mantenimiento (id_equipo, fecha_programada, estado);

-- ──────────────────────────────────────────────────────────────────────────
-- TABLA: nota_seguimiento
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE nota_seguimiento (
    id_nota     CHAR(36)  NOT NULL,
    id_odm      CHAR(36)  NOT NULL,
    id_usuario  CHAR(36)  NOT NULL,
    contenido   TEXT      NOT NULL,
    creado_en   DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_nota        PRIMARY KEY (id_nota),
    CONSTRAINT fk_nota_odm    FOREIGN KEY (id_odm) REFERENCES orden_mantenimiento(id_odm) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_nota_user   FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_nota_odm ON nota_seguimiento (id_odm);

-- ──────────────────────────────────────────────────────────────────────────
-- TABLA: historial_estado
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE historial_estado (
    id_historial    CHAR(36)     NOT NULL,
    entidad_tipo    ENUM('ODM','Equipo','Tecnico') NOT NULL,
    entidad_id      CHAR(36)     NOT NULL,
    estado_anterior VARCHAR(50)  NULL,
    estado_nuevo    VARCHAR(50)  NOT NULL,
    id_usuario      CHAR(36)     NOT NULL,
    fecha_cambio    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_historial      PRIMARY KEY (id_historial),
    CONSTRAINT fk_hist_usuario   FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_hist_entidad ON historial_estado (entidad_tipo, entidad_id);
CREATE INDEX idx_hist_fecha   ON historial_estado (fecha_cambio);

-- ──────────────────────────────────────────────────────────────────────────
-- TABLA: log_auditoria
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE log_auditoria (
    id_log      CHAR(36)     NOT NULL,
    id_usuario  CHAR(36)     NOT NULL,
    operacion   ENUM('LOGIN','LOGOUT','CREATE','UPDATE','DELETE','READ') NOT NULL,
    entidad     VARCHAR(50)  NOT NULL,
    entidad_id  CHAR(36)     NULL,
    detalle     TEXT         NULL,
    ip_cliente  VARCHAR(45)  NULL,
    timestamp   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_log        PRIMARY KEY (id_log),
    CONSTRAINT fk_log_user   FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_log_usuario   ON log_auditoria (id_usuario);
CREATE INDEX idx_log_timestamp ON log_auditoria (timestamp);
CREATE INDEX idx_log_operacion ON log_auditoria (operacion);


-- ──────────────────────────────────────────────────────────────────────────
-- DATOS MÍNIMOS DE PRUEBA
-- ──────────────────────────────────────────────────────────────────────────

INSERT INTO usuario (id_usuario, correo, password_hash, rol) VALUES
('u-0001-admin', 'admin@sigomei.mx',  '$2b$12$cARvgmX6BVAkYvRFdfKv8Ovii9hCx8bztJPQWd0j3SlSrz3SAUr7q', 'Administrador'),
('u-0002-super', 'super@sigomei.mx',  '$2b$12$60klIvEpO8oNnwXXUdgABOyb1tdQFI4eXjU8vO84Oh67G3oc8Pwka', 'Supervisor'),
('u-0003-super', 'super2@sigomei.mx', '$2b$12$SL0ofEZUaJLrNejwJF427eL6t3FVGoJLKPy2X2gydfwY2yIO/7tlO', 'Supervisor');

INSERT INTO equipo (id_equipo, nombre, tipo, marca, modelo, num_serie, ubicacion, fecha_instalacion, estado_operativo, criticidad) VALUES
('e-001', 'Compresor Norte',       'Mecánica',       'Atlas Copco','GX90',  'SER-001','Planta A', '2022-03-15','Operativo',        'Alta'),
('e-002', 'Bomba de Proceso B1',   'Mecánica',       'Grundfos',  'CM5-6', 'SER-002','Planta B', '2021-07-20','Operativo',        'Media'),
('e-003', 'Tablero Eléctrico T3',  'Eléctrica',      'Siemens',   'S7-300','SER-003','Planta C', '2023-01-10','Crítico',          'Alta'),
('e-004', 'Motor Eléctrico M4',    'Eléctrica',      'WEG',       'W22',   'SER-004','Planta A', '2020-11-05','Fuera de servicio','Media'),
('e-005', 'Intercambiador IC-05',  'Instrumentación','Alfa Laval', 'T50',  'SER-005','Planta B', '2023-06-01','Operativo',        'Baja');

INSERT INTO tecnico (id_tecnico, nombre, rfc, telefono, correo, fecha_ingreso, estatus) VALUES
('t-001','Carlos Mendoza Ruiz',    'MERC850101ABC','9211234567','c.mendoza@empresa.mx','2020-01-15','Activo'),
('t-002','Ana Pérez Torres',       'PETA900201XYZ','9219876543','a.perez@empresa.mx',  '2019-06-01','Activo'),
('t-003','Luis García López',      'GALL880315DEF','9218765432','l.garcia@empresa.mx', '2021-03-10','Activo'),
('t-004','María Sánchez Vidal',    'SAVM950720GHI','9217654321','m.sanchez@empresa.mx','2022-08-20','Inactivo'),
('t-005','Roberto Jiménez Mora',   'JIMR780505JKL','9216543210','r.jimenez@empresa.mx','2018-11-30','Activo');

INSERT INTO certificacion_tecnico (id_cert, id_tecnico, especialidad, nivel, vigencia) VALUES
('c-001','t-001','Mecánica',        'II', '2027-12-31'),
('c-002','t-002','Eléctrica',       'III','2026-09-30'),
('c-003','t-003','Instrumentación', 'I',  '2026-06-30'),
('c-004','t-003','Mecánica',        'II', '2027-03-31'),
('c-005','t-005','Mecánica',        'III','2028-01-31');

INSERT INTO orden_mantenimiento (id_odm, id_equipo, id_tecnico, nota_original, fecha_programada, fecha_estimada_cierre, costo_estimado, estado, creado_por) VALUES
('odm-001','e-001','t-001','Mantenimiento preventivo semestral compresor norte', '2026-06-10','2026-06-12',8500.00,'Programada','u-0002-super'),
('odm-002','e-003','t-002','Revisión de tablero eléctrico T3 post-falla', '2026-06-05','2026-06-07',12000.00,'En_Ejecucion','u-0002-super');
