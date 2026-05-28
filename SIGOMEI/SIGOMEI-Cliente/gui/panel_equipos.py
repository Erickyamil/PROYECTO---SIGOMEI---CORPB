# gui/panel_equipos.py
# Panel de gestión de Equipos Industriales — RF-05 a RF-08, RF-31 a RF-34
# Rol requerido: Administrador

import tkinter as tk
from tkinter import ttk

from gui.componentes import (
    COLORES, FUENTE_SUBTIT, FUENTE_NORMAL, FUENTE_PEQUENA,
    label_campo, entry_campo, combo_campo, boton_acento, boton_peligro,
    mostrar_error, mostrar_info, confirmar, tree_con_scroll, color_estado
)
from utils.gui_validators import (
    validar_no_vacio, validar_fecha, validar_decimal_positivo, recopilar_errores
)


TIPOS_EQUIPO   = ["Mecánica", "Eléctrica", "Instrumentación", "Hidráulica", "Neumática"]
ESTADOS_OP     = ["Operativo", "Crítico", "Fuera de servicio", "Inactivo"]
CRITICIDADES   = ["Baja", "Media", "Alta"]
COLS_LISTA     = ("id", "nombre", "tipo", "marca", "modelo", "serie",
                  "ubicacion", "estado", "criticidad")
ENCABEZADOS    = ("ID", "Nombre", "Tipo", "Marca", "Modelo", "N° Serie",
                  "Ubicación", "Estado", "Criticidad")
ANCHOS         = (80, 160, 100, 100, 100, 110, 130, 120, 90)


