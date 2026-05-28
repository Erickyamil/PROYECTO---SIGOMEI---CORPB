"""
Ejecuta este script UNA VEZ para obtener los INSERT correctos con hashes bcrypt reales.
Requiere: pip install bcrypt

Uso:
    python generar_usuarios_bcrypt.py

Luego copia los INSERT generados y ejecútalos en tu MySQL (reemplaza los placeholders del DDL).
"""

import bcrypt

usuarios = [
    {
        "id_usuario": "u-0001-admin",
        "correo": "admin@sigomei.mx",
        "password": "Admin@SIGOMEI1",
        "rol": "Administrador",
    },
    {
        "id_usuario": "u-0002-super",
        "correo": "super@sigomei.mx",
        "password": "Super@SIGOMEI1",
        "rol": "Supervisor",
    },
    {
        "id_usuario": "u-0003-super",
        "correo": "super2@sigomei.mx",
        "password": "Super@SIGOMEI2",
        "rol": "Supervisor",
    },
]

print("-- ─────────────────────────────────────────────────────────")
print("-- Usuarios SIGOMEI con hashes bcrypt reales")
print("-- Ejecutar en MySQL DESPUÉS de crear la BD (sigomei_bd.txt)")
print("-- ─────────────────────────────────────────────────────────\n")
print("USE sigomei_db;")
# Se actualizó el DELETE para incluir al tercer usuario
print("DELETE FROM usuario WHERE id_usuario IN ('u-0001-admin', 'u-0002-super', 'u-0003-super');\n")

for u in usuarios:
    hash_bytes = bcrypt.hashpw(u["password"].encode("utf-8"), bcrypt.gensalt(rounds=12))
    hash_str = hash_bytes.decode("utf-8")
    print(f"-- {u['rol']}: {u['correo']}  /  password: {u['password']}")
    print(
        f"INSERT INTO usuario (id_usuario, correo, password_hash, rol) VALUES\n"
        f"('{u['id_usuario']}', '{u['correo']}', '{hash_str}', '{u['rol']}');\n"
    )

print("-- ─────────────────────────────────────────────────────────")
print("-- Listo. Hashes generados correctamente.")