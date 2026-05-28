import base64
import bcrypt
import csv
import io
import secrets

from services.validators import (
    validar_tecnico_activo,
    validar_especialidad,
    validar_criticidad,
    validar_fechas_odm,
    validar_equipo_disponible,
    validar_carga,
    validar_transicion,
    validar_costo_cierre,
)


class ServiceLayer:
    def __init__(self, repository):
        self.repo = repository

    def verificar_credenciales(self, correo: str, password_hash_recibido: str) -> dict:
        if not isinstance(correo, str) or not isinstance(password_hash_recibido, str):
            return {"status": "ERR_AUTH", "message": "Credenciales invalidas.", "data": None}

        usuario = self.repo.obtener_usuario_por_correo(correo)
        if not usuario:
            return {"status": "ERR_AUTH", "message": "Credenciales invalidas.", "data": None}

        password_bcrypt_db = usuario.get("password_hash", "")
        try:
            credenciales_validas = bcrypt.checkpw(
                password_hash_recibido.encode("utf-8"),
                password_bcrypt_db.encode("utf-8"),
            )
        except ValueError:
            return {"status": "ERR_AUTH", "message": "Credenciales invalidas.", "data": None}

        if not credenciales_validas:
            return {"status": "ERR_AUTH", "message": "Credenciales invalidas.", "data": None}

        return {
            "status": "OK",
            "message": "Inicio de sesion exitoso.",
            "data": {
                "id_usuario": usuario["id_usuario"],
                "rol": usuario["rol"],
                "token": secrets.token_hex(32),
            },
        }

    def crear_odm(self, payload: dict, id_usuario_creador: str) -> dict:
        if not id_usuario_creador:
            return {"status": "ERR_AUTH", "message": "Sesion invalida o expirada.", "data": None}

        tecnico = self.repo.obtener_tecnico(payload["id_tecnico"])
        equipo = self.repo.obtener_equipo(payload["id_equipo"])
        odms_activas = self.repo.listar_odms_activas()

        if not tecnico:
            return {"status": "ERR_NOT_FOUND", "message": "El tecnico especificado no existe.", "data": None}
        if not equipo:
            return {"status": "ERR_NOT_FOUND", "message": "El equipo especificado no existe.", "data": None}

        try:
            validar_tecnico_activo(tecnico)
            validar_especialidad(tecnico, equipo)
            validar_criticidad(equipo, tecnico)
            validar_fechas_odm(payload["fecha_programada"], payload["fecha_estimada_cierre"])
            validar_equipo_disponible(payload["id_equipo"], payload["fecha_programada"], odms_activas)
            validar_carga(tecnico, odms_activas)
        except Exception as exc:
            return {"status": "ERR_BUSINESS", "message": str(exc), "data": None}

        id_nueva_odm = self.repo.guardar_odm(payload, id_usuario_creador)
        return {
            "status": "OK",
            "message": "Orden de Mantenimiento creada exitosamente.",
            "data": {"id_odm": id_nueva_odm},
        }

    def actualizar_estado_odm(self, id_odm: str, nuevo_estado: str, id_usuario: str, costo_real: float = None) -> dict:
        """
        CORRECCIÓN DEF003:
          Si costo_estimado es 0 o None, se evita la ZeroDivisionError que causaba
          un HTTP 500 sin mensaje amigable. Se retorna ERR_BUSINESS con mensaje claro.
        """
        odm = self.repo.obtener_odm(id_odm)
        if not odm:
            return {"status": "ERR_NOT_FOUND", "message": "La ODM especificada no existe.", "data": None}

        try:
            validar_transicion(odm["estado"], nuevo_estado)
            if nuevo_estado == "Finalizada":
                validar_costo_cierre(costo_real)
                costo_estimado = float(odm.get("costo_estimado") or 0)
                # DEF003: guardia contra división por cero
                if costo_estimado == 0:
                    raise ValueError(
                        "El costo estimado de la ODM es 0; no es posible calcular la variacion porcentual. "
                        "Corrija el costo estimado antes de finalizar la orden."
                    )
                variacion = ((costo_real - costo_estimado) / costo_estimado) * 100
                self.repo.actualizar_estado_y_costo(id_odm, nuevo_estado, costo_real, round(variacion, 2), id_usuario)
            else:
                self.repo.actualizar_estado_simple(id_odm, nuevo_estado, id_usuario)
            return {"status": "OK", "message": f"Estado de ODM actualizado con exito a {nuevo_estado}.", "data": None}
        except Exception as exc:
            return {"status": "ERR_BUSINESS", "message": str(exc), "data": None}

    def obtener_odm(self, id_odm: str) -> dict:
        odm = self.repo.obtener_odm(id_odm)
        if not odm:
            return {"status": "ERR_NOT_FOUND", "message": "ODM no encontrada.", "data": None}
        return {"status": "OK", "message": "Exito", "data": odm}

    def listar_odms(self) -> dict:
        return {"status": "OK", "message": "Exito", "data": self.repo.listar_todas_las_odms()}

    def filtrar_odms(self, fecha_inicio: str, fecha_fin: str, estado: str = None) -> dict:
        return {"status": "OK", "message": "Exito", "data": self.repo.filtrar_odms(fecha_inicio, fecha_fin, estado)}

    def agregar_nota_odm(self, id_odm: str, nota_adicional: str, id_usuario: str) -> dict:
        if not self.repo.obtener_odm(id_odm):
            return {"status": "ERR_NOT_FOUND", "message": "ODM no encontrada.", "data": None}
        if not nota_adicional or not nota_adicional.strip():
            return {"status": "ERR_BUSINESS", "message": "La nota no puede estar vacia.", "data": None}
        self.repo.agregar_nota_odm(id_odm, id_usuario, nota_adicional.strip())
        return {"status": "OK", "message": "Nota agregada correctamente.", "data": None}

    def reasignar_tecnico_odm(self, id_odm: str, id_tecnico_nuevo: str, id_usuario: str) -> dict:
        odm = self.repo.obtener_odm(id_odm)
        if not odm:
            return {"status": "ERR_NOT_FOUND", "message": "ODM no encontrada.", "data": None}
        if odm.get("estado") in {"Finalizada", "Cancelada"}:
            return {"status": "ERR_BUSINESS", "message": "No se puede reasignar una ODM terminal.", "data": None}

        tecnico = self.repo.obtener_tecnico(id_tecnico_nuevo)
        equipo = self.repo.obtener_equipo(odm["id_equipo"])
        if not tecnico:
            return {"status": "ERR_NOT_FOUND", "message": "El tecnico especificado no existe.", "data": None}
        if not equipo:
            return {"status": "ERR_NOT_FOUND", "message": "El equipo especificado no existe.", "data": None}

        odms_activas = [
            orden for orden in self.repo.listar_odms_activas()
            if orden.get("id_odm") != id_odm
        ]
        try:
            validar_tecnico_activo(tecnico)
            validar_especialidad(tecnico, equipo)
            validar_criticidad(equipo, tecnico)
            validar_carga(tecnico, odms_activas)
        except Exception as exc:
            return {"status": "ERR_BUSINESS", "message": str(exc), "data": None}

        self.repo.reasignar_tecnico_odm(id_odm, id_tecnico_nuevo, id_usuario)
        return {"status": "OK", "message": "Tecnico reasignado correctamente.", "data": None}

    def resumen_costos(self, id_odm: str) -> dict:
        odm = self.repo.obtener_odm(id_odm)
        if not odm:
            return {"status": "ERR_NOT_FOUND", "message": "ODM no encontrada.", "data": None}
        if odm.get("estado") != "Finalizada":
            return {"status": "ERR_BUSINESS", "message": "La ODM debe estar Finalizada.", "data": None}

        estimado = float(odm.get("costo_estimado") or 0)
        real = float(odm.get("costo_real") or 0)
        variacion = odm.get("variacion_porcentual")
        if variacion is None and estimado:
            variacion = ((real - estimado) / estimado) * 100

        return {
            "status": "OK",
            "message": "Exito",
            "data": {
                "costo_estimado": estimado,
                "costo_real": real,
                "variacion_pct": float(variacion or 0),
            },
        }

    def crear_tecnico(self, payload: dict) -> dict:
        if self.repo.existe_rfc_tecnico(payload["rfc"]):
            return {"status": "ERR_BUSINESS", "message": "El RFC ya se encuentra registrado (Unicidad).", "data": None}
        id_tecnico = self.repo.guardar_tecnico(payload)
        return {"status": "OK", "message": "Tecnico registrado exitosamente.", "data": {"id_tecnico": id_tecnico}}

    def actualizar_tecnico(self, payload: dict) -> dict:
        id_tecnico = payload["id_tecnico"]
        if not self.repo.obtener_tecnico(id_tecnico):
            return {"status": "ERR_NOT_FOUND", "message": "Tecnico no encontrado.", "data": None}
        self.repo.actualizar_tecnico(payload)
        return {"status": "OK", "message": "Tecnico actualizado correctamente.", "data": None}

    def cambiar_estatus_tecnico(self, id_tecnico: str, nuevo_estatus: str) -> dict:
        tecnico = self.repo.obtener_tecnico(id_tecnico)
        if not tecnico:
            return {"status": "ERR_NOT_FOUND", "message": "Tecnico no encontrado.", "data": None}
        self.repo.actualizar_estatus_tecnico(id_tecnico, nuevo_estatus)
        return {"status": "OK", "message": "Estatus del tecnico actualizado correctamente.", "data": None}

    def obtener_tecnico(self, id_tecnico: str) -> dict:
        tecnico = self.repo.obtener_tecnico(id_tecnico)
        if not tecnico:
            return {"status": "ERR_NOT_FOUND", "message": "Tecnico no encontrado.", "data": None}
        return {"status": "OK", "message": "Exito", "data": tecnico}

    def buscar_tecnicos(self, filtros: dict = None) -> dict:
        return {"status": "OK", "message": "Exito", "data": self.repo.buscar_tecnicos(filtros or {})}

    def carga_tecnico(self, id_tecnico: str) -> dict:
        if not self.repo.obtener_tecnico(id_tecnico):
            return {"status": "ERR_NOT_FOUND", "message": "Tecnico no encontrado.", "data": None}
        odms = self.repo.carga_tecnico(id_tecnico)
        return {"status": "OK", "message": "Exito", "data": odms}

    def crear_equipo(self, payload: dict) -> dict:
        if self.repo.existe_num_serie_equipo(payload["num_serie"]):
            return {"status": "ERR_BUSINESS", "message": "Ya existe un equipo con ese numero de serie (Unicidad).", "data": None}
        id_equipo = self.repo.guardar_equipo(payload)
        return {"status": "OK", "message": "Equipo registrado exitosamente.", "data": {"id_equipo": id_equipo}}

    def actualizar_equipo(self, payload: dict) -> dict:
        id_equipo = payload["id_equipo"]
        if not self.repo.obtener_equipo(id_equipo):
            return {"status": "ERR_NOT_FOUND", "message": "Equipo no encontrado.", "data": None}
        self.repo.actualizar_equipo(payload)
        return {"status": "OK", "message": "Equipo actualizado correctamente.", "data": None}

    def eliminar_equipo(self, id_equipo: str) -> dict:
        """
        Lógica de eliminación en tres casos:
          1. Sin ODMs activas y sin historial → eliminación física.
          2. Con ODMs activas → bloqueado, no se permite ninguna acción.
          3. Sin ODMs activas pero con historial → baja lógica (activo=0).
        """
        equipo = self.repo.obtener_equipo(id_equipo)
        if not equipo:
            return {"status": "ERR_NOT_FOUND", "message": "Equipo no encontrado.", "data": None}

        # Verificar órdenes activas
        odms_activas = self.repo.listar_odms_activas()
        odms_activas_equipo = [o for o in odms_activas if o.get("id_equipo") == id_equipo]
        if odms_activas_equipo:
            ids = ", ".join(o.get("id_odm", "?") for o in odms_activas_equipo)
            return {
                "status": "ERR_BUSINESS",
                "message": (
                    f"No es posible eliminar el equipo: tiene {len(odms_activas_equipo)} "
                    f"orden(es) activa(s) (IDs: {ids}). "
                    f"Finalice o cancele esas órdenes antes de continuar."
                ),
                "data": None,
            }

        # Verificar historial (ODMs finalizadas/canceladas)
        historial = self.repo.historial_equipo(id_equipo)
        if historial:
            # Tiene historial → baja lógica para preservar trazabilidad
            self.repo.marcar_inactivo_equipo(id_equipo)
            return {
                "status": "OK",
                "message": "El equipo tiene historial de órdenes; se aplicó baja lógica para preservar la trazabilidad.",
                "data": {"tipo_baja": "logica"},
            }
        else:
            # Sin historial → eliminación física
            self.repo.eliminar_equipo_fisico(id_equipo)
            return {
                "status": "OK",
                "message": "Equipo eliminado permanentemente.",
                "data": {"tipo_baja": "fisica"},
            }

    def baja_equipo(self, id_equipo: str) -> dict:
        """Alias de compatibilidad — delega a eliminar_equipo."""
        return self.eliminar_equipo(id_equipo)

    def obtener_equipo(self, id_equipo: str) -> dict:
        equipo = self.repo.obtener_equipo(id_equipo)
        if not equipo:
            return {"status": "ERR_NOT_FOUND", "message": "Equipo no encontrado.", "data": None}
        return {"status": "OK", "message": "Exito", "data": equipo}

    def listar_equipos(self, filtros: dict = None) -> dict:
        return {"status": "OK", "message": "Exito", "data": self.repo.listar_equipos(filtros or {})}

    def historial_equipo(self, id_equipo: str) -> dict:
        if not self.repo.obtener_equipo(id_equipo):
            return {"status": "ERR_NOT_FOUND", "message": "Equipo no encontrado.", "data": None}
        return {"status": "OK", "message": "Exito", "data": {"odms": self.repo.historial_equipo(id_equipo)}}

    def reporte_desempeno(self, id_tecnico: str, fecha_inicio: str, fecha_fin: str) -> dict:
        if not self.repo.obtener_tecnico(id_tecnico):
            return {"status": "ERR_NOT_FOUND", "message": "Tecnico no encontrado.", "data": None}
        data = self.repo.reporte_desempeno(id_tecnico, fecha_inicio, fecha_fin)
        return {"status": "OK", "message": "Exito", "data": data}

    def reporte_equipos_criticos(self) -> dict:
        return {"status": "OK", "message": "Exito", "data": self.repo.reporte_equipos_criticos()}

    def exportar_csv(self, tipo_reporte: str, parametros: dict = None) -> dict:
        parametros = parametros or {}
        if tipo_reporte == "odms":
            rows = self.repo.filtrar_odms(
                parametros.get("fecha_inicio"),
                parametros.get("fecha_fin"),
                parametros.get("estado"),
            )
        elif tipo_reporte == "equipos_criticos":
            rows = self.repo.reporte_equipos_criticos()
        elif tipo_reporte == "desempeno_tecnicos":
            id_tecnico = parametros.get("id_tecnico")
            if id_tecnico:
                rows = [self.repo.reporte_desempeno(
                    id_tecnico,
                    parametros.get("fecha_inicio"),
                    parametros.get("fecha_fin"),
                )]
            else:
                rows = self.repo.reporte_desempeno_tecnicos(
                    parametros.get("fecha_inicio"),
                    parametros.get("fecha_fin"),
                )
        else:
            return {"status": "ERR_BAD_REQUEST", "message": "Tipo de reporte no soportado.", "data": None}

        contenido = self._rows_to_csv(rows)
        return {
            "status": "OK",
            "message": "CSV generado.",
            "data": {"contenido_base64": base64.b64encode(contenido).decode("ascii")},
        }

    def _rows_to_csv(self, rows: list) -> bytes:
        output = io.StringIO()
        if rows:
            fieldnames = sorted({key for row in rows for key in row.keys()})
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        else:
            output.write("sin_datos\n")
        return output.getvalue().encode("utf-8-sig")
