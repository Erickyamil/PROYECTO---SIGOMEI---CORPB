# gui/panel_odm.py
# Panel de Órdenes de Mantenimiento — RF-11 a RF-25, RF-39 a RF-55
# Rol requerido: Supervisor (también visible para Admin en modo lectura)

import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta

from gui.componentes import (
    COLORES, FUENTE_SUBTIT, FUENTE_NORMAL, FUENTE_PEQUENA,
    label_campo, entry_campo, combo_campo, boton_acento, boton_peligro,
    mostrar_error, mostrar_info, confirmar, tree_con_scroll, color_estado
)
from utils.gui_validators import (
    validar_no_vacio, validar_fechas_odm, validar_decimal_positivo, recopilar_errores
)


ESTADOS_FILTRO = ["", "En_revision", "Programada", "En_Ejecucion",
                  "En_espera_material", "Finalizada", "Cancelada"]
ESTADOS_TRANSICION = ["Programada", "En_Ejecucion", "En_espera_material",
                      "Finalizada", "Cancelada"]

COLS = ("id_odm", "equipo", "tecnico", "estado", "fecha_prog",
        "fecha_cierre_est", "costo_est", "alerta")
ENCS = ("ID ODM", "Equipo", "Técnico", "Estado", "F. Programada",
        "F. Est. Cierre", "Costo Est.", "⚠")
ANCS = (110, 130, 130, 130, 110, 110, 100, 30)


