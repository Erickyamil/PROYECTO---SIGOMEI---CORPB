# gui/componentes.py
# Widgets reutilizables para toda la GUI de SIGOMEI

import tkinter as tk
from tkinter import ttk, messagebox


# ── Paleta de colores SIGOMEI ────────────────────────────────────────────────
COLORES = {
    "bg_principal":  "#0F1923",   # Azul noche industrial
    "bg_panel":      "#1A2535",
    "bg_tarjeta":    "#243044",
    "acento":        "#00D4AA",   # Verde menta
    "acento_hover":  "#00FFD0",
    "alerta":        "#FF6B35",   # Naranja crítico
    "error":         "#E53E3E",
    "texto":         "#E8F0FE",
    "texto_muted":   "#7A8FA6",
    "borde":         "#2D4160",
    "ok":            "#38B2AC",
    "estado_prog":   "#3182CE",
    "estado_ejec":   "#ECC94B",
    "estado_fin":    "#38B2AC",
    "estado_cancel": "#FC8181",
    "estado_rev":    "#9F7AEA",
    "estado_esp":    "#F6AD55",
}

FUENTE_TITULO  = ("Consolas", 18, "bold")
FUENTE_SUBTIT  = ("Consolas", 13, "bold")
FUENTE_NORMAL  = ("Segoe UI", 10)
FUENTE_PEQUENA = ("Segoe UI", 9)
FUENTE_MONO    = ("Consolas", 10)


def aplicar_estilo_global(root: tk.Tk):
    """Aplica tema oscuro global a ttk y tk."""
    root.configure(bg=COLORES["bg_principal"])
    style = ttk.Style(root)
    style.theme_use("clam")

    # Frame / LabelFrame
    style.configure("TFrame", background=COLORES["bg_panel"])
    style.configure("Card.TFrame", background=COLORES["bg_tarjeta"])
    style.configure("TLabelframe", background=COLORES["bg_panel"],
                    foreground=COLORES["acento"], bordercolor=COLORES["borde"])
    style.configure("TLabelframe.Label", background=COLORES["bg_panel"],
                    foreground=COLORES["acento"], font=FUENTE_SUBTIT)

    # Labels
    style.configure("TLabel", background=COLORES["bg_panel"],
                    foreground=COLORES["texto"], font=FUENTE_NORMAL)
    style.configure("Muted.TLabel", background=COLORES["bg_panel"],
                    foreground=COLORES["texto_muted"], font=FUENTE_PEQUENA)
    style.configure("Titulo.TLabel", background=COLORES["bg_principal"],
                    foreground=COLORES["acento"], font=FUENTE_TITULO)
    style.configure("Alerta.TLabel", background=COLORES["bg_panel"],
                    foreground=COLORES["alerta"], font=FUENTE_NORMAL)

    # Botones
    style.configure("TButton", background=COLORES["bg_tarjeta"],
                    foreground=COLORES["texto"], font=FUENTE_NORMAL,
                    borderwidth=1, relief="flat", padding=6)
    style.map("TButton",
              background=[("active", COLORES["borde"])],
              foreground=[("active", COLORES["acento"])])
    style.configure("Acento.TButton", background=COLORES["acento"],
                    foreground="#0F1923", font=("Segoe UI", 10, "bold"), padding=8)
    style.map("Acento.TButton",
              background=[("active", COLORES["acento_hover"])])
    style.configure("Peligro.TButton", background=COLORES["error"],
                    foreground="white", font=FUENTE_NORMAL, padding=6)
    style.map("Peligro.TButton",
              background=[("active", "#C53030")])

    # Entry
    style.configure("TEntry", fieldbackground=COLORES["bg_tarjeta"],
                    foreground=COLORES["texto"], insertcolor=COLORES["acento"],
                    bordercolor=COLORES["borde"], font=FUENTE_NORMAL)

    # Combobox
    style.configure("TCombobox", fieldbackground=COLORES["bg_tarjeta"],
                    background=COLORES["bg_tarjeta"],
                    foreground=COLORES["texto"], font=FUENTE_NORMAL)
    style.map("TCombobox", fieldbackground=[("readonly", COLORES["bg_tarjeta"])])

    # Treeview
    style.configure("Treeview", background=COLORES["bg_tarjeta"],
                    foreground=COLORES["texto"], fieldbackground=COLORES["bg_tarjeta"],
                    rowheight=26, font=FUENTE_NORMAL)
    style.configure("Treeview.Heading", background=COLORES["bg_panel"],
                    foreground=COLORES["acento"], font=("Segoe UI", 10, "bold"))
    style.map("Treeview",
              background=[("selected", COLORES["borde"])],
              foreground=[("selected", COLORES["acento"])])

    # Notebook (pestañas)
    style.configure("TNotebook", background=COLORES["bg_principal"])
    style.configure("TNotebook.Tab", background=COLORES["bg_panel"],
                    foreground=COLORES["texto_muted"], font=FUENTE_NORMAL, padding=[12, 6])
    style.map("TNotebook.Tab",
              background=[("selected", COLORES["bg_tarjeta"])],
              foreground=[("selected", COLORES["acento"])])

    # Scrollbar
    style.configure("TScrollbar", background=COLORES["bg_panel"],
                    troughcolor=COLORES["bg_principal"], arrowcolor=COLORES["texto_muted"])

    # Separator
    style.configure("TSeparator", background=COLORES["borde"])


