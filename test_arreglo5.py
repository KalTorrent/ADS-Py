"""
Pruebas Arreglo 5 (imagenes obligatorias al confirmar recepcion) con test client.
Ejecutar: python test_arreglo5.py  (requiere BD recien regenerada)
"""
import sqlite3, os, sys, io, datetime, base64
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

# PNG minimo valido (1x1) en bytes
PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
def png_file(name="evidencia.png"):
    return (io.BytesIO(PNG_1x1), name)

client = flask_app.app.test_client()

# ── Preparacion: dejar a Ana con una subasta ganada y pago VERIFICADO ─────────
# Cerramos la inglesa (Ana es mejor postor 8500), creamos/forzamos pago verificado.
con = db_con()
ana_id = con.execute("SELECT id_usuario FROM usuario WHERE correo='ana@mail.mx'").fetchone()["id_usuario"]
ing = con.execute("SELECT id_subasta FROM subasta WHERE id_tipo=1 LIMIT 1").fetchone()["id_subasta"]
# cerrar por tiempo
pasado = (datetime.datetime.utcnow() - datetime.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
con.execute("UPDATE subasta SET fecha_fin=? WHERE id_subasta=?", (pasado, ing))
con.commit(); con.close()
client.get("/")  # dispara cierre -> crea pago pendiente para Ana

# Forzar el pago a Verificado (id_estado=3) para habilitar confirmar recepcion
con = db_con()
con.execute("UPDATE pago SET id_estado=3 WHERE id_subasta=? AND id_comprador=?", (ing, ana_id))
con.commit()
id_pago = con.execute("SELECT id_pago FROM pago WHERE id_subasta=? AND id_comprador=?", (ing, ana_id)).fetchone()["id_pago"]
con.close()

client.post("/login", data={"correo": "ana@mail.mx", "password": "Ana12345"}, follow_redirects=True)

# ── AC-21: confirmar SIN imagen -> rechazado ─────────────────────────────────
print("AC-21 Sin imagen -> rechazado")
r = client.post(f"/confirmar_recepcion/{ing}", data={"puntuacion": "5"},
                content_type="multipart/form-data", follow_redirects=True)
con = db_con()
cal = con.execute("SELECT COUNT(*) c FROM calificacion WHERE id_subasta=?", (ing,)).fetchone()["c"]
con.close()
chk("AC-21", cal == 0 and "ERR-13" in r.get_data(as_text=True),
    f"calificacion creada={cal} (esperado 0), ERR-13 mostrado={'ERR-13' in r.get_data(as_text=True)}")

# ── AC-23: extension no permitida -> rechazado ───────────────────────────────
print("\nAC-23 Extension no permitida -> rechazado")
r = client.post(f"/confirmar_recepcion/{ing}", data={
    "puntuacion": "5",
    "imagenes": (io.BytesIO(b"%PDF-1.4 fake"), "doc.pdf"),
}, content_type="multipart/form-data", follow_redirects=True)
con = db_con()
cal = con.execute("SELECT COUNT(*) c FROM calificacion WHERE id_subasta=?", (ing,)).fetchone()["c"]
imgs = con.execute("SELECT COUNT(*) c FROM imagen_recepcion WHERE id_pago=?", (id_pago,)).fetchone()["c"]
con.close()
chk("AC-23", cal == 0 and imgs == 0 and "ERR-04" in r.get_data(as_text=True),
    f"calificacion={cal} imgs={imgs} (esperado 0/0), ERR-04={'ERR-04' in r.get_data(as_text=True)}")

# ── AC-22: confirmar CON imagenes -> guardadas + registradas + calificacion ──
print("\nAC-22 Con imagenes -> guardadas + registradas + calificacion")
r = client.post(f"/confirmar_recepcion/{ing}", data={
    "puntuacion": "4", "comentario_cal": "Todo bien",
    "imagenes": [png_file("ev1.png"), png_file("ev2.png")],
}, content_type="multipart/form-data", follow_redirects=True)
con = db_con()
cal = con.execute("SELECT COUNT(*) c, MAX(puntuacion) p FROM calificacion WHERE id_subasta=?", (ing,)).fetchone()
filas_img = con.execute("SELECT ruta FROM imagen_recepcion WHERE id_pago=?", (id_pago,)).fetchall()
con.close()
rutas = [x["ruta"] for x in filas_img]
en_disco = all(os.path.exists(os.path.join(flask_app.app.root_path, "static", r)) for r in rutas) if rutas else False
chk("AC-22a", cal["c"] == 1 and cal["p"] == 4, f"calificacion registrada count={cal['c']} punt={cal['p']}")
chk("AC-22b", len(rutas) == 2, f"filas en imagen_recepcion={len(rutas)} (esperado 2)")
chk("AC-22c", en_disco, f"archivos en disco={en_disco} rutas={rutas}")

# ── AC-24: imagenes accesibles desde el historial ────────────────────────────
print("\nAC-24 Imagenes accesibles desde historial")
h = client.get("/mi_historial").get_data(as_text=True)
en_historial = all(r in h for r in rutas) if rutas else False
# y accesibles via /static
accesible = True
for r in rutas:
    resp = client.get(f"/static/{r}")
    if resp.status_code != 200:
        accesible = False
chk("AC-24", en_historial and accesible,
    f"miniaturas en historial={en_historial}, servibles via /static={accesible}")

# ── Resumen ──────────────────────────────────────────────────────────────────
print("\n" + "="*50)
fallidos = [r for r in resultados if r[1] == FALLA]
print(f"RESUMEN: {len(resultados)-len(fallidos)}/{len(resultados)} OK")
print("TODOS PASARON" if not fallidos else "FALLARON: " + ", ".join(r[0] for r in fallidos))
print("="*50)
