# models/tecnico.py
# Modelo de datos para Técnico
from dataclasses import dataclass, field
from datetime import date
from typing import List


@dataclass
class Certificacion:
    especialidad: str
    nivel: str
    vigencia: str = "2099-12-31"


@dataclass
class Tecnico:
    id_tecnico: str
    nombre: str
    rfc: str
    telefono: str
    correo: str
    fecha_ingreso: date
    estatus: str = "Activo"
    activo: bool = True
    certificaciones: List[Certificacion] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Tecnico":
        certs = [
            Certificacion(
                especialidad=c["especialidad"],
                nivel=c["nivel"],
                vigencia=c.get("vigencia", "2099-12-31"),
            )
            for c in d.get("certificaciones", [])
        ]
        return cls(
            id_tecnico=d["id_tecnico"],
            nombre=d["nombre"],
            rfc=d["rfc"],
            telefono=d["telefono"],
            correo=d["correo"],
            fecha_ingreso=d["fecha_ingreso"],
            estatus=d.get("estatus", "Activo"),
            activo=bool(d.get("activo", True)),
            certificaciones=certs,
        )
