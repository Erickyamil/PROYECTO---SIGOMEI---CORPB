# gui/login.py
# Pantalla de inicio de sesión — RF-01 a RF-04, RF-28 a RF-30

import tkinter as tk
from tkinter import ttk

from gui.componentes import (
    COLORES, FUENTE_TITULO, FUENTE_NORMAL, FUENTE_PEQUENA,
    aplicar_estilo_global, mostrar_error, boton_acento
)
from utils.gui_validators import validar_correo, validar_no_vacio
from utils.session import Session


class LoginFrame(tk.Frame):
    """
    Pantalla de inicio de sesión.
    Callback on_login_exitoso(proxy) se invoca cuando el servidor responde OK.
    """

    MAX_INTENTOS = 5  # RF-29: bloqueo por intentos fallidos

    def __init__(self, parent, proxy, on_login_exitoso, **kw):
        super().__init__(parent, bg=COLORES["bg_principal"], **kw)
        self.proxy = proxy
        self.on_login_exitoso = on_login_exitoso
        self._intentos = 0

        self._construir_ui()

    def _construir_ui(self):
        # Panel centrado
        contenedor = tk.Frame(self, bg=COLORES["bg_panel"],
                              highlightbackground=COLORES["borde"],
                              highlightthickness=1)
        contenedor.place(relx=0.5, rely=0.5, anchor="center")

        # Logo / Título
        tk.Label(contenedor, text="SIGOMEI", font=("Consolas", 28, "bold"),
                 bg=COLORES["bg_panel"], fg=COLORES["acento"]).pack(pady=(36, 4))
        tk.Label(contenedor,
                 text="Sistema de Gestión de Mantenimiento Industrial",
                 font=FUENTE_PEQUENA,
                 bg=COLORES["bg_panel"], fg=COLORES["texto_muted"]).pack(pady=(0, 28))

        form = tk.Frame(contenedor, bg=COLORES["bg_panel"], padx=40)
        form.pack(fill="x", padx=40)

        # Correo
        tk.Label(form, text="Correo electrónico", font=FUENTE_PEQUENA,
                 bg=COLORES["bg_panel"], fg=COLORES["texto_muted"]).pack(anchor="w")
        self._var_correo = tk.StringVar()
        e_correo = tk.Entry(form, textvariable=self._var_correo, width=32,
                            bg=COLORES["bg_tarjeta"], fg=COLORES["texto"],
                            insertbackground=COLORES["acento"],
                            relief="flat", font=FUENTE_NORMAL,
                            highlightbackground=COLORES["borde"],
                            highlightthickness=1)
        e_correo.pack(fill="x", pady=(2, 12), ipady=6)
        e_correo.focus_set()

        # Contraseña
        tk.Label(form, text="Contraseña", font=FUENTE_PEQUENA,
                 bg=COLORES["bg_panel"], fg=COLORES["texto_muted"]).pack(anchor="w")
        self._var_pass = tk.StringVar()
        e_pass = tk.Entry(form, textvariable=self._var_pass, width=32, show="●",
                          bg=COLORES["bg_tarjeta"], fg=COLORES["texto"],
                          insertbackground=COLORES["acento"],
                          relief="flat", font=FUENTE_NORMAL,
                          highlightbackground=COLORES["borde"],
                          highlightthickness=1)
        e_pass.pack(fill="x", pady=(2, 20), ipady=6)
        e_pass.bind("<Return>", lambda _: self._intentar_login())

        # Mensaje de estado
        self._var_msg = tk.StringVar()
        self._lbl_msg = tk.Label(form, textvariable=self._var_msg,
                                 bg=COLORES["bg_panel"], fg=COLORES["error"],
                                 font=FUENTE_PEQUENA, wraplength=260)
        self._lbl_msg.pack(pady=(0, 8))

        # Botón
        btn = tk.Button(form, text="INICIAR SESIÓN", command=self._intentar_login,
                        bg=COLORES["acento"], fg="#0F1923",
                        activebackground=COLORES["acento_hover"],
                        font=("Segoe UI", 10, "bold"),
                        relief="flat", cursor="hand2", pady=8)
        btn.pack(fill="x", pady=(0, 36))

    def _intentar_login(self):
        correo = self._var_correo.get().strip()
        password = self._var_pass.get()

        # Validaciones de formato (RNF-06)
        err_c = validar_correo(correo)
        if err_c:
            self._var_msg.set(err_c)
            return
        err_p = validar_no_vacio(password, "Contraseña")
        if err_p:
            self._var_msg.set(err_p)
            return

        self._var_msg.set("Conectando...")

        # Se envía el password en texto plano — el servidor aplica bcrypt.checkpw()
        # directamente. No se hace hashing en el cliente porque bcrypt ya incorpora
        # su propio salt y no es compatible con un pre-hash SHA-256.
        password_texto = password

        # Conectar si no está conectado
        if not self.proxy.conectado:
            if not self.proxy.conectar():
                self._var_msg.set("No se puede conectar al servidor.\nVerifique que el servidor esté activo.")
                return

        resp = self.proxy.login(correo, password_texto)

        if resp is None:
            self._var_msg.set("Sin respuesta del servidor. Verifique la red.")
            return

        status = resp.get("status")

        if status == "OK":
            datos = resp["data"]
            Session().iniciar(
                token=datos["token"],
                rol=datos["rol"],
                nombre=datos.get("nombre", correo),
                correo=correo
            )
            self._var_msg.set("")
            self.on_login_exitoso()

        elif status == "ERR_BLOCKED":
            self._var_msg.set(
                f"Cuenta bloqueada temporalmente.\n{resp.get('message', '')}"
            )

        elif status == "ERR_AUTH":
            self._intentos += 1
            restantes = self.MAX_INTENTOS - self._intentos
            if restantes > 0:
                self._var_msg.set(
                    f"Credenciales incorrectas. Intentos restantes: {restantes}"
                )
            else:
                self._var_msg.set("Demasiados intentos fallidos. Intente más tarde.")

        else:
            msg = resp.get("message") or "Error desconocido del servidor."
            self._var_msg.set(f"Error del servidor: {msg}")
