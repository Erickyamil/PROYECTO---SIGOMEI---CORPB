# gui/panel_reportes.py
# Panel de Reportes — RF-22, RF-24, RF-25, RF-46 a RF-48
# Rol: Supervisor

import tkinter as tk
from tkinter import ttk, filedialog
import csv
import io
import base64
from datetime import date, timedelta

from gui.componentes import (
    COLORES, FUENTE_SUBTIT, FUENTE_NORMAL, FUENTE_PEQUENA,
    label_campo, entry_campo, combo_campo, boton_acento,
    mostrar_error, mostrar_info, tree_con_scroll
)


class PanelReportes(ttk.Frame):
    """Panel de reportes para Supervisor."""

    def __init__(self, parent, proxy, **kw):
        super().__init__(parent, **kw)
        self.proxy = proxy
        self._construir_ui()

    def _construir_ui(self):
        ttk.Label(self, text="📊  Reportes y Exportación",
                  font=FUENTE_SUBTIT, style="Titulo.TLabel").pack(
                      pady=(10, 4), padx=12, anchor="w")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=8)

        # ── Pestaña 1: Equipos Críticos ───────────────────────────────────────
        tab_crit = ttk.Frame(nb)
        nb.add(tab_crit, text="Equipos Críticos (RF-47)")
        self._construir_tab_criticos(tab_crit)

        # ── Pestaña 2: Desempeño por Técnico ─────────────────────────────────
        tab_desemp = ttk.Frame(nb)
        nb.add(tab_desemp, text="Desempeño Técnico (RF-46)")
        self._construir_tab_desempeno(tab_desemp)

        # ── Pestaña 3: Exportar CSV ───────────────────────────────────────────
        tab_csv = ttk.Frame(nb)
        nb.add(tab_csv, text="Exportar CSV (RF-48)")
        self._construir_tab_csv(tab_csv)

    # ── Tab Equipos Críticos ──────────────────────────────────────────────────

    def _construir_tab_criticos(self, parent):
        cab = ttk.Frame(parent)
        cab.pack(fill="x", padx=12, pady=8)
        boton_acento(cab, "Cargar equipos críticos y fuera de servicio",
                     self._cargar_criticos).pack(side="left")

        cols  = ("id_equipo", "nombre", "estado", "criticidad", "ultima_odm")
        encs  = ("ID", "Nombre", "Estado", "Criticidad", "Última ODM")
        self._tree_crit = tree_con_scroll(parent, cols, encs, [90, 180, 140, 90, 120])

    def _cargar_criticos(self):
        resp = self.proxy.reporte_equipos_criticos()
        self._tree_crit.delete(*self._tree_crit.get_children())
        if resp["status"] != "OK":
            mostrar_error("Error", resp.get("message", "Error al cargar."))
            return
        for eq in (resp["data"] or []):
            self._tree_crit.insert("", "end", values=(
                eq.get("id_equipo", ""),
                eq.get("nombre", ""),
                eq.get("estado_operativo", ""),
                eq.get("criticidad", ""),
                eq.get("ultima_odm", "—"),
            ))

    # ── Tab Desempeño ─────────────────────────────────────────────────────────

    def _construir_tab_desempeno(self, parent):
        f = ttk.Frame(parent, padding=12)
        f.pack(fill="x")
        f.columnconfigure(1, weight=1)

        self._tecnicos_desempeno: dict = {}  # display -> id_tecnico

        label_campo(f, "Técnico (dejar vacío = todos):", 0)
        self._v_tec_desemp = tk.StringVar()
        self._combo_tec_desemp = ttk.Combobox(f, textvariable=self._v_tec_desemp,
                                               width=30)
        self._combo_tec_desemp.grid(row=0, column=1, sticky="ew", pady=3)

        self._d_ini  = tk.StringVar(value=str(date.today() - timedelta(days=90)))
        self._d_fin  = tk.StringVar(value=str(date.today()))

        label_campo(f, "Desde (YYYY-MM-DD):", 1); entry_campo(f, self._d_ini, 1)
        label_campo(f, "Hasta (YYYY-MM-DD):", 2); entry_campo(f, self._d_fin, 2)
        boton_acento(f, "Generar reporte", self._cargar_desempeno).grid(
            row=3, column=1, sticky="w", pady=8)
        ttk.Button(f, text="↺ Cargar técnicos",
                   command=self._cargar_tecnicos_combo).grid(row=3, column=0, sticky="w", pady=8)

        # Resultado — Treeview para múltiples técnicos
        self._res_frame = ttk.LabelFrame(parent, text="Resultado")
        self._res_frame.pack(fill="both", expand=True, padx=12, pady=4)
        cols = ("tecnico", "num_odm", "promedio_tiempo", "variacion_costo")
        encs = ("Técnico", "ODMs atendidas", "Prom. tiempo (días)", "Variación prom. (%)")
        self._tree_desemp = tree_con_scroll(self._res_frame, cols, encs, [200, 120, 160, 160])

        # Cargar técnicos al construir
        self._cargar_tecnicos_combo()

    def _cargar_tecnicos_combo(self):
        resp = self.proxy.buscar_tecnicos()
        if resp.get("status") == "OK":
            self._tecnicos_desempeno = {
                f"{t['nombre']} ({t['id_tecnico'][:8]}…)": t["id_tecnico"]
                for t in (resp.get("data") or [])
            }
            valores = ["(Todos)"] + list(self._tecnicos_desempeno.keys())
            self._combo_tec_desemp["values"] = valores

    def _cargar_desempeno(self):
        ini = self._d_ini.get().strip()
        fin = self._d_fin.get().strip()
        sel = self._v_tec_desemp.get().strip()

        self._tree_desemp.delete(*self._tree_desemp.get_children())

        if sel and sel != "(Todos)":
            # Reporte individual
            id_tec = self._tecnicos_desempeno.get(sel, sel)
            resp = self.proxy.reporte_desempeno(id_tec, ini, fin)
            if resp["status"] != "OK":
                mostrar_error("Error", resp.get("message", "Error al generar reporte."))
                return
            d = resp["data"] or {}
            self._tree_desemp.insert("", "end", values=(
                sel, d.get("num_odm", 0),
                f"{float(d.get('promedio_tiempo', 0)):.1f}",
                f"{float(d.get('variacion_costo', 0)):.2f}",
            ))
        else:
            # Reporte de todos los técnicos via exportar_csv interno
            resp = self.proxy.exportar_csv("desempeno_tecnicos",
                                           {"fecha_inicio": ini, "fecha_fin": fin})
            if resp["status"] != "OK":
                mostrar_error("Error", resp.get("message", "Error al generar reporte."))
                return
            # Fallback: iterate known technicians
            for display, id_tec in self._tecnicos_desempeno.items():
                r = self.proxy.reporte_desempeno(id_tec, ini, fin)
                if r.get("status") == "OK":
                    d = r["data"] or {}
                    self._tree_desemp.insert("", "end", values=(
                        display, d.get("num_odm", 0),
                        f"{float(d.get('promedio_tiempo', 0)):.1f}",
                        f"{float(d.get('variacion_costo', 0)):.2f}",
                    ))

    # ── Tab Exportar CSV ──────────────────────────────────────────────────────

    def _construir_tab_csv(self, parent):
        f = ttk.Frame(parent, padding=20)
        f.pack(fill="x")
        f.columnconfigure(1, weight=1)

        self._csv_tipo = tk.StringVar()
        self._csv_ini  = tk.StringVar(value=str(date.today() - timedelta(days=30)))
        self._csv_fin  = tk.StringVar(value=str(date.today()))

        label_campo(f, "Tipo de reporte *:", 0)
        combo_campo(f, self._csv_tipo, [
            "odms", "equipos_criticos", "desempeno_tecnicos"
        ], 0, 1, 22)
        label_campo(f, "Desde:", 1); entry_campo(f, self._csv_ini, 1)
        label_campo(f, "Hasta:", 2); entry_campo(f, self._csv_fin, 2)

        boton_acento(f, "Exportar CSV (RF-48)", self._exportar_csv).grid(
            row=3, column=1, sticky="w", pady=12)

        ttk.Label(f, text="El archivo se descargará en la ubicación que elija.",
                  style="Muted.TLabel").grid(row=4, column=0, columnspan=2, sticky="w")

    def _exportar_csv(self):
        tipo = self._csv_tipo.get()
        if not tipo:
            mostrar_error("Selección", "Seleccione un tipo de reporte.")
            return

        params = {"fecha_inicio": self._csv_ini.get(), "fecha_fin": self._csv_fin.get()}
        resp = self.proxy.exportar_csv(tipo, params)

        if resp["status"] != "OK":
            mostrar_error("Error", resp.get("message", "Error al exportar."))
            return

        data = resp.get("data", {}) or {}
        contenido_b64 = data.get("contenido_base64")
        if not contenido_b64:
            mostrar_error("Error", "El servidor no devolvió contenido CSV.")
            return

        ruta = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            initialfile=f"sigomei_{tipo}.csv"
        )
        if not ruta:
            return
        try:
            contenido = base64.b64decode(contenido_b64)
            with open(ruta, "wb") as fp:
                fp.write(contenido)
            mostrar_info("Exportado", f"Archivo guardado en:\n{ruta}")
        except Exception as exc:
            mostrar_error("Error al guardar", str(exc))