class PanelEquipos(ttk.Frame):
    """Panel completo de Equipos para rol Administrador."""

    def __init__(self, parent, proxy, **kw):
        super().__init__(parent, **kw)
        self.proxy = proxy
        self._id_seleccionado: str | None = None
        self._construir_ui()
        self.refrescar_lista()

    def _construir_ui(self):
        # ── Encabezado ────────────────────────────────────────────────────────
        cab = ttk.Frame(self)
        cab.pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(cab, text="⚙  Gestión de Equipos Industriales",
                  font=FUENTE_SUBTIT, style="Titulo.TLabel").pack(side="left")
        boton_acento(cab, "＋ Nuevo Equipo", self._abrir_formulario_nuevo).pack(side="right", padx=4)
        ttk.Button(cab, text="↺ Refrescar", command=self.refrescar_lista).pack(side="right", padx=4)

        # ── Filtros ───────────────────────────────────────────────────────────
        filt = ttk.LabelFrame(self, text="Filtros (RF-33)")
        filt.pack(fill="x", padx=12, pady=4)
        filt.columnconfigure((1, 3, 5, 7), weight=1)

        self._f_tipo  = tk.StringVar()
        self._f_crit  = tk.StringVar()
        self._f_est   = tk.StringVar()
        self._f_ubic  = tk.StringVar()

        label_campo(filt, "Tipo:", 0, 0); combo_campo(filt, self._f_tipo,  [""] + TIPOS_EQUIPO, 0, 1, 14)
        label_campo(filt, "Criticidad:", 0, 2); combo_campo(filt, self._f_crit, [""] + CRITICIDADES, 0, 3, 10)
        label_campo(filt, "Estado:", 0, 4); combo_campo(filt, self._f_est,  [""] + ESTADOS_OP, 0, 5, 16)
        label_campo(filt, "Ubicación:", 0, 6)
        tk.Entry(filt, textvariable=self._f_ubic, width=14,
                 bg=COLORES["bg_tarjeta"], fg=COLORES["texto"],
                 insertbackground=COLORES["acento"], relief="flat").grid(row=0, column=7, sticky="ew", pady=3, padx=(0, 8))
        ttk.Button(filt, text="Buscar", command=self.refrescar_lista).grid(row=0, column=8, padx=6)

        # ── Lista ─────────────────────────────────────────────────────────────
        lista_frame = ttk.Frame(self)
        lista_frame.pack(fill="both", expand=True, padx=12, pady=4)
        self._tree = tree_con_scroll(lista_frame, COLS_LISTA, ENCABEZADOS, ANCHOS)
        self._tree.bind("<<TreeviewSelect>>", self._al_seleccionar)
        self._tree.bind("<Double-1>", lambda _: self._abrir_detalle())

        # ── Botones de acción ─────────────────────────────────────────────────
        acc = ttk.Frame(self)
        acc.pack(fill="x", padx=12, pady=(4, 10))
        ttk.Button(acc, text="Ver detalle / Editar", command=self._abrir_detalle).pack(side="left", padx=4)
        boton_peligro(acc, "🗑 Eliminar (RF-08)", self._eliminar).pack(side="left", padx=4)
        ttk.Button(acc, text="Historial de ODMs (RF-34)", command=self._ver_historial).pack(side="left", padx=4)

    # ── Carga de datos ────────────────────────────────────────────────────────

    def refrescar_lista(self):
        filtros = {}
        if self._f_tipo.get():  filtros["tipo"]            = self._f_tipo.get()
        if self._f_crit.get():  filtros["criticidad"]      = self._f_crit.get()
        if self._f_est.get():   filtros["estado_operativo"]= self._f_est.get()
        if self._f_ubic.get():  filtros["ubicacion"]       = self._f_ubic.get()

        resp = self.proxy.listar_equipos(filtros)
        self._tree.delete(*self._tree.get_children())

        if resp["status"] != "OK":
            mostrar_error("Error", resp.get("message", "Error al listar equipos."))
            return

        for eq in (resp["data"] or []):
            estado = eq.get("estado_operativo", "")
            tag = "critico" if estado in ("Crítico", "Fuera de servicio") else ""
            self._tree.insert("", "end", iid=eq["id_equipo"],
                              values=(
                                  eq.get("id_equipo", ""),
                                  eq.get("nombre", ""),
                                  eq.get("tipo", ""),
                                  eq.get("marca", ""),
                                  eq.get("modelo", ""),
                                  eq.get("num_serie", ""),
                                  eq.get("ubicacion", ""),
                                  estado,
                                  eq.get("criticidad", ""),
                              ), tags=(tag,))
        self._tree.tag_configure("critico", foreground=COLORES["alerta"])

    def _al_seleccionar(self, _):
        sel = self._tree.selection()
        self._id_seleccionado = sel[0] if sel else None

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _abrir_formulario_nuevo(self):
        _DialogoEquipo(self, self.proxy, modo="nuevo",
                       on_guardado=self.refrescar_lista)

    def _abrir_detalle(self):
        if not self._id_seleccionado:
            mostrar_error("Selección", "Seleccione un equipo de la lista.")
            return
        _DialogoEquipo(self, self.proxy, modo="editar",
                       id_equipo=self._id_seleccionado,
                       on_guardado=self.refrescar_lista)

    def _eliminar(self):
        if not self._id_seleccionado:
            mostrar_error("Selección", "Seleccione un equipo de la lista.")
            return
        if not confirmar("Eliminar equipo",
                         "¿Desea eliminar el equipo seleccionado?\n\n"
                         "• Sin historial → eliminación permanente.\n"
                         "• Con historial → baja lógica (se preserva trazabilidad).\n"
                         "• Con órdenes activas → no permitido."):
            return
        resp = self.proxy.eliminar_equipo(self._id_seleccionado)
        if resp["status"] == "OK":
            tipo = (resp.get("data") or {}).get("tipo_baja", "")
            if tipo == "fisica":
                mostrar_info("Eliminado", "El equipo fue eliminado permanentemente.")
            else:
                mostrar_info("Baja lógica aplicada",
                             "El equipo tiene historial de órdenes.\n"
                             "Se aplicó baja lógica para preservar la trazabilidad.")
            self.refrescar_lista()
        else:
            mostrar_error("Error", resp.get("message", "No se pudo eliminar el equipo."))

    def _ver_historial(self):
        if not self._id_seleccionado:
            mostrar_error("Selección", "Seleccione un equipo de la lista.")
            return
        resp = self.proxy.historial_equipo(self._id_seleccionado)
        if resp["status"] != "OK":
            mostrar_error("Error", resp.get("message", "Error al obtener historial."))
            return
        _DialogoHistorial(self, resp["data"], self._id_seleccionado)


# ── Diálogos ──────────────────────────────────────────────────────────────────