class PanelODM(ttk.Frame):
    """Panel de gestión de Órdenes de Mantenimiento."""

    def __init__(self, parent, proxy, **kw):
        super().__init__(parent, **kw)
        self.proxy = proxy
        self._id_sel: str | None = None
        self._construir_ui()
        self._refrescar_hoy()

    def _construir_ui(self):
        cab = ttk.Frame(self)
        cab.pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(cab, text="📋  Órdenes de Mantenimiento",
                  font=FUENTE_SUBTIT, style="Titulo.TLabel").pack(side="left")
        boton_acento(cab, "＋ Nueva ODM", self._nueva_odm).pack(side="right", padx=4)
        ttk.Button(cab, text="↺ Refrescar", command=self._refrescar_hoy).pack(side="right", padx=4)

        # ── Filtros ───────────────────────────────────────────────────────────
        filt = ttk.LabelFrame(self, text="Filtros (RF-22)")
        filt.pack(fill="x", padx=12, pady=4)
        filt.columnconfigure((1, 3, 5), weight=1)

        self._f_inicio = tk.StringVar(value=str(date.today() - timedelta(days=30)))
        self._f_fin    = tk.StringVar(value=str(date.today() + timedelta(days=60)))
        self._f_estado = tk.StringVar()

        label_campo(filt, "Desde:", 0, 0)
        tk.Entry(filt, textvariable=self._f_inicio, width=12,
                 bg=COLORES["bg_tarjeta"], fg=COLORES["texto"],
                 insertbackground=COLORES["acento"], relief="flat").grid(
                     row=0, column=1, sticky="ew", pady=3, padx=(0, 12))
        label_campo(filt, "Hasta:", 0, 2)
        tk.Entry(filt, textvariable=self._f_fin, width=12,
                 bg=COLORES["bg_tarjeta"], fg=COLORES["texto"],
                 insertbackground=COLORES["acento"], relief="flat").grid(
                     row=0, column=3, sticky="ew", pady=3, padx=(0, 12))
        label_campo(filt, "Estado:", 0, 4)
        combo_campo(filt, self._f_estado, ESTADOS_FILTRO, 0, 5, 16)
        ttk.Button(filt, text="Buscar", command=self._filtrar).grid(row=0, column=6, padx=8)

        # ── Lista ─────────────────────────────────────────────────────────────
        lf = ttk.Frame(self)
        lf.pack(fill="both", expand=True, padx=12, pady=4)
        self._tree = tree_con_scroll(lf, COLS, ENCS, ANCS)
        self._tree.bind("<<TreeviewSelect>>", self._al_sel)
        self._tree.bind("<Double-1>", lambda _: self._ver_detalle())

        # ── Acciones ──────────────────────────────────────────────────────────
        acc = ttk.Frame(self)
        acc.pack(fill="x", padx=12, pady=(4, 10))
        ttk.Button(acc, text="Ver detalle", command=self._ver_detalle).pack(side="left", padx=4)
        ttk.Button(acc, text="Avanzar estado", command=self._avanzar_estado).pack(side="left", padx=4)
        ttk.Button(acc, text="Agregar nota (RF-40)", command=self._agregar_nota).pack(side="left", padx=4)
        ttk.Button(acc, text="Reasignar técnico (RF-41)", command=self._reasignar).pack(side="left", padx=4)
        ttk.Button(acc, text="Resumen de costos (RF-25)", command=self._resumen_costos).pack(side="left", padx=4)

    # ── Carga ─────────────────────────────────────────────────────────────────

    def _refrescar_hoy(self):
        self._filtrar()

    def _filtrar(self):
        inicio = self._f_inicio.get().strip() or str(date.today() - timedelta(days=30))
        fin    = self._f_fin.get().strip()    or str(date.today() + timedelta(days=60))
        estado = self._f_estado.get() or None

        resp = self.proxy.filtrar_odms(inicio, fin, estado)
        self._tree.delete(*self._tree.get_children())

        if resp["status"] != "OK":
            mostrar_error("Error", resp.get("message", "Error al filtrar."))
            return

        hoy = date.today()
        manana = hoy + timedelta(days=1)

        for odm in (resp["data"] or []):
            # RF-44: alerta visual si fecha est. cierre dentro de 24h
            try:
                fecha_cierre_est = date.fromisoformat(str(odm.get("fecha_estimada_cierre", "")))
                alerta = "⚠" if hoy <= fecha_cierre_est <= manana else ""
            except ValueError:
                alerta = ""

            estado_val = odm.get("estado", "")
            tag = estado_val.lower().replace("_", "")
            self._tree.insert("", "end", iid=odm.get("id_odm"),
                              values=(
                                  odm.get("id_odm", ""),
                                  odm.get("id_equipo", ""),
                                  odm.get("id_tecnico", ""),
                                  estado_val,
                                  odm.get("fecha_programada", ""),
                                  odm.get("fecha_estimada_cierre", ""),
                                  odm.get("costo_estimado", ""),
                                  alerta,
                              ), tags=(tag, "alerta" if alerta else ""))

        # Colorear por estado
        for est, color in {
            "en_revision": COLORES["estado_rev"],
            "programada": COLORES["estado_prog"],
            "en_ejecucion": COLORES["estado_ejec"],
            "en_espera_material": COLORES["estado_esp"],
            "finalizada": COLORES["estado_fin"],
            "cancelada": COLORES["estado_cancel"],
        }.items():
            self._tree.tag_configure(est, foreground=color)
        self._tree.tag_configure("alerta", background="#3D2A1A")

    def _al_sel(self, _):
        sel = self._tree.selection()
        self._id_sel = sel[0] if sel else None

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _nueva_odm(self):
        _DialogoNuevaODM(self, self.proxy, on_guardado=self._filtrar)

    def _ver_detalle(self):
        if not self._id_sel:
            mostrar_error("Selección", "Seleccione una ODM.")
            return
        _DialogoDetalleODM(self, self.proxy, self._id_sel)

    def _avanzar_estado(self):
        if not self._id_sel:
            mostrar_error("Selección", "Seleccione una ODM.")
            return
        _DialogoAvanzarEstado(self, self.proxy, self._id_sel, on_guardado=self._filtrar)

    def _agregar_nota(self):
        if not self._id_sel:
            mostrar_error("Selección", "Seleccione una ODM.")
            return
        _DialogoAgregarNota(self, self.proxy, self._id_sel, on_guardado=self._filtrar)

    def _reasignar(self):
        if not self._id_sel:
            mostrar_error("Selección", "Seleccione una ODM.")
            return
        _DialogoReasignar(self, self.proxy, self._id_sel, on_guardado=self._filtrar)

    def _resumen_costos(self):
        if not self._id_sel:
            mostrar_error("Selección", "Seleccione una ODM Finalizada.")
            return
        resp = self.proxy.resumen_costos(self._id_sel)
        if resp["status"] != "OK":
            mostrar_error("Error", resp.get("message", "No disponible."))
            return
        d = resp["data"] or {}
        mostrar_info("Resumen de Costos",
                     f"ODM: {self._id_sel}\n"
                     f"Costo estimado:  ${d.get('costo_estimado', 0):,.2f}\n"
                     f"Costo real:      ${d.get('costo_real', 0):,.2f}\n"
                     f"Variación:       {d.get('variacion_pct', 0):.2f}%")


