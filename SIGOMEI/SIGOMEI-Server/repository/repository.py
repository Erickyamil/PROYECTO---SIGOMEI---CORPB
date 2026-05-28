import uuid

import mysql.connector


class MySQLRepository:
    def __init__(self, db_config: dict):
        self.config = db_config

    def _get_connection(self):
        return mysql.connector.connect(**self.config)

    # ─── Generación de IDs secuenciales ──────────────────────────────────────

    def _generar_id_equipo(self, cursor) -> str:
        """Genera un ID secuencial con formato E-NNN (ej. E-001, E-012, E-123)."""
        cursor.execute("SELECT id_equipo FROM equipo ORDER BY creado_en DESC, id_equipo DESC")
        filas = cursor.fetchall()
        max_num = 0
        for fila in filas:
            id_val = fila["id_equipo"] if isinstance(fila, dict) else fila[0]
            if id_val and id_val.upper().startswith("E-"):
                try:
                    num = int(id_val[2:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        return f"e-{max_num + 1:03d}"

    def _generar_id_tecnico(self, cursor) -> str:
        """Genera un ID secuencial con formato T-NNN (ej. T-001, T-012, T-123)."""
        cursor.execute("SELECT id_tecnico FROM tecnico ORDER BY creado_en DESC, id_tecnico DESC")
        filas = cursor.fetchall()
        max_num = 0
        for fila in filas:
            id_val = fila["id_tecnico"] if isinstance(fila, dict) else fila[0]
            if id_val and id_val.upper().startswith("T-"):
                try:
                    num = int(id_val[2:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        return f"T-{max_num + 1:03d}"

    def _generar_id_odm(self, cursor) -> str:
        """Genera un ID secuencial con formato ODM-NNN (ej. ODM-001, ODM-012, ODM-123)."""
        cursor.execute(
            "SELECT id_odm FROM orden_mantenimiento ORDER BY fecha_creacion DESC, id_odm DESC"
        )
        filas = cursor.fetchall()
        max_num = 0
        for fila in filas:
            id_val = fila["id_odm"] if isinstance(fila, dict) else fila[0]
            if id_val and id_val.upper().startswith("ODM-"):
                try:
                    num = int(id_val[4:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
        return f"ODM-{max_num + 1:03d}"

    def obtener_usuario_por_correo(self, correo: str) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id_usuario, correo, password_hash, rol, activo
                FROM usuario
                WHERE correo = %s AND activo = 1
                """,
                (correo,),
            )
            return cursor.fetchone() or {}
        finally:
            cursor.close()
            conn.close()

    def obtener_tecnico(self, id_tecnico: str) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id_tecnico, nombre, rfc, telefono, correo, fecha_ingreso, estatus
                FROM tecnico
                WHERE id_tecnico = %s AND activo = 1
                """,
                (id_tecnico,),
            )
            tecnico = cursor.fetchone()
            if not tecnico:
                return {}
            tecnico["certificaciones"] = self._certificaciones_tecnico(cursor, id_tecnico)
            return tecnico
        finally:
            cursor.close()
            conn.close()

    def buscar_tecnicos(self, filtros: dict) -> list:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT DISTINCT t.id_tecnico, t.nombre, t.rfc, t.telefono,
                       t.correo, t.fecha_ingreso, t.estatus
                FROM tecnico t
                LEFT JOIN certificacion_tecnico c ON c.id_tecnico = t.id_tecnico
                WHERE t.activo = 1
            """
            params = []
            if filtros.get("especialidad"):
                sql += " AND c.especialidad = %s"
                params.append(filtros["especialidad"])
            if filtros.get("nivel_cert"):
                sql += " AND c.nivel = %s"
                params.append(filtros["nivel_cert"])
            sql += " ORDER BY t.nombre"
            cursor.execute(sql, tuple(params))
            tecnicos = cursor.fetchall()
            for tecnico in tecnicos:
                tecnico["certificaciones"] = self._certificaciones_tecnico(cursor, tecnico["id_tecnico"])
            return tecnicos
        finally:
            cursor.close()
            conn.close()

    def guardar_tecnico(self, payload: dict) -> str:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            id_tecnico = self._generar_id_tecnico(cursor)
            cursor.execute(
                """
                INSERT INTO tecnico
                (id_tecnico, nombre, rfc, telefono, correo, fecha_ingreso, estatus)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    id_tecnico,
                    payload["nombre"],
                    payload["rfc"],
                    payload["telefono"],
                    payload["correo"],
                    payload["fecha_ingreso"],
                    payload.get("estatus", "Activo"),
                ),
            )
            self._guardar_certificaciones(cursor, id_tecnico, payload.get("certificaciones", []))
            conn.commit()
            return id_tecnico
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def actualizar_tecnico(self, payload: dict) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE tecnico
                SET nombre = %s, rfc = %s, telefono = %s, correo = %s, fecha_ingreso = %s
                WHERE id_tecnico = %s
                """,
                (
                    payload["nombre"],
                    payload["rfc"],
                    payload["telefono"],
                    payload["correo"],
                    payload["fecha_ingreso"],
                    payload["id_tecnico"],
                ),
            )
            cursor.execute("DELETE FROM certificacion_tecnico WHERE id_tecnico = %s", (payload["id_tecnico"],))
            self._guardar_certificaciones(cursor, payload["id_tecnico"], payload.get("certificaciones", []))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def actualizar_estatus_tecnico(self, id_tecnico: str, nuevo_estatus: str) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE tecnico SET estatus = %s WHERE id_tecnico = %s",
                (nuevo_estatus, id_tecnico),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def carga_tecnico(self, id_tecnico: str) -> list:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id_odm, id_equipo, estado, fecha_programada
                FROM orden_mantenimiento
                WHERE id_tecnico = %s
                  AND estado NOT IN ('Finalizada', 'Cancelada')
                ORDER BY fecha_programada
                """,
                (id_tecnico,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def existe_rfc_tecnico(self, rfc: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM tecnico WHERE rfc = %s LIMIT 1", (rfc,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()
            conn.close()

    def obtener_equipo(self, id_equipo: str) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id_equipo, nombre, tipo, marca, modelo, num_serie,
                       ubicacion, fecha_instalacion, estado_operativo, criticidad
                FROM equipo
                WHERE id_equipo = %s AND activo = 1
                """,
                (id_equipo,),
            )
            return cursor.fetchone() or {}
        finally:
            cursor.close()
            conn.close()

    def listar_equipos(self, filtros: dict) -> list:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT id_equipo, nombre, tipo, marca, modelo, num_serie,
                       ubicacion, fecha_instalacion, estado_operativo, criticidad
                FROM equipo
                WHERE activo = 1
            """
            params = []
            for key in ("id_equipo", "tipo", "criticidad", "estado_operativo"):
                if filtros.get(key):
                    sql += f" AND {key} = %s"
                    params.append(filtros[key])
            if filtros.get("ubicacion"):
                sql += " AND ubicacion LIKE %s"
                params.append(f"%{filtros['ubicacion']}%")
            sql += " ORDER BY nombre"
            cursor.execute(sql, tuple(params))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def guardar_equipo(self, payload: dict) -> str:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            id_equipo = self._generar_id_equipo(cursor)
            cursor.execute(
                """
                INSERT INTO equipo
                (
                    id_equipo, nombre, tipo, marca, modelo, num_serie,
                    ubicacion, fecha_instalacion, estado_operativo, criticidad
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    id_equipo,
                    payload["nombre"],
                    payload["tipo"],
                    payload["marca"],
                    payload["modelo"],
                    payload["num_serie"],
                    payload["ubicacion"],
                    payload["fecha_instalacion"],
                    payload.get("estado_operativo", "Operativo"),
                    payload.get("criticidad", "Media"),
                ),
            )
            conn.commit()
            return id_equipo
        finally:
            cursor.close()
            conn.close()

    def actualizar_equipo(self, payload: dict) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE equipo
                SET nombre = %s, tipo = %s, marca = %s, modelo = %s,
                    num_serie = %s, ubicacion = %s, fecha_instalacion = %s,
                    estado_operativo = %s, criticidad = %s
                WHERE id_equipo = %s
                """,
                (
                    payload["nombre"],
                    payload["tipo"],
                    payload["marca"],
                    payload["modelo"],
                    payload["num_serie"],
                    payload["ubicacion"],
                    payload["fecha_instalacion"],
                    payload.get("estado_operativo", "Operativo"),
                    payload.get("criticidad", "Media"),
                    payload["id_equipo"],
                ),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def marcar_inactivo_equipo(self, id_equipo: str) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE equipo
                SET activo = 0, estado_operativo = 'Inactivo'
                WHERE id_equipo = %s
                """,
                (id_equipo,),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def eliminar_equipo_fisico(self, id_equipo: str) -> None:
        """Elimina el equipo permanentemente de la base de datos."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM equipo WHERE id_equipo = %s", (id_equipo,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def existe_num_serie_equipo(self, num_serie: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM equipo WHERE num_serie = %s LIMIT 1", (num_serie,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()
            conn.close()

    def historial_equipo(self, id_equipo: str) -> list:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id_odm, id_tecnico, estado, fecha_programada,
                       costo_estimado, costo_real
                FROM orden_mantenimiento
                WHERE id_equipo = %s
                ORDER BY fecha_programada DESC
                """,
                (id_equipo,),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def listar_odms_activas(self) -> list:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id_odm, id_equipo, id_tecnico, fecha_programada, estado
                FROM orden_mantenimiento
                WHERE estado NOT IN ('Cancelada', 'Finalizada')
                """
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def guardar_odm(self, payload: dict, id_usuario_creador: str) -> str:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            id_odm = self._generar_id_odm(cursor)
            cursor.execute(
                """
                INSERT INTO orden_mantenimiento
                (
                    id_odm, id_equipo, id_tecnico, nota_original,
                    fecha_programada, fecha_estimada_cierre,
                    costo_estimado, estado, creado_por
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'En_revision', %s)
                """,
                (
                    id_odm,
                    payload["id_equipo"],
                    payload["id_tecnico"],
                    payload["nota_original"],
                    payload["fecha_programada"],
                    payload["fecha_estimada_cierre"],
                    payload["costo_estimado"],
                    id_usuario_creador,
                ),
            )
            conn.commit()
            return id_odm
        finally:
            cursor.close()
            conn.close()

    def obtener_odm(self, id_odm: str) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id_odm, id_equipo, id_tecnico, nota_original, fecha_creacion,
                       fecha_programada, fecha_inicio, fecha_estimada_cierre,
                       fecha_cierre, costo_estimado, costo_real,
                       variacion_porcentual, estado, creado_por
                FROM orden_mantenimiento
                WHERE id_odm = %s
                """,
                (id_odm,),
            )
            odm = cursor.fetchone() or {}
            if odm:
                cursor.execute(
                    """
                    SELECT id_nota, contenido, creado_en, id_usuario
                    FROM nota_seguimiento
                    WHERE id_odm = %s
                    ORDER BY creado_en
                    """,
                    (id_odm,),
                )
                odm["notas"] = cursor.fetchall()
            return odm
        finally:
            cursor.close()
            conn.close()

    def listar_todas_las_odms(self) -> list:
        return self.filtrar_odms(None, None, None)

    def filtrar_odms(self, fecha_inicio: str | None, fecha_fin: str | None, estado: str | None = None) -> list:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT id_odm, id_equipo, id_tecnico, fecha_programada,
                       fecha_estimada_cierre, costo_estimado, costo_real,
                       variacion_porcentual, estado, creado_por
                FROM orden_mantenimiento
                WHERE 1 = 1
            """
            params = []
            if fecha_inicio:
                sql += " AND fecha_programada >= %s"
                params.append(fecha_inicio)
            if fecha_fin:
                sql += " AND fecha_programada <= %s"
                params.append(fecha_fin)
            if estado:
                sql += " AND estado = %s"
                params.append(estado)
            sql += " ORDER BY fecha_programada DESC, id_odm"
            cursor.execute(sql, tuple(params))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def actualizar_estado_simple(self, id_odm: str, nuevo_estado: str, id_usuario: str) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            estado_anterior = self._obtener_estado_odm(cursor, id_odm)
            extra_set = ", fecha_inicio = CURDATE()" if nuevo_estado == "En_Ejecucion" else ""
            cursor.execute(
                f"UPDATE orden_mantenimiento SET estado = %s{extra_set} WHERE id_odm = %s",
                (nuevo_estado, id_odm),
            )
            self._guardar_historial(cursor, "ODM", id_odm, estado_anterior, nuevo_estado, id_usuario)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def actualizar_estado_y_costo(
        self,
        id_odm: str,
        nuevo_estado: str,
        costo_real: float,
        variacion: float,
        id_usuario: str,
    ) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            estado_anterior = self._obtener_estado_odm(cursor, id_odm)
            cursor.execute(
                """
                UPDATE orden_mantenimiento
                SET estado = %s,
                    costo_real = %s,
                    variacion_porcentual = %s,
                    fecha_cierre = CURDATE()
                WHERE id_odm = %s
                """,
                (nuevo_estado, costo_real, variacion, id_odm),
            )
            self._guardar_historial(cursor, "ODM", id_odm, estado_anterior, nuevo_estado, id_usuario)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def agregar_nota_odm(self, id_odm: str, id_usuario: str, contenido: str) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO nota_seguimiento (id_nota, id_odm, id_usuario, contenido)
                VALUES (%s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), id_odm, id_usuario, contenido),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    def reasignar_tecnico_odm(self, id_odm: str, id_tecnico_nuevo: str, id_usuario: str) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE orden_mantenimiento SET id_tecnico = %s WHERE id_odm = %s",
                (id_tecnico_nuevo, id_odm),
            )
            self._guardar_historial(cursor, "ODM", id_odm, "Reasignacion", id_tecnico_nuevo, id_usuario)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def reporte_desempeno(self, id_tecnico: str, fecha_inicio: str | None, fecha_fin: str | None) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT
                    COUNT(*) AS num_odm,
                    COALESCE(AVG(DATEDIFF(fecha_cierre, fecha_programada)), 0) AS promedio_tiempo,
                    COALESCE(AVG(variacion_porcentual), 0) AS variacion_costo
                FROM orden_mantenimiento
                WHERE id_tecnico = %s AND estado = 'Finalizada'
            """
            params = [id_tecnico]
            if fecha_inicio:
                sql += " AND fecha_cierre >= %s"
                params.append(fecha_inicio)
            if fecha_fin:
                sql += " AND fecha_cierre <= %s"
                params.append(fecha_fin)
            cursor.execute(sql, tuple(params))
            return cursor.fetchone() or {"num_odm": 0, "promedio_tiempo": 0, "variacion_costo": 0}
        finally:
            cursor.close()
            conn.close()

    def reporte_desempeno_tecnicos(self, fecha_inicio: str | None, fecha_fin: str | None) -> list:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Fecha filters go inside the LEFT JOIN ON clause so that
            # tecnico rows with no matching ODMs still appear (not filtered out by WHERE).
            join_conditions = ["o.id_tecnico = t.id_tecnico", "o.estado = 'Finalizada'"]
            params = []
            if fecha_inicio:
                join_conditions.append("o.fecha_cierre >= %s")
                params.append(fecha_inicio)
            if fecha_fin:
                join_conditions.append("o.fecha_cierre <= %s")
                params.append(fecha_fin)

            sql = f"""
                SELECT
                    t.id_tecnico,
                    t.nombre,
                    COUNT(o.id_odm) AS num_odm,
                    COALESCE(AVG(DATEDIFF(o.fecha_cierre, o.fecha_programada)), 0) AS promedio_tiempo,
                    COALESCE(AVG(o.variacion_porcentual), 0) AS variacion_costo
                FROM tecnico t
                LEFT JOIN orden_mantenimiento o
                       ON {" AND ".join(join_conditions)}
                WHERE t.activo = 1
                GROUP BY t.id_tecnico, t.nombre
                ORDER BY t.nombre
            """
            cursor.execute(sql, tuple(params))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def reporte_equipos_criticos(self) -> list:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT e.id_equipo, e.nombre, e.estado_operativo, e.criticidad,
                       (
                           SELECT o.id_odm
                           FROM orden_mantenimiento o
                           WHERE o.id_equipo = e.id_equipo
                           ORDER BY o.fecha_programada DESC
                           LIMIT 1
                       ) AS ultima_odm
                FROM equipo e
                WHERE e.activo = 1
                  AND e.estado_operativo IN ('Crítico', 'Fuera de servicio')
                ORDER BY e.nombre
                """
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def _certificaciones_tecnico(self, cursor, id_tecnico: str) -> list:
        cursor.execute(
            """
            SELECT especialidad, nivel, vigencia
            FROM certificacion_tecnico
            WHERE id_tecnico = %s
            ORDER BY especialidad, nivel
            """,
            (id_tecnico,),
        )
        return cursor.fetchall()

    def _guardar_certificaciones(self, cursor, id_tecnico: str, certificaciones: list) -> None:
        for cert in certificaciones:
            cursor.execute(
                """
                INSERT INTO certificacion_tecnico
                (id_cert, id_tecnico, especialidad, nivel, vigencia)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    id_tecnico,
                    cert["especialidad"],
                    cert["nivel"],
                    cert.get("vigencia", "2099-12-31"),
                ),
            )

    def _obtener_estado_odm(self, cursor, id_odm: str):
        cursor.execute("SELECT estado FROM orden_mantenimiento WHERE id_odm = %s", (id_odm,))
        row = cursor.fetchone()
        return row[0] if row else None

    def _guardar_historial(
        self,
        cursor,
        entidad_tipo: str,
        entidad_id: str,
        estado_anterior: str,
        estado_nuevo: str,
        id_usuario: str,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO historial_estado
            (id_historial, entidad_tipo, entidad_id, estado_anterior, estado_nuevo, id_usuario)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                entidad_tipo,
                entidad_id,
                estado_anterior,
                estado_nuevo,
                id_usuario,
            ),
        )
