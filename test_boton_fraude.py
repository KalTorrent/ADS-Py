"""
Verifica el flujo del boton 'Cancelar por fraude' end-to-end via test client,
simulando exactamente lo que envia el formulario del panel admin.
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))
import app as flask_app

client = flask_app.app.test_client()

# 1. El boton existe en el HTML del panel (logueado como admin)
client.post("/login", data={"correo": "admin@subasta.mx", "password": "Admin1234"}, follow_redirects=True)
panel = client.get("/admin").get_data(as_text=True)
tiene_boton = 'value="CancelarFraude"' in panel and "Cancelar por fraude" in panel
tiene_confirm = "confirm(" in panel and "lista negra" in panel
print(f"Boton presente en panel: {'OK' if tiene_boton else 'FALLA'}")
print(f"Pide confirmacion JS:    {'OK' if tiene_confirm else 'FALLA'}")

# 2. Disparar el POST como lo hace el form
r = client.post("/admin/usuario/4", data={"accion": "CancelarFraude"}, follow_redirects=True)
html = r.get_data(as_text=True)

# 3. Flash de exito visible
flash_ok = "marcado por fraude" in html and "lista negra" in html
print(f"Flash de exito visible:  {'OK' if flash_ok else 'FALLA'}")

# 4. El vendedor ahora aparece como Suspendida en la tabla
suspendida = bool(re.search(r"vend@mail\.mx.*?Suspendida", html, re.S))
print(f"Vendedor ahora Suspendida en panel: {'OK' if suspendida else 'FALLA'}")

print("\nVERIFICACION NAVEGADOR:",
      "TODO OK" if (tiene_boton and tiene_confirm and flash_ok and suspendida) else "REVISAR")
