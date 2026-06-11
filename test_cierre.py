"""
Script de prueba para verificar_cierre_subastas.
Ejecutar con: python test_cierre.py
"""
import sqlite3
import datetime
import sys
import os

DB = os.path.join(os.path.dirname(__file__), "subasta.db")

def now_str():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def pasado_str(minutos=5):
    return (datetime.datetime.utcnow() - datetime.timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M:%S")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

art  = con.execute("SELECT id_articulo FROM articulo LIMIT 1").fetchone()
ana  = con.execute("SELECT id_usuario FROM usuario WHERE correo='ana@mail.mx'").fetchone()
admin = con.execute("SELECT id_usuario FROM usuario WHERE correo='admin@subasta.mx'").fetchone()

if not art or not ana:
    print("ERROR: no hay datos demo. Corre python database.py primero.")
    sys.exit(1)

id_art = art["id_articulo"]
id_ana = ana["id_usuario"]
id_postor2 = admin["id_usuario"]  # usamos admin como segundo postor solo para el test

pasado = pasado_str(10)

# --- TEST-A: vencida con 2 ofertas ---
con.execute(
    "INSERT INTO subasta (id_articulo,id_tipo,precio_base,precio_actual,incremento_min,fecha_inicio,fecha_fin,id_estado) VALUES(?,1,1000,1500,100,?,?,1)",
    (id_art, pasado, pasado)
)
sub_a = con.execute("SELECT last_insert_rowid()").fetchone()[0]
# segundo postor primero (menor monto y misma fecha → pierde)
con.execute("INSERT INTO oferta (id_subasta,id_comprador,monto) VALUES(?,?,?)", (sub_a, id_postor2, 1200))
# ana con mayor monto → debe ganar
con.execute("INSERT INTO oferta (id_subasta,id_comprador,monto) VALUES(?,?,?)", (sub_a, id_ana, 1500))
print(f"[SETUP] TEST-A id_subasta={sub_a}: vencida, 2 ofertas, ganador esperado=ana (id={id_ana})")

# --- TEST-B: vencida sin ofertas ---
con.execute(
    "INSERT INTO subasta (id_articulo,id_tipo,precio_base,precio_actual,incremento_min,fecha_inicio,fecha_fin,id_estado) VALUES(?,1,2000,2000,100,?,?,1)",
    (id_art, pasado, pasado)
)
sub_b = con.execute("SELECT last_insert_rowid()").fetchone()[0]
print(f"[SETUP] TEST-B id_subasta={sub_b}: vencida, 0 ofertas, debe quedar Desierta (id_estado=3)")

con.commit()

# --- Importar y correr verificar_cierre_subastas ---
sys.path.insert(0, os.path.dirname(__file__))
from database import get_db
import app as flask_app

with flask_app.app.app_context():
    db = get_db()
    flask_app.verificar_cierre_subastas(db)
    db.close()

# --- Verificar resultados ---
print("\n=== RESULTADOS ===")

# AC-01: TEST-A debe ser Finalizada con ganador=ana
r_a = con.execute("SELECT id_estado, id_ganador FROM subasta WHERE id_subasta=?", (sub_a,)).fetchone()
pago_a = con.execute("SELECT id_comprador, monto, fecha_limite, id_estado FROM pago WHERE id_subasta=? AND id_comprador=?", (sub_a, id_ana)).fetchone()
notif_a = con.execute("SELECT mensaje FROM notificacion WHERE id_usuario=? AND id_ref=?", (id_ana, sub_a)).fetchone()

print(f"\nAC-01 TEST-A (debe Finalizada=2, ganador=ana={id_ana}):")
print(f"  id_estado={r_a['id_estado']} {'OK' if r_a['id_estado']==2 else 'FALLA'}")
print(f"  id_ganador={r_a['id_ganador']} {'OK' if r_a['id_ganador']==id_ana else 'FALLA'}")
print(f"  pago creado: {'OK '+str(dict(pago_a)) if pago_a else 'FALLA NO existe'}")
print(f"  notificacion MSG-06: {'OK '+notif_a['mensaje'][:60] if notif_a else 'FALLA NO existe'}")

# AC-02: TEST-B debe ser Desierta=3
r_b = con.execute("SELECT id_estado, id_ganador FROM subasta WHERE id_subasta=?", (sub_b,)).fetchone()
vend = con.execute("SELECT id_vendedor FROM articulo WHERE id_articulo=?", (id_art,)).fetchone()
notif_b = con.execute("SELECT mensaje FROM notificacion WHERE id_usuario=? AND id_ref=?", (vend["id_vendedor"], sub_b)).fetchone()

print(f"\nAC-02 TEST-B (debe Desierta=3, sin ganador):")
print(f"  id_estado={r_b['id_estado']} {'OK' if r_b['id_estado']==3 else 'FALLA'}")
print(f"  id_ganador={r_b['id_ganador']} {'OK None' if r_b['id_ganador'] is None else 'FALLA tiene ganador'}")
print(f"  notificacion MSG-13 al vendedor: {'OK '+notif_b['mensaje'][:60] if notif_b else 'FALLA NO existe'}")

# AC-03: fecha_limite del pago debe ser > ahora (fue calculada al cierre)
if pago_a:
    limite_dt = datetime.datetime.strptime(pago_a["fecha_limite"], "%Y-%m-%d %H:%M:%S")
    ahora = datetime.datetime.utcnow()
    diferencia_h = (limite_dt - ahora).total_seconds() / 3600
    print(f"\nAC-03 Plazo de pago desde cierre (esperado ~48h):")
    print(f"  fecha_limite={pago_a['fecha_limite']}")
    print(f"  horas restantes={diferencia_h:.1f}h {'OK' if 47 < diferencia_h < 49 else 'FALLA'}")

# AC-06: no hay duplicados de pago
pago_count = con.execute("SELECT COUNT(*) as c FROM pago WHERE id_subasta=?", (sub_a,)).fetchone()["c"]
print(f"\nAC-06 Sin duplicado de pago (debe ser 1):")
print(f"  count={pago_count} {'OK' if pago_count==1 else 'FALLA'}")

con.close()
print("\n=== FIN ===")
