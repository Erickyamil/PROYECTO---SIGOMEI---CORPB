# utils/session.py
# Administra la sesión activa del usuario en el cliente

class Session:
    """Singleton que guarda los datos del usuario autenticado."""
    _instancia = None

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia._reset()
        return cls._instancia

    def _reset(self):
        self.token: str | None = None
        self.rol: str | None = None
        self.nombre: str | None = None
        self.correo: str | None = None

    def iniciar(self, token: str, rol: str, nombre: str, correo: str):
        self.token = token
        self.rol = rol
        self.nombre = nombre
        self.correo = correo

    def cerrar(self):
        self._reset()

    @property
    def activa(self) -> bool:
        return self.token is not None

    @property
    def es_admin(self) -> bool:
        return self.rol == "Administrador"

    @property
    def es_supervisor(self) -> bool:
        return self.rol == "Supervisor"
