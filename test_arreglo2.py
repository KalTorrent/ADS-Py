"""
Pruebas Arreglo 2 (Holandesa + Sellada) usando el test client de Flask.
Ejercita las rutas reales /login y /oferta/<id>. Ejecutar: python test_arreglo2.py
Requiere BD recien regenerada (python database.py).
"""
import sqlite3
import datetime
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
    resultados.append((ac, estado, detalle))
    print(f"  {ac}: {estado} - {detalle}")

def db_con():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def sub_id(tipo):
    con = db_con()
    r = con.execute("SELECT id_subasta FROM subasta WHERE id_tipo=? AND id_estado=1 ORDER BY id_subasta LIMIT 1", (tipo,)).fetchone()
    con.close()
    return r["id_subasta"] if r else None

def login(client, correo, pwd):
    return client.post("/login", data={"correo": correo, "password": pwd}, follow_redirects=True)

client = flask_app.app.test_client()

ing_id = sub_id(1)
hol_id = sub_id(2)
sel_id = sub_id(3)
print(f"IDs -> Inglesa={ing_id}  Holandesa={hol_id}  Sellada={sel_id}\n")

# ── AC-07: decremento holandesa con piso ─────────────────────────────────────
print("AC-07 Holandesa: precio baja por hora y respeta el piso")
con = db_con()
def set_inicio(horas):
    fi = (datetime.datetime.utcnow() - datetime.timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    con.execute("UPDATE subasta SET fecha_inicio=? WHERE id_subasta=?", (fi, hol_id))
    con.commit()

with flask_app.app.app_context():
    from database import get_db
    # 2h -> 1000 - 100*2 = 800
    set_inicio(2)
    d = get_db(); flask_app.verificar_decremento_holandesa(d); d.close()
    p2 = con.execute("SELECT precio_actual FROM subasta WHERE id_subasta=?", (hol_id,)).fetchone()["precio_actual"]
    chk("AC-07a", p2 == 800, f"a 2h precio_actual={p2} (esperado 800)")
    # 3h -> 700
    set_inicio(3)
    d = get_db(); flask_app.verificar_decremento_holandesa(d); d.close()
    p3 = con.execute("SELECT precio_actual FROM subasta WHERE id_subasta=?", (hol_id,)).fetchone()["precio_actual"]
    chk("AC-07b", p3 == 700, f"a 3h precio_actual={p3} (esperado 700)")
    # 8h -> max(500, 1000-800)=500 (piso)
    set_inicio(8)
    d = get_db(); flask_app.verificar_decremento_holandesa(d); d.close()
    p8 = con.execute("SELECT precio_actual FROM subasta WHERE id_subasta=?", (hol_id,)).fetchone()["precio_actual"]
    chk("AC-07c", p8 == 500, f"a 8h precio_actual={p8} (esperado 500=piso)")
con.close()

# Dejar holandesa a 3h (precio vigente 700) para la prueba de aceptacion
con = db_con()
fi3 = (datetime.datetime.utcnow() - datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
con.execute("UPDATE subasta SET fecha_inicio=? WHERE id_subasta=?", (fi3, hol_id))
con.commit(); con.close()

# ── AC-14: Inglesa no-regresion (carlos puja 8600 sobre 8500) ────────────────
print("\nAC-14 Inglesa: incremento minimo sigue funcionando (no-regresion)")
login(client, "carlos@mail.mx", "Carlos1234")
client.post(f"/oferta/{ing_id}", data={"monto": "8600"}, follow_redirects=True)
con = db_con()
ing = con.execute("SELECT precio_actual, id_ganador FROM subasta WHERE id_subasta=?", (ing_id,)).fetchone()
carlos_id = con.execute("SELECT id_usuario FROM usuario WHERE correo='carlos@mail.mx'").fetchone()["id_usuario"]
chk("AC-14", ing["precio_actual"] == 8600 and ing["id_ganador"] == carlos_id,
    f"precio_actual={ing['precio_actual']} id_ganador={ing['id_ganador']} (esperado 8600 / carlos={carlos_id})")
# Rechazo por debajo del minimo
client.post(f"/oferta/{ing_id}", data={"monto": "8650"}, follow_redirects=True)  # < 8600+100
ing2 = con.execute("SELECT precio_actual FROM subasta WHERE id_subasta=?", (ing_id,)).fetchone()
chk("AC-14b", ing2["precio_actual"] == 8600, f"puja 8650 (<8700) rechazada, precio sigue {ing2['precio_actual']}")
con.close()

# ── AC-10/11/12: Sellada ─────────────────────────────────────────────────────
print("\nAC-10/11/12 Sellada: ofertas privadas")
ana_id = None
con = db_con()
ana_id = con.execute("SELECT id_usuario FROM usuario WHERE correo='ana@mail.mx'").fetchone()["id_usuario"]
con.close()

login(client, "ana@mail.mx", "Ana12345")
client.post(f"/oferta/{sel_id}", data={"monto": "900"}, follow_redirects=True)
# AC-11: segundo intento de ana -> ERR-11
client.post(f"/oferta/{sel_id}", data={"monto": "950"}, follow_redirects=True)
login(client, "carlos@mail.mx", "Carlos1234")
client.post(f"/oferta/{sel_id}", data={"monto": "1000"}, follow_redirects=True)

con = db_con()
sel = con.execute("SELECT precio_actual, id_ganador FROM subasta WHERE id_subasta=?", (sel_id,)).fetchone()
chk("AC-10", sel["precio_actual"] == 800 and sel["id_ganador"] is None,
    f"precio_actual={sel['precio_actual']} (esperado 800, sin cambio) id_ganador={sel['id_ganador']} (esperado None)")

ofertas_ana = con.execute("SELECT COUNT(*) c FROM oferta WHERE id_subasta=? AND id_comprador=?", (sel_id, ana_id)).fetchone()["c"]
chk("AC-11", ofertas_ana == 1, f"ana tiene {ofertas_ana} oferta(s) sellada(s) (esperado 1, segunda rechazada)")

msg04 = con.execute("SELECT COUNT(*) c FROM notificacion WHERE id_ref=? AND mensaje LIKE 'MSG-04%'", (sel_id,)).fetchone()["c"]
chk("AC-12", msg04 == 0, f"notificaciones MSG-04 en sellada={msg04} (esperado 0)")
con.close()

# ── AC-13: Sellada cierra por tiempo y revela ganador (MAX monto=carlos 1000) ─
print("\nAC-13 Sellada: cierre por tiempo revela al ganador (MAX monto)")
con = db_con()
pasado = (datetime.datetime.utcnow() - datetime.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
con.execute("UPDATE subasta SET fecha_fin=? WHERE id_subasta=?", (pasado, sel_id))
con.commit(); con.close()
client.get("/")  # dispara verificar_cierre_subastas
con = db_con()
sel2 = con.execute("SELECT id_estado, id_ganador FROM subasta WHERE id_subasta=?", (sel_id,)).fetchone()
chk("AC-13", sel2["id_estado"] == 2 and sel2["id_ganador"] == carlos_id,
    f"id_estado={sel2['id_estado']} (esperado 2) id_ganador={sel2['id_ganador']} (esperado carlos={carlos_id})")
con.close()

# ── AC-08/09: Holandesa aceptar y cerrar de inmediato ────────────────────────
print("\nAC-08/09 Holandesa: aceptar precio vigente cierra de inmediato")
login(client, "ana@mail.mx", "Ana12345")
client.post(f"/oferta/{hol_id}", data={"monto": "700"}, follow_redirects=True)
con = db_con()
hol = con.execute("SELECT id_estado, id_ganador, precio_actual FROM subasta WHERE id_subasta=?", (hol_id,)).fetchone()
pago_hol = con.execute("SELECT monto, fecha_limite, id_estado FROM pago WHERE id_subasta=? AND id_comprador=?", (hol_id, ana_id)).fetchone()
notif06 = con.execute("SELECT COUNT(*) c FROM notificacion WHERE id_ref=? AND id_usuario=? AND mensaje LIKE 'MSG-06%'", (hol_id, ana_id)).fetchone()["c"]
chk("AC-08a", hol["id_estado"] == 2 and hol["id_ganador"] == ana_id,
    f"id_estado={hol['id_estado']} (esperado 2) id_ganador={hol['id_ganador']} (esperado ana={ana_id})")
chk("AC-08b", pago_hol is not None and pago_hol["monto"] == 700,
    f"pago creado monto={pago_hol['monto'] if pago_hol else None} (esperado 700)")
chk("AC-08c", notif06 >= 1, f"notificaciones MSG-06 al ganador={notif06} (esperado >=1)")

# AC-09: segunda puja tras cierre -> rechazada (no nueva oferta)
ofertas_antes = con.execute("SELECT COUNT(*) c FROM oferta WHERE id_subasta=?", (hol_id,)).fetchone()["c"]
con.close()
login(client, "carlos@mail.mx", "Carlos1234")
client.post(f"/oferta/{hol_id}", data={"monto": "700"}, follow_redirects=True)
con = db_con()
ofertas_despues = con.execute("SELECT COUNT(*) c FROM oferta WHERE id_subasta=?", (hol_id,)).fetchone()["c"]
chk("AC-09", ofertas_antes == ofertas_despues, f"ofertas antes={ofertas_antes} despues={ofertas_despues} (no debe crecer)")
con.close()

# ── Resumen ──────────────────────────────────────────────────────────────────
print("\n" + "="*50)
fallidos = [r for r in resultados if r[1] == FALLA]
print(f"RESUMEN: {len(resultados)-len(fallidos)}/{len(resultados)} OK")
if fallidos:
    print("FALLARON:")
    for ac, _, det in fallidos:
        print(f"  - {ac}: {det}")
else:
    print("TODOS LOS CRITERIOS PASARON (AC-07 a AC-14)")
print("="*50)
