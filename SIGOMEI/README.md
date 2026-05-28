# SIGOMEI — Sistema de Gestión de Mantenimiento Industrial

**Universidad Veracruzana · Ingeniería de Software · Desarrollo de Sistemas en Red**

Arquitectura cliente-servidor TCP/JSON. El servidor accede a MySQL; el cliente
**nunca** toca la base de datos directamente.

---

## Estructura del proyecto

```
SIGOMEI/
├── README.md
├── CU-17_Reformulacion.md         ← Caso de uso 17 reformulado (ver carga de trabajo)
├── SIGOMEI-Server/                ← Servidor Python
│   ├── server.properties          ← Configuración externa (credenciales, puertos)
│   ├── main_server.py             ← Punto de entrada del servidor
│   ├── app.py                     ← Configuración de la aplicación
│   ├── config.py                  ← Carga server.properties + configura logging
│   ├── generar_usuarios_bcrypt.py ← Script para generar usuarios de prueba
│   ├── requirements.txt
│   ├── db/
│   │   ├── sigomei_db.sql         ← DDL completo + datos iniciales
│   │   └── connection.py          ← Pool de conexiones MySQL
│   ├── communication/
│   │   └── socket_server.py       ← Servidor de sockets TCP/JSON
│   ├── services/                  ← Lógica de negocio
│   │   ├── service.py             ← ServiceLayer (orquesta repositorio + validadores)
│   │   ├── validators.py          ← Reglas de negocio (RN-03, RN-06, RN-07...)
│   │   └── schemas.py             ← Validación de payloads entrantes
│   ├── repository/
│   │   └── repository.py          ← Acceso a MySQL (única capa que toca la BD)
│   ├── models/
│   │   ├── equipo.py
│   │   ├── odm.py
│   │   └── tecnico.py
│   ├── routes/
│   │   ├── equipo_routes.py
│   │   ├── odm_routes.py
│   │   └── tecnico_routes.py
│   └── tests/
│       ├── test_service.py
│       └── test_validators.py
└── SIGOMEI-Cliente/               ← Cliente de escritorio (tkinter)
    ├── main_client.py             ← Punto de entrada del cliente
    ├── requirements.txt
    ├── network/
    │   └── client_proxy.py        ← Única capa de red del cliente
    ├── gui/
    │   ├── componentes.py         ← Widgets y estilos reutilizables
    │   ├── login.py               ← Pantalla de inicio de sesión
    │   ├── ventana_principal.py   ← Contenedor principal con pestañas
    │   ├── panel_equipos.py       ← Gestión de equipos (RF-05 a RF-08, RF-31 a RF-34)
    │   ├── panel_tecnicos.py      ← Gestión de técnicos (RF-09 a RF-12, RF-36)
    │   ├── panel_odm.py           ← Órdenes de mantenimiento (RF-13 a RF-29)
    │   └── panel_reportes.py      ← Reportes y exportación (RF-30 a RF-35)
    └── utils/
        ├── gui_validators.py      ← Validaciones de campos en formularios
        └── session.py             ← Manejo de sesión activa en el cliente
```

---

## Requisitos previos

| Herramienta  | Versión mínima | Verificación           |
|--------------|----------------|------------------------|
| Python       | 3.10+          | `python --version`     |
| MySQL Server | 8.0+           | `mysql --version`      |
| tkinter      | incluido en Python estándar | `python -m tkinter` |

> **Linux:** tkinter requiere instalación aparte:
> ```bash
> sudo apt install python3-tk
> ```

---

## 1. Preparar la base de datos (solo la primera vez)

```bash
# Crear el esquema y tablas
mysql -u root -p < SIGOMEI-Server/db/sigomei_db.sql

# Generar e insertar usuarios de prueba (hashes bcrypt)
cd SIGOMEI-Server
python generar_usuarios_bcrypt.py
# El script imprime los INSERT en consola; ejecútalos en MySQL Workbench o en tu cliente SQL.
```

