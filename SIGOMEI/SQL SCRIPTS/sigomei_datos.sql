-- ──────────────────────────────────────────────────────────────────────────
-- DATOS MÍNIMOS DE PRUEBA
-- ──────────────────────────────────────────────────────────────────────────

USE sigomei_db;

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