"""
Pruebas Arreglo 6 (pagos a plazos >$10,000, RN-27) con test client.
Ejecutar: python test_arreglo6.py  (requiere BD recien regenerada)
"""
import sqlite3, os, sys, io, base64, datetime
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

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")

client = flask_app.app.test_client()
con = db_con()
ana_id  = con.execute("SELECT id_usuario FROM usuario WHERE correo='ana@mail.mx'").fetchone()["id_usuario"]
vend_id = con.execute("SELECT id_usuario FROM usuario WHERE correo='vend@mail.mx'").fetchone()["id_usuario"]

def crear_caso(titulo, id_tipo_art, monto):
    """Crea articulo+subasta(finalizada, ganada por Ana)+pago(pendiente) con el monto dado."""
    con.execute("INSERT INTO articulo (titulo,descripcion,id_tipo,id_condicion,ubicacion,id_vendedor,id_estado) VALUES(?,?,?,?,?,?,4)",
                (titulo, "demo", id_tipo_art, 2, "CDMX", vend_id))
    id_art = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    ini = (datetime.datetime.utcnow() - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    fin = (datetime.datetime.utcnow() - datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    con.execute("""INSERT INTO subasta (id_articulo,id_tipo,precio_base,precio_actual,incremento_min,fecha_inicio,fecha_fin,id_estado,id_ganador)
                   VALUES(?,1,?,?,100,?,?,2,?)""", (id_art, monto, monto, ini, fin, ana_id))
    id_sub = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    limite = (datetime.datetime.utcnow() + datetime.timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
    con.execute("INSERT INTO pago (id_subasta,id_comprador,monto,id_estado,fecha_limite) VALUES(?,?,?,1,?)",
                (id_sub, ana_id, monto, limite))
    con.commit()
    return id_sub

# Casos: >10k general, >10k inmueble, <=10k general
sub_caro_gen = crear_caso("Laptop premium", 1, 25000)   # >10k, no inmueble -> SI plazos
sub_inmueble = crear_caso("Casa en venta",  3, 500000)  # >10k, inmueble    -> NO plazos
sub_barato   = crear_caso("Audifonos",      1, 5000)    # <=10k             -> NO plazos
con.close()

client.post("/login", data={"correo": "ana@mail.mx", "password": "Ana12345"}, follow_redirects=True)

# ── AC-25: >10k no-inmueble ofrece plazos ────────────────────────────────────
print("AC-25 >$10,000 no-inmueble -> ofrece plazos")
html = client.get(f"/pago/{sub_caro_gen}").get_data(as_text=True)
ofrece = ("3 meses" in html and "6 meses" in html and "12 meses" in html)
chk("AC-25", ofrece, f"opciones 3/6/12 presentes={ofrece}")

# ── AC-26: inmueble NO ofrece plazos ─────────────────────────────────────────
print("\nAC-26 Inmueble -> NO ofrece plazos")
html = client.get(f"/pago/{sub_inmueble}").get_data(as_text=True)
chk("AC-26", "meses —" not in html and "Forma de pago" not in html,
    f"sin opciones de plazo={'Forma de pago' not in html}")

# ── AC-27: <=10k NO ofrece plazos ────────────────────────────────────────────
print("\nAC-27 <=$10,000 -> NO ofrece plazos")
html = client.get(f"/pago/{sub_barato}").get_data(as_text=True)
chk("AC-27", "Forma de pago" not in html, f"sin opciones de plazo={'Forma de pago' not in html}")

# ── AC-28: elegir 6 meses -> 6 cuotas correctas ──────────────────────────────
print("\nAC-28 Elegir 6 meses -> 6 cuotas con fechas/montos correctos")
client.post(f"/pago/{sub_caro_gen}", data={
    "plan": "6",
    "comprobante": (io.BytesIO(PNG), "comp.png"),
}, content_type="multipart/form-data", follow_redirects=True)
con = db_con()
id_pago = con.execute("SELECT id_pago FROM pago WHERE id_subasta=? AND id_comprador=?", (sub_caro_gen, ana_id)).fetchone()["id_pago"]
cuotas = con.execute("SELECT num_cuota, monto_cuota, fecha_vencimiento FROM plan_pago WHERE id_pago=? ORDER BY num_cuota", (id_pago,)).fetchall()
con.close()
suma = round(sum(c["monto_cuota"] for c in cuotas), 2)
nums = [c["num_cuota"] for c in cuotas]
fechas_ok = len(set(c["fecha_vencimiento"][:7] for c in cuotas)) == 6  # 6 meses distintos
chk("AC-28a", len(cuotas) == 6, f"numero de cuotas={len(cuotas)} (esperado 6)")
chk("AC-28b", suma == 25000.0, f"suma de cuotas=${suma} (esperado 25000)")
chk("AC-28c", nums == [1,2,3,4,5,6] and fechas_ok, f"num_cuota={nums}, meses distintos={fechas_ok}")

# ── AC-29: cuotas visibles en el historial ───────────────────────────────────
print("\nAC-29 Cuotas en el historial del comprador")
h = client.get("/mi_historial").get_data(as_text=True)
chk("AC-29", "A plazos: 0/6 cuotas" in h, f"indicador de plazos en historial={'A plazos: 0/6 cuotas' in h}")

# ── Resumen ──────────────────────────────────────────────────────────────────
print("\n" + "="*50)
fallidos = [r for r in resultados if r[1] == FALLA]
print(f"RESUMEN: {len(resultados)-len(fallidos)}/{len(resultados)} OK")
print("TODOS PASARON" if not fallidos else "FALLARON: " + ", ".join(r[0] for r in fallidos))
print("="*50)