class _DialogoEquipo(tk.Toplevel):
    """Formulario modal para crear o editar un equipo."""

    def __init__(self, parent, proxy, modo: str,
                 id_equipo: str = None, on_guardado=None):
        super().__init__(parent)
        self.proxy = proxy
        self.modo = modo
        self.id_equipo = id_equipo
        self.on_guardado = on_guardado

        titulo = "Nuevo Equipo" if modo == "nuevo" else f"Editar Equipo — {id_equipo}"
        self.title(titulo)
        self.resizable(False, False)
        self.configure(bg=COLORES["bg_panel"])
        self.grab_set()

        self._vars = {k: tk.StringVar() for k in (
            "nombre", "tipo", "marca", "modelo", "num_serie",
            "ubicacion", "fecha_instalacion", "estado_operativo", "criticidad"
        )}

        self._construir_form()

        if modo == "editar" and id_equipo:
            self._cargar_datos()

    def _construir_form(self):
        ttk.Label(self, text="Datos del Equipo",
                  font=FUENTE_SUBTIT, style="Titulo.TLabel").pack(pady=(16, 8), padx=20, anchor="w")

        f = ttk.Frame(self, padding=20)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        campos = [
            ("Nombre *",              "nombre",             "entry"),
            ("Tipo *",                "tipo",               TIPOS_EQUIPO),
            ("Marca *",               "marca",              "entry"),
            ("Modelo *",              "modelo",             "entry"),
            ("N° Serie *",            "num_serie",          "entry"),
            ("Ubicación *",           "ubicacion",          "entry"),
            ("Fecha instalación *\n(YYYY-MM-DD)", "fecha_instalacion", "entry"),
            ("Estado operativo *",    "estado_operativo",   ESTADOS_OP),
            ("Criticidad *",          "criticidad",         CRITICIDADES),
        ]
        for i, (lbl, key, tipo) in enumerate(campos):
            label_campo(f, lbl, i)
            if tipo == "entry":
                entry_campo(f, self._vars[key], i)
            else:
                combo_campo(f, self._vars[key], tipo, i)

        # Mensaje de error
        self._var_msg = tk.StringVar()
        tk.Label(self, textvariable=self._var_msg, bg=COLORES["bg_panel"],
                 fg=COLORES["error"], font=FUENTE_PEQUENA, wraplength=340).pack(pady=4)

        # Botones
        btn_frame = ttk.Frame(self, padding=(20, 0, 20, 20))
        btn_frame.pack(fill="x")
        boton_acento(btn_frame, "Guardar", self._guardar).pack(side="right", padx=4)
        ttk.Button(btn_frame, text="Cancelar", command=self.destroy).pack(side="right")

    def _cargar_datos(self):
        # Podríamos tener el dict ya disponible desde el tree;
        # aquí pedimos directamente al servidor para datos completos.
        resp = self.proxy.listar_equipos({"id_equipo": self.id_equipo})
        if resp["status"] == "OK" and resp["data"]:
            eq = resp["data"][0] if isinstance(resp["data"], list) else resp["data"]
            for key, var in self._vars.items():
                val = eq.get(key, "") or eq.get(key.replace("_", ""), "")
                if val:
                    var.set(str(val))

    def _guardar(self):
        payload = {k: v.get().strip() for k, v in self._vars.items()}

        errores = recopilar_errores(
            nombre=validar_no_vacio(payload["nombre"], "Nombre"),
            tipo=validar_no_vacio(payload["tipo"], "Tipo"),
            marca=validar_no_vacio(payload["marca"], "Marca"),
            modelo=validar_no_vacio(payload["modelo"], "Modelo"),
            serie=validar_no_vacio(payload["num_serie"], "N° Serie"),
            ubic=validar_no_vacio(payload["ubicacion"], "Ubicación"),
            fecha=validar_fecha(payload["fecha_instalacion"]),
        )
        if errores:
            self._var_msg.set("\n".join(errores))
            return

        if self.modo == "nuevo":
            resp = self.proxy.crear_equipo(payload)
        else:
            payload["id_equipo"] = self.id_equipo
            resp = self.proxy.actualizar_equipo(payload)

        if resp["status"] == "OK":
            mostrar_info("Éxito", resp.get("message", "Operación exitosa."))
            if self.on_guardado:
                self.on_guardado()
            self.destroy()
        else:
            self._var_msg.set(resp.get("message", "Error al guardar."))


class _DialogoHistorial(tk.Toplevel):
    """Muestra el historial de ODMs asociadas a un equipo."""

    def __init__(self, parent, data: dict, id_equipo: str):
        super().__init__(parent)
        self.title(f"Historial — Equipo {id_equipo}")
        self.configure(bg=COLORES["bg_panel"])
        self.geometry("700x450")
        self.grab_set()

        ttk.Label(self, text=f"Historial de ODMs — {id_equipo}",
                  font=FUENTE_SUBTIT, style="Titulo.TLabel").pack(pady=12, padx=12, anchor="w")

        cols = ("id_odm", "tecnico", "estado", "fecha_prog", "costo_est", "costo_real")
        enc  = ("ID ODM", "Técnico", "Estado", "Fecha Prog.", "Costo Est.", "Costo Real")
        anc  = (110, 140, 120, 100, 100, 100)
        tree = tree_con_scroll(self, cols, enc, anc)

        odms = (data or {}).get("odms", [])
        for odm in odms:
            tree.insert("", "end", values=(
                odm.get("id_odm", ""),
                odm.get("id_tecnico", ""),
                odm.get("estado", ""),
                odm.get("fecha_programada", ""),
                odm.get("costo_estimado", ""),
                odm.get("costo_real", "—"),
            ))
        if not odms:
            tree.insert("", "end", values=("Sin órdenes registradas", "", "", "", "", ""))

        ttk.Button(self, text="Cerrar", command=self.destroy).pack(pady=10)
