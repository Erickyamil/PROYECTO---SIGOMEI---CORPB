# services/schemas.py
# Esquemas de validación de payloads para cada acción del protocolo.
# Se usan para documentar los campos requeridos; la validación de negocio
# está en validators.py.

SCHEMA_CREAR_EQUIPO = {
    "required": ["nombre", "tipo", "marca", "modelo", "num_serie",
                 "ubicacion", "fecha_instalacion"],
    "optional": ["estado_operativo", "criticidad"],
}

SCHEMA_CREAR_TECNICO = {
    "required": ["nombre", "rfc", "telefono", "correo",
                 "fecha_ingreso", "certificaciones"],
    "optional": ["estatus"],
}

SCHEMA_CREAR_ODM = {
    "required": ["id_equipo", "id_tecnico", "nota_original",
                 "fecha_programada", "fecha_estimada_cierre", "costo_estimado"],
    "optional": [],
}

SCHEMA_ACTUALIZAR_ESTADO_ODM = {
    "required": ["id_odm", "nuevo_estado"],
    "optional": ["costo_real"],
}

SCHEMA_LOGIN = {
    "required": ["correo", "password_hash"],
    "optional": [],
}
