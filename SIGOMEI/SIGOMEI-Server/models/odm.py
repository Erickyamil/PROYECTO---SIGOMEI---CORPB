# models/odm.py
# Modelo de datos para Orden de Mantenimiento (ODM)
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class NotaSeguimiento:
    id_nota: str
    contenido: str
    creado_en: str
    id_usuario: str


@dataclass
class OrdenMantenimiento:
    id_odm: str
    id_equipo: str
    id_tecnico: str
    nota_original: str
    fecha_programada: date
    fecha_estimada_cierre: date
    costo_estimado: float
    estado: str = "En_revision"
    creado_por: str = ""
    fecha_creacion: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_cierre: Optional[date] = None
    costo_real: Optional[float] = None
    variacion_porcentual: Optional[float] = None
    notas: List[NotaSeguimiento] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "OrdenMantenimiento":
        notas = [
            NotaSeguimiento(
                id_nota=n["id_nota"],
                contenido=n["contenido"],
                creado_en=str(n.get("creado_en", "")),
                id_usuario=n.get("id_usuario", ""),
            )
            for n in d.get("notas", [])
        ]
        return cls(
            id_odm=d["id_odm"],
            id_equipo=d["id_equipo"],
            id_tecnico=d["id_tecnico"],
            nota_original=d.get("nota_original", ""),
            fecha_programada=d["fecha_programada"],
            fecha_estimada_cierre=d["fecha_estimada_cierre"],
            costo_estimado=float(d.get("costo_estimado", 0)),
            estado=d.get("estado", "En_revision"),
            creado_por=d.get("creado_por", ""),
            fecha_creacion=d.get("fecha_creacion"),
            fecha_inicio=d.get("fecha_inicio"),
            fecha_cierre=d.get("fecha_cierre"),
            costo_real=float(d["costo_real"]) if d.get("costo_real") else None,
            variacion_porcentual=float(d["variacion_porcentual"]) if d.get("variacion_porcentual") else None,
            notas=notas,
        )
