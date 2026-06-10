# Sistema de Gestión de Subastas
**ESCOM-IPN | Análisis y Diseño de Sistemas**

## Tecnologías
- Python 3.10+
- Flask (framework web)
- SQLite (base de datos, 3FN normalizada)
- Bootstrap 5 (interfaz)

## Instalación

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Ejecutar
python app.py
```

## Acceso
- URL: http://127.0.0.1:5000
- **Admin:** admin@subasta.mx / Admin1234
- **Comprador:** ana@mail.mx / Ana12345
- **Vendedor (demo):** vend@mail.mx / Vend1234

## Actores implementados
| Actor | Casos de Uso cubiertos |
|-------|----------------------|
| **Administrador** | CU-A01 a CU-A07 (login, validar artículos, extender plazo, cancelar subastas, gestionar usuarios) |
| **Comprador** | CU-C01 a CU-C08 (registro, login, catálogo, oferta, pago, confirmar recepción, calificación, historial) |
| **Vendedor** | Publicar artículo (necesario para flujo completo) |

## Reglas de negocio implementadas
- RN-02: Aprobación automática de artículos generales a los 30 min
- RN-03: Validación obligatoria para vehículos e inmuebles (sin auto-aprobación)
- RN-07: Ofertas irreversibles
- RN-08: Incremento mínimo en subasta inglesa
- RN-10: Comprador solo ve puja actual, no historial
- RN-11: Restricción de ofertas con pagos pendientes
- RN-12: Restricción de cancelación de cuenta con actividad
- RN-17: Sin penalización económica por no pagar
- RN-18: Reasignación al segundo postor / subasta desierta

## Estructura del proyecto
```
subasta_sistema/
├── app.py           # Rutas y lógica de negocio (Flask)
├── database.py      # Esquema BD normalizado (SQLite) + seed demo
├── requirements.txt
├── templates/       # Vistas Jinja2
│   ├── base.html
│   ├── index.html
│   ├── catalogo.html
│   ├── detalle_subasta.html
│   ├── login.html
│   ├── registro.html
│   ├── admin_dashboard.html
│   ├── admin_validar.html
│   ├── realizar_pago.html
│   ├── mi_historial.html
│   ├── notificaciones.html
│   └── publicar.html
└── uploads/         # Comprobantes e imágenes (creado automáticamente)
```