# ── Diálogos ──────────────────────────────────────────────────────────────────

class _DialogoNuevaODM(tk.Toplevel):
    """Formulario de nueva ODM con selectores de equipo y técnico (RF-11)."""

    def __init__(self, parent, proxy, on_guardado=None):
        super().__init__(parent)
        self.proxy = proxy
        self.on_guardado = on_guardado
        self._equipos_map: dict = {}     # display -> id_equipo
        self._tecnicos_map: dict = {}    # display -> id_tecnico
        self.title("Nueva Orden de Mantenimiento")
        self.configure(bg=COLORES["bg_panel"])
        self.resizable(False, False)
        self.grab_set()

        self._vars = {k: tk.StringVar() for k in (
            "nota_original", "fecha_programada",
            "fecha_estimada_cierre", "costo_estimado"
        )}
        self._v_equipo  = tk.StringVar()
        self._v_tecnico = tk.StringVar()
        self._construir()
        self._cargar_selectores()

    def _construir(self):
        ttk.Label(self, text="Nueva ODM", font=FUENTE_SUBTIT,
                  style="Titulo.TLabel").pack(pady=(16, 4), padx=20, anchor="w")

        f = ttk.Frame(self, padding=20)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        # Equipo selector
        label_campo(f, "Equipo *:", 0)
        self._combo_equipo = ttk.Combobox(f, textvariable=self._v_equipo,
                                           state="readonly", width=34)
        self._combo_equipo.grid(row=0, column=1, sticky="ew", pady=3)

        # Técnico selector
        label_campo(f, "Técnico *:", 1)
        self._combo_tecnico = ttk.Combobox(f, textvariable=self._v_tecnico,
                                            state="readonly", width=34)
        self._combo_tecnico.grid(row=1, column=1, sticky="ew", pady=3)

        # Campos de texto
        textos = [
            ("Nota original *",               "nota_original",         2),
            ("Fecha programada *\n(YYYY-MM-DD)",  "fecha_programada",  3),
            ("Fecha est. cierre *\n(YYYY-MM-DD)", "fecha_estimada_cierre", 4),
            ("Costo estimado * ($)",           "costo_estimado",        5),
        ]
        for lbl, key, row in textos:
            label_campo(f, lbl, row)
            entry_campo(f, self._vars[key], row)

        self._var_msg = tk.StringVar()
        tk.Label(self, textvariable=self._var_msg, bg=COLORES["bg_panel"],
                 fg=COLORES["error"], font=FUENTE_PEQUENA, wraplength=380).pack(pady=4)

        bf = ttk.Frame(self, padding=(20, 0, 20, 20))
        bf.pack(fill="x")
        boton_acento(bf, "Crear ODM", self._guardar).pack(side="right", padx=4)
        ttk.Button(bf, text="Cancelar", command=self.destroy).pack(side="right")

    def _cargar_selectores(self):
        # Equipos activos
        resp_eq = self.proxy.listar_equipos({})
        if resp_eq.get("status") == "OK":
            self._equipos_map = {
                f"{e['nombre']} — {e['ubicacion']} ({e['id_equipo'][:8]}…)": e["id_equipo"]
                for e in (resp_eq.get("data") or [])
            }
            self._combo_equipo["values"] = list(self._equipos_map.keys())

        # Técnicos activos
        resp_tec = self.proxy.buscar_tecnicos()
        if resp_tec.get("status") == "OK":
            self._tecnicos_map = {
                f"{t['nombre']} ({t['id_tecnico'][:8]}…)": t["id_tecnico"]
                for t in (resp_tec.get("data") or [])
                if t.get("estatus") == "Activo"
            }
            self._combo_tecnico["values"] = list(self._tecnicos_map.keys())

    def _guardar(self):
        id_equipo  = self._equipos_map.get(self._v_equipo.get(), "")
        id_tecnico = self._tecnicos_map.get(self._v_tecnico.get(), "")

        payload = {k: v.get().strip() for k, v in self._vars.items()}
        payload["id_equipo"]  = id_equipo
        payload["id_tecnico"] = id_tecnico

        errores = recopilar_errores(
            equipo=validar_no_vacio(id_equipo, "Equipo"),
            tecnico=validar_no_vacio(id_tecnico, "Técnico"),
            nota=validar_no_vacio(payload["nota_original"], "Nota"),
            fechas=validar_fechas_odm(payload["fecha_programada"],
                                      payload["fecha_estimada_cierre"]),
            costo=validar_decimal_positivo(payload["costo_estimado"]),
        )
        if errores:
            self._var_msg.set("\n".join(errores))
            return

        payload["costo_estimado"] = float(payload["costo_estimado"])
        resp = self.proxy.crear_odm(payload)

        if resp["status"] == "OK":
            id_nueva = (resp.get("data") or {}).get("id_odm", "")
            mostrar_info("Éxito", f"ODM creada con ID: {id_nueva}")
            if self.on_guardado:
                self.on_guardado()
            self.destroy()
        else:
            self._var_msg.set(resp.get("message", "Error al crear ODM."))