# ── Widget helpers ────────────────────────────────────────────────────────────

def label_campo(parent, texto: str, row: int, col: int = 0, **kw):
    lbl = ttk.Label(parent, text=texto, style="Muted.TLabel")
    lbl.grid(row=row, column=col, sticky="w", padx=(0, 8), pady=3, **kw)
    return lbl


def entry_campo(parent, variable: tk.StringVar, row: int, col: int = 1,
                ancho: int = 28, show: str = "", **kw):
    e = ttk.Entry(parent, textvariable=variable, width=ancho, show=show)
    e.grid(row=row, column=col, sticky="ew", pady=3, **kw)
    return e


def combo_campo(parent, variable: tk.StringVar, valores: list,
                row: int, col: int = 1, ancho: int = 26, **kw):
    c = ttk.Combobox(parent, textvariable=variable, values=valores,
                     state="readonly", width=ancho)
    c.grid(row=row, column=col, sticky="ew", pady=3, **kw)
    return c


def boton_acento(parent, texto: str, comando, **kw):
    return ttk.Button(parent, text=texto, command=comando,
                      style="Acento.TButton", **kw)


def boton_peligro(parent, texto: str, comando, **kw):
    return ttk.Button(parent, text=texto, command=comando,
                      style="Peligro.TButton", **kw)


def mostrar_error(titulo: str, mensaje: str):
    messagebox.showerror(titulo, mensaje)


def mostrar_info(titulo: str, mensaje: str):
    messagebox.showinfo(titulo, mensaje)


def confirmar(titulo: str, mensaje: str) -> bool:
    return messagebox.askyesno(titulo, mensaje)


def color_estado(estado: str) -> str:
    mapa = {
        "En_revision":        COLORES["estado_rev"],
        "Programada":         COLORES["estado_prog"],
        "En_Ejecucion":       COLORES["estado_ejec"],
        "En_espera_material": COLORES["estado_esp"],
        "Finalizada":         COLORES["estado_fin"],
        "Cancelada":          COLORES["estado_cancel"],
    }
    return mapa.get(estado, COLORES["texto_muted"])


def tree_con_scroll(parent, columnas: list[str], encabezados: list[str],
                    anchos: list[int] = None) -> ttk.Treeview:
    """Crea un Treeview con scrollbars vertical y horizontal."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)

    vsb = ttk.Scrollbar(frame, orient="vertical")
    hsb = ttk.Scrollbar(frame, orient="horizontal")

    tree = ttk.Treeview(frame, columns=columnas, show="headings",
                        yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    vsb.configure(command=tree.yview)
    hsb.configure(command=tree.xview)

    vsb.pack(side="right", fill="y")
    hsb.pack(side="bottom", fill="x")
    tree.pack(fill="both", expand=True)

    for i, col in enumerate(columnas):
        encabezado = encabezados[i] if i < len(encabezados) else col
        ancho = anchos[i] if anchos and i < len(anchos) else 120
        tree.heading(col, text=encabezado)
        tree.column(col, width=ancho, minwidth=60, anchor="w")

    return tree


class BarraEstado(tk.Frame):
    """Barra de estado en la parte inferior de la ventana principal."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=COLORES["bg_panel"],
                         highlightbackground=COLORES["borde"],
                         highlightthickness=1, **kw)
        self._var = tk.StringVar(value="Listo")
        self._lbl = tk.Label(self, textvariable=self._var,
                             bg=COLORES["bg_panel"], fg=COLORES["texto_muted"],
                             font=FUENTE_PEQUENA, anchor="w", padx=10)
        self._lbl.pack(side="left", fill="x", expand=True)

        self._conn = tk.Label(self, text="⬤ Desconectado",
                              bg=COLORES["bg_panel"], fg=COLORES["error"],
                              font=FUENTE_PEQUENA, padx=10)
        self._conn.pack(side="right")

    def set_mensaje(self, msg: str, color: str = None):
        self._var.set(msg)
        if color:
            self._lbl.configure(fg=color)
        else:
            self._lbl.configure(fg=COLORES["texto_muted"])

    def set_conectado(self, conectado: bool):
        if conectado:
            self._conn.configure(text="⬤ Conectado", fg=COLORES["ok"])
        else:
            self._conn.configure(text="⬤ Desconectado", fg=COLORES["error"])
