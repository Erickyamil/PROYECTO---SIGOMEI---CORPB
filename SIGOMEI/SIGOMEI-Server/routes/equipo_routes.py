# routes/equipo_routes.py
# Registro de rutas de Equipo — usado por el dispatcher del socket server
# Las rutas reales están en SIGOMEISocketServer._dispatch; este módulo
# expone las acciones disponibles para documentación y registro.

RUTAS_EQUIPO = [
    "CREAR_EQUIPO",
    "ACTUALIZAR_EQUIPO",
    "BAJA_EQUIPO",
    "OBTENER_EQUIPO",
    "LISTAR_EQUIPOS",
    "HISTORIAL_EQUIPO",
]