class _DialogoDetalleODM(tk.Toplevel):
    def __init__(self, parent, proxy, id_odm: str):
        super().__init__(parent)
        self.title(f"Detalle ODM — {id_odm}")
        self.configure(bg=COLORES["bg_panel"])
        self.geometry("480x420")
        self.grab_set()

        ttk.Label(self, text=f"Detalle: {id_odm}",
                  font=FUENTE_SUBTIT, style="Titulo.TLabel").pack(pady=12, padx=16, anchor="w")

        # Pedimos los datos directamente por ID (más eficiente)
        resp = proxy.obtener_odm(id_odm)
        odm = resp.get("data") if resp.get("status") == "OK" else None

        if not odm:
            ttk.Label(self, text="ODM no encontrada.").pack()
            return

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both")
        frame.columnconfigure(1, weight=1)

        campos = [
            ("ID ODM",            odm.get("id_odm", "")),
            ("Equipo",            odm.get("id_equipo", "")),
            ("Técnico",           odm.get("id_tecnico", "")),
            ("Estado",            odm.get("estado", "")),
            ("Fecha programada",  str(odm.get("fecha_programada", ""))),
            ("Fecha est. cierre", str(odm.get("fecha_estimada_cierre", ""))),
            ("Fecha cierre",      str(odm.get("fecha_cierre") or "—")),
            ("Costo estimado",    f"${float(odm.get('costo_estimado', 0) or 0):,.2f}"),
            ("Costo real",        f"${float(odm.get('costo_real', 0) or 0):,.2f}" if odm.get("costo_real") else "—"),
            ("Variación %",       f"{float(odm.get('variacion_porcentual', 0) or 0):.2f}%" if odm.get("variacion_porcentual") is not None else "—"),
            ("Nota original",     odm.get("nota_original", "")),
        ]
        for i, (lbl, val) in enumerate(campos):
            label_campo(frame, lbl + ":", i)
            tk.Label(frame, text=val, bg=COLORES["bg_panel"],
                     fg=COLORES["texto"], font=FUENTE_NORMAL,
                     wraplength=280, justify="left").grid(
                         row=i, column=1, sticky="w", pady=2)

        # Mostrar notas de seguimiento si existen
        notas = odm.get("notas", [])
        if notas:
            ttk.Separator(frame, orient="horizontal").grid(
                row=len(campos), column=0, columnspan=2, sticky="ew", pady=6)
            ttk.Label(frame, text="Notas de seguimiento:",
                      style="Muted.TLabel").grid(row=len(campos)+1, column=0, sticky="nw", pady=2)
            notas_txt = "\n".join(
                f"[{n.get('creado_en', '')}] {n.get('contenido', '')}"
                for n in notas
            )
            tk.Label(frame, text=notas_txt, bg=COLORES["bg_panel"],
                     fg=COLORES["texto_muted"], font=FUENTE_PEQUENA,
                     wraplength=280, justify="left").grid(
                         row=len(campos)+1, column=1, sticky="w", pady=2)

        ttk.Button(self, text="Cerrar", command=self.destroy).pack(pady=12)


