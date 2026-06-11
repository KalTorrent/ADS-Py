"""
Pruebas Arreglo 8 (cosmeticos y cierre): AC-34, AC-35, AC-36.
Ejecutar: python test_arreglo8.py  (requiere BD recien regenerada)
"""
import sqlite3, os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))
from database import DB_PATH

OK, FALLA = "OK", "FALLA"
resultados = []
def chk(ac, cond, detalle):
    resultados.append((ac, OK if cond else FALLA))
    print(f"  {ac}: {OK if cond else FALLA} - {detalle}")

def db_con():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

con = db_con()

# ── AC-34: dos admins en el seed ─────────────────────────────────────────────
print("AC-34 Dos administradores en el seed")
admins = con.execute("SELECT correo FROM usuario WHERE id_tipo=1 ORDER BY id_usuario").fetchall()
correos = [a["correo"] for a in admins]
chk("AC-34", len(admins) == 2 and "admin@subasta.mx" in correos and "admin2@subasta.mx" in correos,
    f"admins={correos} (esperado 2: admin y admin2)")

# ── AC-35: validacion de vehiculo sin fecha_limite ───────────────────────────
print("\nAC-35 Validacion de vehiculo/inmueble sin fecha_limite")
# El seed crea el Honda Civic (vehiculo) con validacion sin limite
veh = con.execute(
    """SELECT v.fecha_limite, a.titulo, t.tipo
       FROM validacion v JOIN articulo a ON a.id_articulo=v.id_articulo
       JOIN cat_tipo_articulo t ON t.id=a.id_tipo
       WHERE t.tipo IN ('Vehiculo','Inmueble')"""
).fetchall()
todas_null = all(r["fecha_limite"] is None for r in veh) and len(veh) > 0
chk("AC-35a", todas_null, f"validaciones vehiculo/inmueble con fecha_limite NULL={todas_null} ({len(veh)} fila/s)")

# El dashboard renderiza "Sin límite" cuando fecha_limite es NULL
import app as flask_app
client = flask_app.app.test_client()
client.post("/login", data={"correo": "admin@subasta.mx", "password": "Admin1234"}, follow_redirects=True)
html = client.get("/admin").get_data(as_text=True)
chk("AC-35b", "Sin límite" in html, f"dashboard muestra 'Sin límite'={'Sin límite' in html}")
con.close()

# ── AC-36: README sin funcionalidades fantasma ───────────────────────────────
print("\nAC-36 README refleja el estado real")
with open(os.path.join(os.path.dirname(__file__), "README.md"), encoding="utf-8") as f:
    readme = f.read()
# Debe mencionar lo real y NO las rutas/campos fantasma del README viejo
menciona_real = all(s in readme for s in [
    "/admin/reportes", "/admin/correos", "lista negra", "plazos", "admin2@subasta.mx",
    "Holandesa", "Sellada", "Bootstrap 5"
])
sin_fantasma = ("/admin/reporte\n" not in readme and "/admin/reporte " not in readme
                and "en_lista_negra" not in readme and "tasa de interés" not in readme
                and "id_tipo_subasta" not in readme)
chk("AC-36a", menciona_real, f"menciona funcionalidades reales={menciona_real}")
chk("AC-36b", sin_fantasma, f"sin rutas/campos fantasma={sin_fantasma}")

# ── Resumen ──────────────────────────────────────────────────────────────────
print("\n" + "="*50)
fallidos = [r for r in resultados if r[1] == FALLA]
print(f"RESUMEN: {len(resultados)-len(fallidos)}/{len(resultados)} OK")
print("TODOS PASARON" if not fallidos else "FALLARON: " + ", ".join(r[0] for r in fallidos))
print("="*50)
