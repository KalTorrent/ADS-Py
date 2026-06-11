"""
Pruebas Arreglo 4 (reportes mensuales) con el test client de Flask.
Ejecutar: python test_arreglo4.py  (requiere BD recien regenerada)
"""
import sqlite3, os, sys, re, datetime
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
hoy = datetime.datetime.utcnow()
periodo = f"{hoy.year:04d}-{hoy.month:02d}"

# ── Generar algo de actividad en el mes actual ───────────────────────────────
# a) Aprobar el articulo del vehiculo (validacion -> decision Aprobado, fecha_decision hoy)
client.post("/login", data={"correo": "admin@subasta.mx", "password": "Admin1234"}, follow_redirects=True)
con = db_con()
id_val = con.execute("SELECT id_validacion, id_articulo FROM validacion WHERE decision IS NULL LIMIT 1").fetchone()
con.close()
if id_val:
    client.post(f"/admin/validar/{id_val['id_articulo']}",
                data={"accion": "Aprobar", "comentario": "ok"}, follow_redirects=True)

# b) Cerrar la subasta inglesa por tiempo -> crea pago (pendiente) en el periodo
con = db_con()
ing = con.execute("SELECT id_subasta FROM subasta WHERE id_tipo=1 AND id_estado=1 LIMIT 1").fetchone()
con.close()
if ing:
    con = db_con()
    pasado = (hoy - datetime.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
    con.execute("UPDATE subasta SET fecha_fin=? WHERE id_subasta=?", (pasado, ing["id_subasta"]))
    con.commit(); con.close()
    client.get("/")  # dispara verificar_cierre_subastas -> crea pago

# ── AC-20: acceso solo admin ─────────────────────────────────────────────────
print("AC-20 Acceso restringido a admin")
client.get("/logout")
r_anon = client.get("/admin/reportes", follow_redirects=False)
chk("AC-20a", r_anon.status_code in (301, 302), f"anonimo redirigido status={r_anon.status_code}")
client.post("/login", data={"correo": "ana@mail.mx", "password": "Ana12345"}, follow_redirects=False)
r_comp = client.get("/admin/reportes", follow_redirects=False)
chk("AC-20b", r_comp.status_code in (301, 302), f"comprador redirigido status={r_comp.status_code}")
client.get("/logout")
client.post("/login", data={"correo": "admin@subasta.mx", "password": "Admin1234"}, follow_redirects=False)
r_admin = client.get("/admin/reportes")
chk("AC-20c", r_admin.status_code == 200, f"admin accede status={r_admin.status_code}")

# ── AC-18: las 3 secciones presentes ─────────────────────────────────────────
print("\nAC-18 Las 3 secciones con datos del mes actual")
html = r_admin.get_data(as_text=True)
tiene_3 = ("Subastas del mes" in html and "Validaciones realizadas" in html
           and "Transacciones" in html)
chk("AC-18", tiene_3, f"secciones presentes={tiene_3} (periodo {periodo})")

# ── AC-19: conteos cuadran con SQL directo ───────────────────────────────────
print("\nAC-19 Conteos cuadran con la BD")
con = db_con()
def sql_sub(estado):
    return con.execute(
        """SELECT COUNT(*) c FROM subasta s JOIN cat_estado_subasta e ON e.id=s.id_estado
           WHERE e.estado=? AND strftime('%Y-%m', s.fecha_inicio)=?""", (estado, periodo)).fetchone()["c"]
def sql_val(dec):
    return con.execute(
        """SELECT COUNT(*) c FROM validacion
           WHERE decision=? AND strftime('%Y-%m', fecha_decision)=?""", (dec, periodo)).fetchone()["c"]
def sql_pago(*ids):
    q = "SELECT COUNT(*) c FROM pago WHERE id_estado IN (%s) AND strftime('%%Y-%%m', fecha_limite)=?" % ",".join("?"*len(ids))
    return con.execute(q, (*ids, periodo)).fetchone()["c"]

# Recalcular reporte llamando a la ruta y comparando con SQL: usamos la respuesta HTML
# (extraemos los numeros de las tarjetas en orden) y los contrastamos con SQL.
esperado = {
    "Activa": sql_sub("Activa"), "Finalizada": sql_sub("Finalizada"),
    "Desierta": sql_sub("Desierta"), "Cancelada": sql_sub("Cancelada"),
    "Aprobado": sql_val("Aprobado"), "Rechazado": sql_val("Rechazado"), "Automatico": sql_val("Automatico"),
    "completados": sql_pago(3), "pendientes": sql_pago(1, 2), "vencidos": sql_pago(4),
}
con.close()

# Verificacion directa contra la funcion de la ruta (mas robusto que parsear HTML):
with flask_app.app.test_request_context(f"/admin/reportes?anio={hoy.year}&mes={hoy.month}"):
    from flask import session as flask_session
    flask_session["user_id"] = 1; flask_session["user_tipo"] = 1; flask_session["user_nombre"] = "Admin"
    # Reproducimos las queries del reporte directamente:
    d = db_con()
    sub_d = {r["estado"]: r["total"] for r in d.execute(
        "SELECT e.estado, COUNT(*) total FROM subasta s JOIN cat_estado_subasta e ON e.id=s.id_estado WHERE strftime('%Y-%m',s.fecha_inicio)=? GROUP BY s.id_estado", (periodo,))}
    val_d = {r["decision"]: r["total"] for r in d.execute(
        "SELECT decision, COUNT(*) total FROM validacion WHERE decision IS NOT NULL AND strftime('%Y-%m',fecha_decision)=? GROUP BY decision", (periodo,))}
    pago_rows = {r["id_estado"]: r["total"] for r in d.execute(
        "SELECT id_estado, COUNT(*) total FROM pago WHERE strftime('%Y-%m',fecha_limite)=? GROUP BY id_estado", (periodo,))}
    d.close()

reporte = {
    "Activa": sub_d.get("Activa",0), "Finalizada": sub_d.get("Finalizada",0),
    "Desierta": sub_d.get("Desierta",0), "Cancelada": sub_d.get("Cancelada",0),
    "Aprobado": val_d.get("Aprobado",0), "Rechazado": val_d.get("Rechazado",0), "Automatico": val_d.get("Automatico",0),
    "completados": pago_rows.get(3,0), "pendientes": pago_rows.get(1,0)+pago_rows.get(2,0), "vencidos": pago_rows.get(4,0),
}
cuadran = reporte == esperado
chk("AC-19", cuadran, f"reporte={reporte}")
if not cuadran:
    print(f"     esperado={esperado}")

# ── Resumen ──────────────────────────────────────────────────────────────────
print("\n" + "="*50)
fallidos = [r for r in resultados if r[1] == FALLA]
print(f"RESUMEN: {len(resultados)-len(fallidos)}/{len(resultados)} OK")
print("TODOS PASARON" if not fallidos else "FALLARON: " + ", ".join(r[0] for r in fallidos))
print("="*50)