class _DialogoAvanzarEstado(tk.Toplevel):
    def __init__(self, parent, proxy, id_odm: str, on_guardado=None):
        super().__init__(parent)
        self.proxy = proxy
        self.id_odm = id_odm
        self.on_guardado = on_guardado
        self.title(f"Avanzar estado — {id_odm}")
        self.configure(bg=COLORES["bg_panel"])
        self.resizable(False, False)
        self.grab_set()

        self._v_estado = tk.StringVar()
        self._v_costo  = tk.StringVar()
        self._construir()

    def _construir(self):
        f = ttk.Frame(self, padding=24)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text=f"ODM: {self.id_odm}",
                  font=FUENTE_SUBTIT, style="Titulo.TLabel").grid(
                      row=0, column=0, columnspan=2, pady=(0, 16), sticky="w")

        label_campo(f, "Nuevo estado *:", 1)
        combo_campo(f, self._v_estado, ESTADOS_TRANSICION, 1, 1)
        self._v_estado.trace_add("write", self._on_estado_change)

        self._lbl_costo = label_campo(f, "Costo real * ($):", 2)
        self._e_costo = entry_campo(f, self._v_costo, 2)
        self._lbl_costo.grid_remove()
        self._e_costo.grid_remove()

        self._var_msg = tk.StringVar()
        tk.Label(f, textvariable=self._var_msg, bg=COLORES["bg_panel"],
                 fg=COLORES["error"], font=FUENTE_PEQUENA).grid(
                     row=3, column=0, columnspan=2, pady=4)

        bf = ttk.Frame(f)
        bf.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
        boton_acento(bf, "Confirmar", self._guardar).pack(side="right", padx=4)
        ttk.Button(bf, text="Cancelar", command=self.destroy).pack(side="right")

    def _on_estado_change(self, *_):
        if self._v_estado.get() == "Finalizada":
            self._lbl_costo.grid()
            self._e_costo.grid()
        else:
            self._lbl_costo.grid_remove()
            self._e_costo.grid_remove()

    def _guardar(self):
        nuevo_estado = self._v_estado.get()
        if not nuevo_estado:
            self._var_msg.set("Seleccione un estado.")
            return

        payload = {"id_odm": self.id_odm, "nuevo_estado": nuevo_estado}

        if nuevo_estado == "Finalizada":
            err = validar_decimal_positivo(self._v_costo.get())
            if err:
                self._var_msg.set(f"Costo real: {err}")
                return
            payload["costo_real"] = float(self._v_costo.get())

        resp = self.proxy.actualizar_estado_odm(payload)
        if resp["status"] == "OK":
            mostrar_info("Éxito", f"Estado actualizado a {nuevo_estado}.")
            if self.on_guardado:
                self.on_guardado()
            self.destroy()
        else:
            self._var_msg.set(resp.get("message", "Error al actualizar estado."))


class _DialogoAgregarNota(tk.Toplevel):
    def __init__(self, parent, proxy, id_odm: str, on_guardado=None):
        super().__init__(parent)
        self.proxy = proxy
        self.id_odm = id_odm
        self.on_guardado = on_guardado
        self.title(f"Agregar nota — {id_odm}")
        self.configure(bg=COLORES["bg_panel"])
        self.grab_set()

        f = ttk.Frame(self, padding=20)
        f.pack(fill="both")

        ttk.Label(f, text="Nota adicional (RF-40):").pack(anchor="w")
        self._txt = tk.Text(f, height=6, width=44,
                            bg=COLORES["bg_tarjeta"], fg=COLORES["texto"],
                            insertbackground=COLORES["acento"], relief="flat",
                            font=FUENTE_NORMAL)
        self._txt.pack(fill="both", pady=8)

        self._var_msg = tk.StringVar()
        tk.Label(f, textvariable=self._var_msg, bg=COLORES["bg_panel"],
                 fg=COLORES["error"], font=FUENTE_PEQUENA).pack()

        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(8, 0))
        boton_acento(bf, "Agregar nota", self._guardar).pack(side="right", padx=4)
        ttk.Button(bf, text="Cancelar", command=self.destroy).pack(side="right")

    def _guardar(self):
        nota = self._txt.get("1.0", "end").strip()
        if not nota:
            self._var_msg.set("La nota no puede estar vacía.")
            return
        resp = self.proxy.agregar_nota_odm(self.id_odm, nota)
        if resp["status"] == "OK":
            mostrar_info("Éxito", "Nota agregada correctamente.")
            if self.on_guardado:
                self.on_guardado()
            self.destroy()
        else:
            self._var_msg.set(resp.get("message", "Error al agregar nota."))


