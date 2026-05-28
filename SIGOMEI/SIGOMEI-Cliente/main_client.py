# main_client.py
# Punto de arranque del cliente SIGOMEI
# Uso: python main_client.py [host] [puerto]
#   Ej.: python main_client.py 192.168.1.10 9000

import sys
import tkinter as tk

from gui.componentes import aplicar_estilo_global, COLORES
from gui.login import LoginFrame
from network.client_proxy import ClientProxy

# ── Configuración de conexión (puede sobreescribirse con argumentos CLI) ──────
HOST_SERVIDOR = "127.0.0.1"
PUERTO        = 9000


def main():
    host   = sys.argv[1] if len(sys.argv) > 1 else HOST_SERVIDOR
    puerto = int(sys.argv[2]) if len(sys.argv) > 2 else PUERTO

    proxy = ClientProxy(host=host, port=puerto)

    root = tk.Tk()
    root.title("SIGOMEI — Inicio de sesión")
    root.geometry("520x400")
    root.minsize(460, 360)
    aplicar_estilo_global(root)

    def mostrar_login():
        """Borra el contenido actual y muestra la pantalla de login."""
        for widget in root.winfo_children():
            widget.destroy()
        login_frame = LoginFrame(root, proxy, on_login_exitoso=abrir_ventana_principal)
        login_frame.pack(fill="both", expand=True)

    def abrir_ventana_principal():
        """Abre la ventana principal y oculta (no destruye) la raíz."""
        root.withdraw()   # Ocultar root durante la sesión
        from gui.ventana_principal import VentanaPrincipal
        vp = VentanaPrincipal(root, proxy, on_logout=regresar_al_login)
        vp.lift()

    def regresar_al_login():
        """Vuelve a la pantalla de login al cerrar sesión."""
        root.deiconify()
        mostrar_login()

    mostrar_login()
    root.mainloop()


if __name__ == "__main__":
    main()
