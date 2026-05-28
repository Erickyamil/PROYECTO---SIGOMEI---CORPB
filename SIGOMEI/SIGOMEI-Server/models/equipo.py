# models/equipo.py
# Modelo de datos para Equipo Industrial (documentación/tipado)
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Equipo:
    id_equipo: str
    nombre: str
    tipo: str
    marca: str
    modelo: str
    num_serie: str
    ubicacion: str
    fecha_instalacion: date
    estado_operativo: str = "Operativo"
    criticidad: str = "Media"
    activo: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> "Equipo":
        return cls(
            id_equipo=d["id_equipo"],
            nombre=d["nombre"],
            tipo=d["tipo"],
            marca=d["marca"],
            modelo=d["modelo"],
            num_serie=d["num_serie"],
            ubicacion=d["ubicacion"],
            fecha_instalacion=d["fecha_instalacion"],
            estado_operativo=d.get("estado_operativo", "Operativo"),
            criticidad=d.get("criticidad", "Media"),
            activo=bool(d.get("activo", True)),
        )
