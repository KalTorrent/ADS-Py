# SubastaApp — Sistema de Gestión de Subastas

Plataforma web de subastas en línea desarrollada con **Python + Flask + SQLite + Bootstrap 5**.
Soporta tres modalidades de subasta (Inglesa, Holandesa, Sellada) y los actores
**Administrador** y **Comprador** (se incluye **Vendedor** para que el flujo sea demostrable de extremo a extremo).

Proyecto académico — ESCOM-IPN, Análisis y Diseño de Sistemas 2026 (Equipo 6).

---

## Stack

| Componente             | Tecnología                | Versión   |
|------------------------|---------------------------|-----------|
| Lenguaje               | Python                    | 3.10+     |
| Framework web          | Flask                     | 3.x       |
| Cifrado de contraseñas | Werkzeug (pbkdf2:sha256)  | 3.x       |
| Base de datos          | SQLite                    | 3         |
| Plantillas             | Jinja2 (con Flask)        | —         |
| CSS                    | Bootstrap 5.3 (CDN) + estilo eBay propio | — |

> No se usa ORM: todas las consultas son SQL directo con `sqlite3`, por transparencia pedagógica.

---

## Instalar y correr

Requisitos: Python 3.10+ y pip.

```bash
# 1. Instalar dependencias (Flask + Werkzeug)
pip install -r requirements.txt

# 2. Crear la base de datos con datos demo
python database.py

# 3. Levantar el servidor
python app.py
```

Abre `http://127.0.0.1:5000`. La primera ejecución de `app.py` también inicializa la BD si no existe.

Para regenerar la BD desde cero: borra `subasta.db` y vuelve a ejecutar `python database.py`.

---

## Credenciales demo

| Rol             | Correo              | Contraseña  |
|-----------------|---------------------|-------------|
| Administrador   | admin@subasta.mx    | Admin1234   |
| Administrador 2 | admin2@subasta.mx   | Admin1234   |
| Comprador       | ana@mail.mx         | Ana12345    |
| Comprador 2     | carlos@mail.mx      | Carlos1234  |
| Vendedor        | vend@mail.mx        | Vend1234    |

> Hay **dos administradores con los mismos permisos**, según el requisito del profesor.

Subastas demo precargadas: una **Inglesa** (Laptop), una **Holandesa** (Reloj: arranca en
$1,000, baja $100/h hasta un piso de $500) y una **Sellada** (Cuadro, base $800).

---

## Funcionalidades implementadas

### Tres tipos de subasta
- **Inglesa** — puja ascendente con incremento mínimo (RN-08).
- **Holandesa** — el precio baja cada hora hasta un piso; el primero en aceptar gana y la
  subasta **cierra de inmediato** (RN-09). El precio se recalcula en el servidor.
- **Sellada** — ofertas privadas (una por usuario); el precio no se revela y el ganador
  (mayor monto) se descubre **solo al cierre** (RN-10).

### Ciclo de vida de la subasta
- **Cierre automático por tiempo** (`verificar_cierre_subastas`, RN-13): al vencer `fecha_fin`
  se determina el ganador (mayor oferta), se crea el pago con su plazo y se notifica. Sin
  ofertas → subasta **desierta**.
- **Plazos de pago** desde el cierre: General 48 h, Vehículo 72 h, Inmueble 7 días (RN-14/15/16).
- **Pago vencido** (`verificar_pagos_vencidos`, RN-17/18): reasigna al 2.º mejor postor; si
  tampoco paga, se declara desierta.
- **Aprobación automática** de artículos generales a los 30 min (`verificar_aprobacion_automatica`, RN-02).
  Vehículos e inmuebles requieren revisión documental **sin límite de tiempo** (RN-03).

### Administrador
- Panel con artículos pendientes, subastas y usuarios (`/admin`).
- Validar artículos: aprobar / rechazar (motivo obligatorio) / extender plazo (`/admin/validar`).
- Cancelar subastas con motivo (`/admin/cancelar_subasta`).
- Gestión de usuarios: crear, editar, suspender, cancelar, reactivar.
- **Cancelar por fraude** (RN-26): suspende la cuenta, cancela todas sus subastas activas y
  agrega el correo a la **lista negra**. Un correo en lista negra no puede volver a registrarse.
- **Reportes mensuales** (`/admin/reportes`, CU-A08): subastas por estado, validaciones y
  transacciones del período, con filtro de mes/año.
- **Bandeja de correos** (`/admin/correos`): registro interno de los correos que el sistema
  generaría (al ganar y al vencer un pago). Es una simulación; no usa SMTP real.

### Comprador
- Registro (validado contra lista negra) e inicio de sesión.
- Catálogo con búsqueda/filtros y detalle de artículo.
- Ofertar según el tipo de subasta (`/oferta`).
- **Pagar** y subir comprobante (`/pago`). Para montos **> $10,000 MXN** no inmuebles se
  ofrecen **pagos a plazos** de 3, 6 o 12 meses (RN-27), generando las cuotas con sus fechas.
- **Confirmar recepción con evidencia fotográfica obligatoria** (`/confirmar_recepcion`):
  al menos una imagen JPG/PNG (máx. 5 MB c/u), que queda accesible desde el historial. Calificación 1–5.
- Historial personal e informe de notificaciones internas.

### Notificaciones
Internas (panel web) vía `notificar(...)`. El contador del navbar se actualiza cada 30 s
mediante `/api/notificaciones_count`. Adicionalmente, la bandeja de correos simula el envío
externo en los eventos de victoria y de pago vencido.

---

## Estructura del proyecto

```
ADS-Py/
├── app.py               # Rutas, lógica de negocio, funciones de barrido y decoradores
├── database.py          # Esquema SQLite (3FN), inicialización y datos demo
├── requirements.txt     # flask, werkzeug
├── docs/
│   └── decisiones.md    # Bitácora de reglas aplicadas, esquema y criterios de aceptación
├── templates/           # Vistas Jinja2 (base, catálogo, detalle, pago, recepción, panel admin, reportes, correos…)
└── static/uploads/recepciones/   # Imágenes de recepción subidas (generado en runtime)
```

---

## Base de datos (3FN)

Tablas de catálogo: `cat_tipo_usuario`, `cat_tipo_articulo`, `cat_tipo_subasta`,
`cat_estado_articulo`, `cat_estado_subasta`, `cat_estado_cuenta`, `cat_estado_pago`,
`cat_condicion_articulo`.

Tablas principales: `usuario`, `articulo`, `vehiculo`, `inmueble`, `validacion`, `subasta`,
`oferta`, `pago`, `calificacion`, `notificacion`, `log_admin`, `lista_negra`,
`imagen_recepcion`, `plan_pago`, `correo_salida`.

Notas de diseño:
- `subasta.precio_base` es el precio de arranque; en Holandesa `precio_piso` y
  `decremento_hora` definen el descenso y `precio_actual` se recalcula.
- `precio_actual` y `usuario.reputacion` son cachés desnormalizadas intencionales.

---

## Seguridad

- Contraseñas hasheadas con `werkzeug.security` (pbkdf2:sha256, nunca en texto claro).
- Sesión de Flask firmada con `secret_key`.
- Control de acceso con decoradores `@login_required` y `@admin_required`.
- Auditoría de acciones administrativas en `log_admin`.

---

*Sistema de Gestión de Subastas — ESCOM-IPN | Análisis y Diseño de Sistemas 2026*