class _DialogoReasignar(tk.Toplevel):
    """Diálogo de reasignación con selector de técnicos activos (RF-41)."""

    def __init__(self, parent, proxy, id_odm: str, on_guardado=None):
        super().__init__(parent)
        self.proxy = proxy
        self.id_odm = id_odm
        self.on_guardado = on_guardado
        self._tecnicos_map: dict = {}   # nombre_display -> id_tecnico
        self.title(f"Reasignar técnico — {id_odm}")
        self.configure(bg=COLORES["bg_panel"])
        self.resizable(False, False)
        self.grab_set()
        self._construir()
        self._cargar_tecnicos()

    def _construir(self):
        f = ttk.Frame(self, padding=24)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        label_campo(f, "Técnico actual ODM:", 0)
        self._lbl_actual = tk.Label(f, text="(cargando...)", bg=COLORES["bg_panel"],
                                    fg=COLORES["texto_muted"], font=FUENTE_PEQUENA)
        self._lbl_actual.grid(row=0, column=1, sticky="w", pady=3)

        label_campo(f, "Nuevo técnico *:", 1)
        self._v_tec = tk.StringVar()
        self._combo_tec = ttk.Combobox(f, textvariable=self._v_tec,
                                        state="readonly", width=30)
        self._combo_tec.grid(row=1, column=1, sticky="ew", pady=3)

        self._var_msg = tk.StringVar()
        tk.Label(f, textvariable=self._var_msg, bg=COLORES["bg_panel"],
                 fg=COLORES["error"], font=FUENTE_PEQUENA).grid(
                     row=2, column=0, columnspan=2, pady=4)

        bf = ttk.Frame(f)
        bf.grid(row=3, column=0, columnspan=2, sticky="e")
        boton_acento(bf, "Reasignar", self._guardar).pack(side="right", padx=4)
        ttk.Button(bf, text="Cancelar", command=self.destroy).pack(side="right")

    def _cargar_tecnicos(self):
        # Cargar técnico actual de la ODM
        resp_odm = self.proxy.obtener_odm(self.id_odm)
        if resp_odm.get("status") == "OK" and resp_odm.get("data"):
            self._lbl_actual.configure(text=resp_odm["data"].get("id_tecnico", "—"))

        # Cargar lista de técnicos activos
        resp = self.proxy.buscar_tecnicos()
        if resp.get("status") == "OK":
            tecnicos_activos = [t for t in (resp.get("data") or [])
                                if t.get("estatus") == "Activo"]
            self._tecnicos_map = {
                f"{t['nombre']} ({t['id_tecnico'][:8]}…)": t["id_tecnico"]
                for t in tecnicos_activos
            }
            self._combo_tec["values"] = list(self._tecnicos_map.keys())
        else:
            self._var_msg.set("No se pudieron cargar los técnicos.")

    def _guardar(self):
        display = self._v_tec.get().strip()
        if not display:
            self._var_msg.set("Seleccione un técnico.")
            return
        id_tec = self._tecnicos_map.get(display, "")
        if not id_tec:
            self._var_msg.set("Técnico no válido.")
            return
        resp = self.proxy.reasignar_tecnico_odm(self.id_odm, id_tec)
        if resp["status"] == "OK":
            mostrar_info("Éxito", "Técnico reasignado correctamente.")
            if self.on_guardado:
                self.on_guardado()
            self.destroy()
        else:
            self._var_msg.set(resp.get("message", "Error al reasignar."))
