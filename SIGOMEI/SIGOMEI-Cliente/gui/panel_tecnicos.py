# gui/panel_tecnicos.py
# Panel de gestión de Técnicos — RF-09, RF-10, RF-35 a RF-38
# Rol requerido: Administrador

import tkinter as tk
from tkinter import ttk

from gui.componentes import (
    COLORES, FUENTE_SUBTIT, FUENTE_NORMAL, FUENTE_PEQUENA,
    label_campo, entry_campo, combo_campo, boton_acento, boton_peligro,
    mostrar_error, mostrar_info, confirmar, tree_con_scroll
)
from utils.gui_validators import (
    validar_no_vacio, validar_correo, validar_rfc, validar_telefono,
    validar_fecha, recopilar_errores
)


ESPECIALIDADES  = ["Mecánica", "Eléctrica", "Instrumentación", "Hidráulica", "Neumática"]
NIVELES_CERT    = ["I", "II", "III"]
ESTATUS_OPCIONES= ["Activo", "Inactivo"]

COLS  = ("id", "nombre", "rfc", "telefono", "correo", "estatus")
ENCS  = ("ID", "Nombre", "RFC", "Teléfono", "Correo", "Estatus")
ANCS  = (80, 180, 120, 110, 180, 80)


class PanelTecnicos(ttk.Frame):
    """Panel de Técnicos para Administrador."""

    def __init__(self, parent, proxy, **kw):
        super().__init__(parent, **kw)
        self.proxy = proxy
        self._id_sel: str | None = None
        self._construir_ui()
        self.refrescar_lista()

    def _construir_ui(self):
        cab = ttk.Frame(self)
        cab.pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(cab, text="👷  Gestión de Técnicos",
                  font=FUENTE_SUBTIT, style="Titulo.TLabel").pack(side="left")
        boton_acento(cab, "＋ Nuevo Técnico", self._nuevo).pack(side="right", padx=4)
        ttk.Button(cab, text="↺ Refrescar", command=self.refrescar_lista).pack(side="right", padx=4)

        # ── Barra de filtros (RF-08) ──────────────────────────────────────────
        fb = ttk.LabelFrame(self, text="Filtros")
        fb.pack(fill="x", padx=12, pady=(0, 4))

        ttk.Label(fb, text="Especialidad:").grid(row=0, column=0, padx=6, pady=4, sticky="e")
        self._var_esp = tk.StringVar()
        ttk.Combobox(fb, textvariable=self._var_esp,
                     values=[""] + ESPECIALIDADES, state="readonly", width=16
                     ).grid(row=0, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(fb, text="Nivel cert.:").grid(row=0, column=2, padx=6, pady=4, sticky="e")
        self._var_niv = tk.StringVar()
        ttk.Combobox(fb, textvariable=self._var_niv,
                     values=[""] + NIVELES_CERT, state="readonly", width=8
                     ).grid(row=0, column=3, padx=4, pady=4, sticky="w")

        ttk.Label(fb, text="Estatus:").grid(row=0, column=4, padx=6, pady=4, sticky="e")
        self._var_est = tk.StringVar()
        ttk.Combobox(fb, textvariable=self._var_est,
                     values=["", "Activo", "Inactivo"], state="readonly", width=10
                     ).grid(row=0, column=5, padx=4, pady=4, sticky="w")

        ttk.Button(fb, text="🔍 Buscar", command=self.refrescar_lista).grid(
            row=0, column=6, padx=8, pady=4)
        ttk.Button(fb, text="✕ Limpiar", command=self._limpiar_filtros).grid(
            row=0, column=7, padx=2, pady=4)
        # ─────────────────────────────────────────────────────────────────────

        # Lista
        lf = ttk.Frame(self)
        lf.pack(fill="both", expand=True, padx=12, pady=4)
        self._tree = tree_con_scroll(lf, COLS, ENCS, ANCS)
        self._tree.bind("<<TreeviewSelect>>", self._al_sel)
        self._tree.bind("<Double-1>", lambda _: self._editar())

        # Acciones
        acc = ttk.Frame(self)
        acc.pack(fill="x", padx=12, pady=(4, 10))
        ttk.Button(acc, text="Ver / Editar", command=self._editar).pack(side="left", padx=4)
        ttk.Button(acc, text="Activar / Inactivar (RF-10)", command=self._cambiar_estatus).pack(side="left", padx=4)
        ttk.Button(acc, text="Ver carga de trabajo (RF-36)", command=self._carga_trabajo).pack(side="left", padx=4)

    def refrescar_lista(self):
        self._tree.delete(*self._tree.get_children())
        filtros = {}
        esp = self._var_esp.get() if hasattr(self, "_var_esp") else ""
        niv = self._var_niv.get() if hasattr(self, "_var_niv") else ""
        est = self._var_est.get() if hasattr(self, "_var_est") else ""
        if esp:
            filtros["especialidad"] = esp
        if niv:
            filtros["nivel_cert"] = niv
        resp = self.proxy.buscar_tecnicos(**filtros)
        if resp["status"] != "OK":
            mostrar_error("Error", resp.get("message", "Error al listar técnicos."))
            return
        tecnicos = resp["data"] or []
        # Filtro de estatus se aplica en cliente (no requiere cambio en servidor)
        if est:
            tecnicos = [t for t in tecnicos if t.get("estatus") == est]
        for t in tecnicos:
            tag = "inactivo" if t.get("estatus") == "Inactivo" else ""
            self._tree.insert("", "end", iid=t["id_tecnico"],
                              values=(
                                  t.get("id_tecnico", ""),
                                  t.get("nombre", ""),
                                  t.get("rfc", ""),
                                  t.get("telefono", ""),
                                  t.get("correo", ""),
                                  t.get("estatus", ""),
                              ), tags=(tag,))
        self._tree.tag_configure("inactivo", foreground=COLORES["texto_muted"])

    def _limpiar_filtros(self):
        self._var_esp.set("")
        self._var_niv.set("")
        self._var_est.set("")
        self.refrescar_lista()

    def _al_sel(self, _):
        sel = self._tree.selection()
        self._id_sel = sel[0] if sel else None

    def _nuevo(self):
        _DialogoTecnico(self, self.proxy, modo="nuevo", on_guardado=self.refrescar_lista)

    def _editar(self):
        if not self._id_sel:
            mostrar_error("Selección", "Seleccione un técnico.")
            return
        _DialogoTecnico(self, self.proxy, modo="editar",
                        id_tecnico=self._id_sel, on_guardado=self.refrescar_lista)

    def _cambiar_estatus(self):
        if not self._id_sel:
            mostrar_error("Selección", "Seleccione un técnico.")
            return
        item = self._tree.item(self._id_sel, "values")
        estatus_actual = item[5] if item else "Activo"
        nuevo = "Inactivo" if estatus_actual == "Activo" else "Activo"
        if not confirmar("Cambiar estatus",
                         f"¿Cambiar estatus de este técnico a '{nuevo}'?"):
            return
        resp = self.proxy.cambiar_estatus_tecnico(self._id_sel, nuevo)
        if resp["status"] == "OK":
            mostrar_info("Éxito", f"Estatus actualizado a {nuevo}.")
            self.refrescar_lista()
        else:
            mostrar_error("Error", resp.get("message", "No se pudo cambiar estatus."))

    def _carga_trabajo(self):
        if not self._id_sel:
            mostrar_error("Selección", "Seleccione un técnico.")
            return
        resp = self.proxy.carga_tecnico(self._id_sel)
        if resp["status"] != "OK":
            mostrar_error("Error", resp.get("message", "Error al obtener carga."))
            return
        _DialogoCarga(self, self._id_sel, resp["data"])


# ── Diálogos ──────────────────────────────────────────────────────────────────

class _DialogoTecnico(tk.Toplevel):
    """Formulario modal para crear / editar técnico con certificaciones."""

    def __init__(self, parent, proxy, modo: str,
                 id_tecnico: str = None, on_guardado=None):
        super().__init__(parent)
        self.proxy = proxy
        self.modo = modo
        self.id_tecnico = id_tecnico
        self.on_guardado = on_guardado
        self.title("Nuevo Técnico" if modo == "nuevo" else f"Técnico — {id_tecnico}")
        self.configure(bg=COLORES["bg_panel"])
        self.resizable(False, False)
        self.grab_set()

        self._vars = {k: tk.StringVar() for k in (
            "nombre", "rfc", "telefono", "correo", "fecha_ingreso"
        )}
        # Certificaciones (hasta 3 filas)
        self._certs = [
            {"especialidad": tk.StringVar(), "nivel": tk.StringVar()}
            for _ in range(3)
        ]

        self._construir()
        if modo == "editar" and id_tecnico:
            self._cargar()

    def _construir(self):
        ttk.Label(self, text="Datos del Técnico",
                  font=FUENTE_SUBTIT, style="Titulo.TLabel").pack(pady=(16, 4), padx=20, anchor="w")

        f = ttk.Frame(self, padding=20)
        f.pack(fill="both")
        f.columnconfigure(1, weight=1)

        campos = [
            ("Nombre completo *", "nombre"),
            ("RFC *",             "rfc"),
            ("Teléfono *",        "telefono"),
            ("Correo *",          "correo"),
            ("Fecha de ingreso *\n(YYYY-MM-DD)", "fecha_ingreso"),
        ]
        for i, (lbl, key) in enumerate(campos):
            label_campo(f, lbl, i)
            entry_campo(f, self._vars[key], i)

        # Certificaciones (RF-38)
        cert_lf = ttk.LabelFrame(self, text="Certificaciones (RF-38) — hasta 3")
        cert_lf.pack(fill="x", padx=20, pady=8)
        cert_lf.columnconfigure((1, 3), weight=1)
        for row, cert in enumerate(self._certs):
            label_campo(cert_lf, f"Especialidad {row+1}:", row, 0)
            combo_campo(cert_lf, cert["especialidad"], [""] + ESPECIALIDADES, row, 1, 14)
            label_campo(cert_lf, "Nivel:", row, 2)
            combo_campo(cert_lf, cert["nivel"], [""] + NIVELES_CERT, row, 3, 6)

        self._var_msg = tk.StringVar()
        tk.Label(self, textvariable=self._var_msg, bg=COLORES["bg_panel"],
                 fg=COLORES["error"], font=FUENTE_PEQUENA, wraplength=360).pack(pady=4)

        bf = ttk.Frame(self, padding=(20, 0, 20, 20))
        bf.pack(fill="x")
        boton_acento(bf, "Guardar", self._guardar).pack(side="right", padx=4)
        ttk.Button(bf, text="Cancelar", command=self.destroy).pack(side="right")

    def _cargar(self):
        resp = self.proxy.obtener_tecnico(self.id_tecnico)
        if resp.get("status") == "OK" and resp.get("data"):
            t = resp["data"]
            for key, var in self._vars.items():
                var.set(str(t.get(key, "")))
            for i, cert in enumerate(t.get("certificaciones", [])[:3]):
                self._certs[i]["especialidad"].set(cert.get("especialidad", ""))
                self._certs[i]["nivel"].set(cert.get("nivel", ""))

    def _guardar(self):
        payload = {k: v.get().strip() for k, v in self._vars.items()}

        errores = recopilar_errores(
            nombre=validar_no_vacio(payload["nombre"], "Nombre"),
            rfc=validar_rfc(payload["rfc"]),
            tel=validar_telefono(payload["telefono"]),
            correo=validar_correo(payload["correo"]),
            fecha=validar_fecha(payload["fecha_ingreso"]),
        )
        if errores:
            self._var_msg.set("\n".join(errores))
            return

        # Recopilar certificaciones no vacías
        certificaciones = []
        for cert in self._certs:
            esp = cert["especialidad"].get()
            niv = cert["nivel"].get()
            if esp and niv:
                certificaciones.append({"especialidad": esp, "nivel": niv})

        if not certificaciones:
            self._var_msg.set("Agregue al menos una certificación.")
            return

        payload["certificaciones"] = certificaciones

        if self.modo == "nuevo":
            resp = self.proxy.crear_tecnico(payload)
        else:
            payload["id_tecnico"] = self.id_tecnico
            resp = self.proxy.actualizar_tecnico(payload)

        if resp["status"] == "OK":
            mostrar_info("Éxito", resp.get("message", "Operación exitosa."))
            if self.on_guardado:
                self.on_guardado()
            self.destroy()
        else:
            self._var_msg.set(resp.get("message", "Error al guardar."))


class _DialogoCarga(tk.Toplevel):
    def __init__(self, parent, id_tecnico: str, data):
        super().__init__(parent)
        self.title(f"Carga de trabajo — {id_tecnico}")
        self.configure(bg=COLORES["bg_panel"])
        self.geometry("640x360")
        self.grab_set()

        ttk.Label(self, text=f"ODMs activas del técnico {id_tecnico}",
                  font=FUENTE_SUBTIT, style="Titulo.TLabel").pack(pady=12, padx=12, anchor="w")

        cols = ("id_odm", "id_equipo", "estado", "fecha_prog")
        encs = ("ID ODM", "Equipo", "Estado", "Fecha Prog.")
        tree = tree_con_scroll(self, cols, encs, [120, 120, 140, 110])

        for odm in (data or []):
            tree.insert("", "end", values=(
                odm.get("id_odm", ""),
                odm.get("id_equipo", ""),
                odm.get("estado", ""),
                odm.get("fecha_programada", ""),
            ))
        if not data:
            tree.insert("", "end", values=("Sin ODMs activas", "", "", ""))

        ttk.Button(self, text="Cerrar", command=self.destroy).pack(pady=10)
