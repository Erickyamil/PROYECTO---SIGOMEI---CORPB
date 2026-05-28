# gui/ventana_principal.py
# Ventana principal post-login — muestra pestañas según el rol del usuario

import tkinter as tk
from tkinter import ttk
import threading
import time

from gui.componentes import (
    COLORES, FUENTE_SUBTIT, FUENTE_NORMAL, FUENTE_PEQUENA,
    aplicar_estilo_global, BarraEstado, mostrar_info, confirmar
)
from gui.panel_equipos  import PanelEquipos
from gui.panel_tecnicos import PanelTecnicos
from gui.panel_odm      import PanelODM
from gui.panel_reportes import PanelReportes
from utils.session import Session

# RF-26: timeout de inactividad (segundos)
TIMEOUT_INACTIVIDAD = 30 * 60


class VentanaPrincipal(tk.Toplevel):
    """
    Ventana principal del sistema SIGOMEI.
    Crea pestañas según el rol de la sesión activa.
    Implementa cierre de sesión por inactividad (RF-26).
    """

    def __init__(self, parent, proxy, on_logout):
        super().__init__(parent)
        self.proxy = proxy
        self.on_logout = on_logout
        self._sesion = Session()
        self._ultima_actividad = time.time()

        self.title(f"SIGOMEI — {self._sesion.nombre} ({self._sesion.rol})")
        self.geometry("1100x680")
        self.minsize(900, 560)
        self.configure(bg=COLORES["bg_principal"])
        self.protocol("WM_DELETE_WINDOW", self._cerrar_sesion)

        aplicar_estilo_global(self)
        self._construir_ui()
        self._iniciar_watchdog_inactividad()

    def _construir_ui(self):
        # ── Barra superior ────────────────────────────────────────────────────
        barra_top = tk.Frame(self, bg=COLORES["bg_panel"], height=48,
                             highlightbackground=COLORES["borde"],
                             highlightthickness=1)
        barra_top.pack(fill="x")
        barra_top.pack_propagate(False)

        tk.Label(barra_top, text="⚡ SIGOMEI",
                 bg=COLORES["bg_panel"], fg=COLORES["acento"],
                 font=("Consolas", 14, "bold")).pack(side="left", padx=16)

        tk.Label(barra_top,
                 text=f"{self._sesion.nombre}  •  {self._sesion.rol}",
                 bg=COLORES["bg_panel"], fg=COLORES["texto_muted"],
                 font=FUENTE_PEQUENA).pack(side="left", padx=8)

        tk.Button(barra_top, text="Cerrar sesión",
                  command=self._cerrar_sesion,
                  bg=COLORES["bg_tarjeta"], fg=COLORES["texto"],
                  activebackground=COLORES["error"],
                  font=FUENTE_PEQUENA, relief="flat", padx=10, pady=4,
                  cursor="hand2").pack(side="right", padx=12)

        # ── Notebook de módulos ───────────────────────────────────────────────
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=0, pady=0)
        nb.bind("<<NotebookTabChanged>>", self._reset_inactividad)

        # Pestañas por rol
        if self._sesion.es_admin:
            tab_eq = PanelEquipos(nb, self.proxy)
            nb.add(tab_eq, text="  ⚙ Equipos  ")

            tab_tec = PanelTecnicos(nb, self.proxy)
            nb.add(tab_tec, text="  👷 Técnicos  ")

        if self._sesion.es_supervisor or self._sesion.es_admin:
            tab_odm = PanelODM(nb, self.proxy)
            nb.add(tab_odm, text="  📋 Órdenes (ODM)  ")

            tab_rep = PanelReportes(nb, self.proxy)
            nb.add(tab_rep, text="  📊 Reportes  ")

        # ── Barra de estado inferior ──────────────────────────────────────────
        self._barra_est = BarraEstado(self)
        self._barra_est.pack(fill="x", side="bottom")
        self._barra_est.set_conectado(self.proxy.conectado)
        self._barra_est.set_mensaje(f"Sesión iniciada como {self._sesion.nombre}")

        # Registrar actividad ante cualquier evento en la ventana
        self.bind_all("<Motion>",  self._reset_inactividad)
        self.bind_all("<KeyPress>", self._reset_inactividad)
        self.bind_all("<Button>",   self._reset_inactividad)

    # ── Inactividad (RF-26) ───────────────────────────────────────────────────

    def _reset_inactividad(self, *_):
        self._ultima_actividad = time.time()

    def _iniciar_watchdog_inactividad(self):
        def watchdog():
            while self.winfo_exists():
                inactividad = time.time() - self._ultima_actividad
                if inactividad >= TIMEOUT_INACTIVIDAD:
                    self.after(0, self._cerrar_por_inactividad)
                    return
                # Actualizar estado de conexión periódicamente
                self.after(0, lambda: self._barra_est.set_conectado(self.proxy.conectado))
                time.sleep(30)
        t = threading.Thread(target=watchdog, daemon=True)
        t.start()

    def _cerrar_por_inactividad(self):
        if self.winfo_exists():
            mostrar_info("Sesión expirada",
                         "La sesión se cerró por inactividad (RF-26).")
            self._cerrar_sesion(forzado=True)

    def _cerrar_sesion(self, forzado: bool = False):
        if not forzado:
            if not confirmar("Cerrar sesión", "¿Desea cerrar la sesión actual?"):
                return
        self.proxy.logout()
        Session().cerrar()
        self.destroy()
        self.on_logout()
