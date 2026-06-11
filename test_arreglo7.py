"""
Pruebas Arreglo 7 (bandeja de correos stub, C10) con test client.
Ejecutar: python test_arreglo7.py  (requiere BD recien regenerada)
"""
import sqlite3, os, sys, datetime
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))
import app as flask_app
from database import DB_PATH

OK, FALLA = "OK", "FALLA"
resultados = []
def chk(ac, cond, detalle):
    resultados.append((ac, OK if cond else FALLA))
    print(f"  {ac}: {OK if cond else FALLA} - {detalle}")

def db_con():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

client = flask_app.app.test_client()
con = db_con()
ana_id = con.execute("SELECT id_usuario FROM usuario WHERE correo='ana@mail.mx'").fetchone()["id_usuario"]

# ── AC-30: cerrar subasta con ganador -> correo_salida ───────────────────────
print("AC-30 Cierre con ganador -> correo en bandeja")
ing = con.execute("SELECT id_subasta FROM subasta WHERE id_tipo=1 LIMIT 1").fetchone()["id_subasta"]
titulo = con.execute("SELECT a.titulo FROM subasta s JOIN articulo a ON a.id_articulo=s.id_articulo WHERE s.id_subasta=?", (ing,)).fetchone()["titulo"]
pasado = (datetime.datetime.utcnow() - datetime.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
con.execute("UPDATE subasta SET fecha_fin=? WHERE id_subasta=?", (pasado, ing))
con.commit(); con.close()
client.get("/")  # dispara cierre -> ganador Ana (oferta 8500)

con = db_con()
correo = con.execute(
    "SELECT * FROM correo_salida WHERE id_destinatario=? AND asunto=?",
    (ana_id, f"Has ganado la subasta: {titulo}")
).fetchone()
con.close()
chk("AC-30", correo is not None and correo["correo_destino"] == "ana@mail.mx",
    f"correo creado={correo is not None}, destino={correo['correo_destino'] if correo else None}, asunto='{correo['asunto'] if correo else None}'")

# ── AC-31: pago vencido -> correo_salida ─────────────────────────────────────
print("\nAC-31 Pago vencido -> correo en bandeja")
con = db_con()
# El cierre anterior creo un pago pendiente para Ana. Lo vencemos.
con.execute("UPDATE pago SET fecha_limite=? WHERE id_subasta=? AND id_comprador=?",
            (pasado, ing, ana_id))
con.commit(); con.close()
client.get("/")  # dispara verificar_pagos_vencidos
con = db_con()
correo_v = con.execute(
    "SELECT * FROM correo_salida WHERE id_destinatario=? AND asunto LIKE 'Tu pago ha vencido:%'",
    (ana_id,)
).fetchone()
con.close()
chk("AC-31", correo_v is not None, f"correo de vencimiento creado={correo_v is not None}, asunto='{correo_v['asunto'] if correo_v else None}'")

# ── AC-33: acceso solo admin ─────────────────────────────────────────────────
print("\nAC-33 Acceso restringido a admin")
r_anon = client.get("/admin/correos", follow_redirects=False)
chk("AC-33a", r_anon.status_code in (301, 302), f"anonimo redirigido status={r_anon.status_code}")
client.post("/login", data={"correo": "ana@mail.mx", "password": "Ana12345"}, follow_redirects=False)
r_comp = client.get("/admin/correos", follow_redirects=False)
chk("AC-33b", r_comp.status_code in (301, 302), f"comprador redirigido status={r_comp.status_code}")
client.get("/logout")
client.post("/login", data={"correo": "admin@subasta.mx", "password": "Admin1234"}, follow_redirects=False)
r_admin = client.get("/admin/correos")
chk("AC-33c", r_admin.status_code == 200, f"admin accede status={r_admin.status_code}")

# ── AC-32: bandeja muestra los correos ───────────────────────────────────────
print("\nAC-32 /admin/correos muestra la bandeja")
html = r_admin.get_data(as_text=True)
con = db_con()
total = con.execute("SELECT COUNT(*) c FROM correo_salida").fetchone()["c"]
con.close()
muestra = (f"Has ganado la subasta: {titulo}" in html and "Tu pago ha vencido" in html)
chk("AC-32", muestra and total >= 2, f"bandeja muestra correos={muestra}, total en BD={total}")

# ── Resumen ──────────────────────────────────────────────────────────────────
print("\n" + "="*50)
fallidos = [r for r in resultados if r[1] == FALLA]
print(f"RESUMEN: {len(resultados)-len(fallidos)}/{len(resultados)} OK")
print("TODOS PASARON" if not fallidos else "FALLARON: " + ", ".join(r[0] for r in fallidos))
print("="*50)