> **Restablecer la BD a valores originales:** repite los dos comandos anteriores.
> Si necesitas partir de cero, primero ejecuta en MySQL:
> ```sql
> DROP DATABASE sigomei_db;
> CREATE DATABASE sigomei_db;
> ```
> Luego vuelve a correr `sigomei_db.sql` y `generar_usuarios_bcrypt.py`.

---

## 2. Configurar el servidor

Edita **`SIGOMEI-Server/server.properties`** con tus credenciales reales:

```properties
SIGOMEI_DB_HOST=127.0.0.1
SIGOMEI_DB_PORT=3306
SIGOMEI_DB_USER=root
SIGOMEI_DB_PASSWORD=tu_password_real
SIGOMEI_DB_NAME=sigomei_db

SIGOMEI_SERVER_HOST=0.0.0.0
SIGOMEI_SERVER_PORT=9000

# Bitácora: ruta del archivo de log (dejar vacío = solo consola)
SIGOMEI_LOG_FILE=sigomei_server.log
SIGOMEI_LOG_LEVEL=INFO
```

> Las variables de entorno del SO tienen **prioridad** sobre `server.properties`.
> Esto permite sobreescribir valores en CI/CD sin tocar el archivo.
>
> ```bash
> # Linux/macOS
> export SIGOMEI_DB_PASSWORD=mi_password
>
> # Windows PowerShell
> $env:SIGOMEI_DB_PASSWORD = "mi_password"
>
> # Windows CMD
> set SIGOMEI_DB_PASSWORD=mi_password
> ```

---

## 3. Instalar dependencias e iniciar el servidor

```bash
cd SIGOMEI-Server

# Crear entorno virtual (recomendado)
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
.\.venv\Scripts\activate           # Windows PowerShell

# Instalar dependencias
pip install -r requirements.txt
# Dependencias: bcrypt>=4.0.0, mysql-connector-python>=8.0.0

# Iniciar el servidor
python main_server.py
```

El servidor valida la conexión a MySQL al arrancar y termina con un mensaje
de error claro si las credenciales son incorrectas.

La bitácora se escribe en `sigomei_server.log` (rotativa, máx 5 MB × 3 archivos).
Para deshabilitar el log en disco, deja `SIGOMEI_LOG_FILE` vacío en `server.properties`.

---

## 4. Iniciar el cliente

```bash
cd SIGOMEI-Cliente

# Sin dependencias externas (solo biblioteca estándar de Python + tkinter)

# Conectar al servidor en localhost:9000 (por defecto)
python main_client.py

# Conectar a un servidor remoto
python main_client.py 192.168.1.10 9000
```

> El cliente **no contiene** credenciales de base de datos ni accede a MySQL.
> Toda comunicación se realiza mediante el proxy TCP/JSON (`network/client_proxy.py`).

---

## 5. Credenciales de prueba

| Correo           | Contraseña     | Rol           |
|------------------|----------------|---------------|
| admin@sigomei.mx | Admin@SIGOMEI1 | Administrador |
| super@sigomei.mx | Super@SIGOMEI1 | Supervisor    |

---

## 6. Protocolo de comunicación

Comunicación TCP, un mensaje JSON por línea (`\n`), puerto 9000 por defecto.

**Petición (cliente → servidor):**
```json
{ "cmd": "ACCION", "token": "<token_de_sesion>", "payload": { ... } }
```

**Respuesta (servidor → cliente):**
```json
{
  "status": "OK|ERR_AUTH|ERR_BAD_REQUEST|ERR_BUSINESS|ERR_NOT_FOUND|ERR_INTERNAL|ERR_TIMEOUT",
  "message": "descripción legible",
  "data": { ... }
}
```

### Acciones soportadas

