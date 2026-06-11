"""
Pruebas Arreglo 3 (lista negra + fraude) con el test client de Flask.
Ejecutar: python test_arreglo3.py  (requiere BD recien regenerada)
"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

import app as flask_app
from database import DB_PATH

OK, FALLA = "OK", "FALLA"
resultados = []

def chk(ac, cond, detalle):
    estado = OK if cond else FALLA
    resultados.append((ac, estado))
    print(f"  {ac}: {estado} - {detalle}")

def db_con():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

client = flask_app.app.test_client()

def login(correo, pwd):
    return client.post("/login", data={"correo": correo, "password": pwd}, follow_redirects=True)

# ── Preparacion: el vendedor (vend@mail.mx, id 4) tiene subastas activas en el seed ──
con = db_con()
vend = con.execute("SELECT id_usuario FROM usuario WHERE correo='vend@mail.mx'").fetchone()
vend_id = vend["id_usuario"]
activas_antes = con.execute(
    """SELECT COUNT(*) c FROM subasta s JOIN articulo a ON a.id_articulo=s.id_articulo
       WHERE a.id_vendedor=? AND s.id_estado=1""", (vend_id,)).fetchone()["c"]
con.close()
print(f"Vendedor id={vend_id} con {activas_antes} subasta(s) activa(s) antes del fraude\n")

# ── AC-15: Cancelar por fraude ───────────────────────────────────────────────
print("AC-15 Cancelar por fraude")
login("admin@subasta.mx", "Admin1234")
client.post(f"/admin/usuario/{vend_id}", data={"accion": "CancelarFraude"}, follow_redirects=True)

con = db_con()
correo_vend = con.execute("SELECT correo FROM usuario WHERE id_usuario=?", (vend_id,)).fetchone()["correo"]
en_ln = con.execute("SELECT COUNT(*) c FROM lista_negra WHERE correo=?", (correo_vend,)).fetchone()["c"]
estado_cuenta = con.execute("SELECT id_estado FROM usuario WHERE id_usuario=?", (vend_id,)).fetchone()["id_estado"]
activas_despues = con.execute(
    """SELECT COUNT(*) c FROM subasta s JOIN articulo a ON a.id_articulo=s.id_articulo
       WHERE a.id_vendedor=? AND s.id_estado=1""", (vend_id,)).fetchone()["c"]
canceladas = con.execute(
    """SELECT COUNT(*) c FROM subasta s JOIN articulo a ON a.id_articulo=s.id_articulo
       WHERE a.id_vendedor=? AND s.id_estado=4""", (vend_id,)).fetchone()["c"]
# notificaciones MSG-12 a participantes de las subastas canceladas
notif12 = con.execute("SELECT COUNT(*) c FROM notificacion WHERE mensaje LIKE 'MSG-12%' AND tipo='Advertencia'").fetchone()["c"]
con.close()

chk("AC-15a", en_ln == 1, f"correo '{correo_vend}' en lista_negra={en_ln} (esperado 1)")
chk("AC-15b", estado_cuenta == 2, f"id_estado cuenta={estado_cuenta} (esperado 2=Suspendida)")
chk("AC-15c", activas_despues == 0, f"subastas activas tras fraude={activas_despues} (esperado 0)")
chk("AC-15d", canceladas >= activas_antes and activas_antes > 0, f"subastas canceladas={canceladas} (>= {activas_antes} previas)")
chk("AC-15e", notif12 >= 1, f"notificaciones MSG-12 a participantes={notif12} (esperado >=1)")

# ── AC-16: Registro con correo en lista negra ────────────────────────────────
print("\nAC-16 Registro bloqueado por lista negra")
con = db_con()
antes16 = con.execute("SELECT COUNT(*) c FROM usuario WHERE correo='fraude@mail.mx'").fetchone()["c"]
con.close()
client.get("/logout")
r16 = client.post("/registro", data={
    "nombre": "Intruso", "correo": "fraude@mail.mx",
    "password": "Test12345", "terminos": "on"
}, follow_redirects=True)
con = db_con()
despues16 = con.execute("SELECT COUNT(*) c FROM usuario WHERE correo='fraude@mail.mx'").fetchone()["c"]
con.close()
texto16 = r16.get_data(as_text=True)
chk("AC-16", despues16 == antes16 and ("ERR-12" in texto16 or despues16 == 0),
    f"usuario creado={despues16>antes16} (esperado NO), ERR-12 mostrado={'ERR-12' in texto16}")

# ── AC-17: Registro con correo limpio (no-regresion) ─────────────────────────
print("\nAC-17 Registro con correo limpio")
r17 = client.post("/registro", data={
    "nombre": "Usuario Limpio", "correo": "nuevo@mail.mx",
    "password": "Test12345", "terminos": "on"
}, follow_redirects=True)
con = db_con()
creado17 = con.execute("SELECT COUNT(*) c FROM usuario WHERE correo='nuevo@mail.mx'").fetchone()["c"]
con.close()
chk("AC-17", creado17 == 1, f"usuario 'nuevo@mail.mx' creado={creado17} (esperado 1)")

# ── Resumen ──────────────────────────────────────────────────────────────────
print("\n" + "="*50)
fallidos = [r for r in resultados if r[1] == FALLA]
print(f"RESUMEN: {len(resultados)-len(fallidos)}/{len(resultados)} OK")
print("TODOS PASARON" if not fallidos else "FALLARON: " + ", ".join(r[0] for r in fallidos))
print("="*50)