| Categoría    | Acción                    | Descripción                                      |
|--------------|---------------------------|--------------------------------------------------|
| Sesión       | `LOGIN`                   | Autenticación; devuelve token de sesión          |
|              | `LOGOUT`                  | Cierra la sesión activa                          |
|              | `ping`                    | Prueba de conectividad                           |
| Equipos      | `CREAR_EQUIPO`            | Registrar nuevo equipo industrial                |
|              | `ACTUALIZAR_EQUIPO`       | Editar datos de un equipo                        |
|              | `ELIMINAR_EQUIPO`         | Eliminar equipo (física o lógicamente según historial) |
|              | `BAJA_EQUIPO`             | Alias de `ELIMINAR_EQUIPO` (compatibilidad)      |
|              | `OBTENER_EQUIPO`          | Obtener detalle de un equipo                     |
|              | `LISTAR_EQUIPOS`          | Listar equipos con filtros opcionales            |
|              | `HISTORIAL_EQUIPO`        | ODMs históricas de un equipo                     |
| Técnicos     | `CREAR_TECNICO`           | Registrar nuevo técnico                          |
|              | `ACTUALIZAR_TECNICO`      | Editar datos de un técnico                       |
|              | `CAMBIAR_ESTATUS_TECNICO` | Activar o inactivar un técnico                   |
|              | `OBTENER_TECNICO`         | Obtener detalle de un técnico                    |
|              | `BUSCAR_TECNICOS`         | Listar técnicos con filtros (especialidad, nivel, estatus) |
|              | `CARGA_TECNICO`           | ODMs activas asignadas a un técnico              |
| ODM          | `CREAR_ODM`               | Crear orden de mantenimiento                     |
|              | `ACTUALIZAR_ESTADO_ODM`   | Cambiar estado de una ODM                        |
|              | `OBTENER_ODM`             | Obtener detalle de una ODM                       |
|              | `LISTAR_ODMS`             | Listar todas las ODMs                            |
|              | `FILTRAR_ODMS`            | Filtrar ODMs por fecha, estado, etc.             |
|              | `REASIGNAR_TECNICO_ODM`   | Cambiar técnico asignado a una ODM               |
|              | `AGREGAR_NOTA_ODM`        | Añadir nota a una ODM                            |
| Reportes     | `RESUMEN_COSTOS`          | Resumen de costos por período                    |
|              | `REPORTE_DESEMPENO`       | Desempeño de técnico(s) por período              |
|              | `REPORTE_EQUIPOS_CRITICOS`| Equipos en estado Crítico o Fuera de servicio    |
|              | `EXPORTAR_CSV`            | Exportar datos a CSV                             |

---

## 7. Reglas de negocio principales

| Clave  | Regla                                                                                      |
|--------|--------------------------------------------------------------------------------------------|
| RN-03  | Un equipo no puede tener dos ODMs activas en la misma fecha programada.                    |
| RN-06  | Un técnico no puede tener más de **3 ODMs activas** simultáneamente (cualquier estado no terminal). |
| RN-07  | Las transiciones de estado de una ODM siguen la máquina de estados definida: `Programada → En_Ejecucion → En_espera_material → Finalizada` (con `Cancelada` disponible desde cualquier estado activo). |
| RN-08  | Un técnico solo puede asignarse a una ODM si tiene certificación **vigente** en la especialidad del equipo. |
| RN-09  | No se puede eliminar un equipo que tenga órdenes activas. Si tiene historial, se aplica baja lógica; si no tiene historial alguno, se elimina físicamente. |

---

## 8. Ejecutar pruebas unitarias (servidor)

```bash
cd SIGOMEI-Server
pytest --cov=services --cov=repository --cov-report=term-missing
```

Cobertura objetivo: ≥ 90 % en la capa lógica (`services/`).

---

## Notas de seguridad

- `server.properties` **no debe incluirse en el repositorio** si contiene
  contraseñas reales. Agrega la línea `server.properties` a tu `.gitignore`.
- El cliente nunca recibe trazas internas del servidor; los errores se
  registran en la bitácora del servidor y el cliente recibe solo un mensaje
  genérico (`ERR_INTERNAL`).
- Las contraseñas de usuarios se almacenan con hash `bcrypt` (factor de costo 12).
