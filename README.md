# SubastaApp — Sistema de Gestión de Subastas

Plataforma web de subastas en línea desarrollada con **Python + Flask + SQLite**.  
Diseñada para el mercado mexicano, soporta tres modalidades de subasta y dos actores principales: **Administrador** y **Comprador**.

---

## Índice

1. [Inicio rápido](#inicio-rápido)
2. [Credenciales demo](#credenciales-demo)
3. [Estructura del proyecto](#estructura-del-proyecto)
4. [Arquitectura general](#arquitectura-general)
5. [Base de datos](#base-de-datos)
6. [Rutas y funcionalidades](#rutas-y-funcionalidades)
7. [Actores y casos de uso](#actores-y-casos-de-uso)
8. [Reglas de negocio implementadas](#reglas-de-negocio-implementadas)
9. [Sistema de notificaciones](#sistema-de-notificaciones)
10. [Seguridad](#seguridad)
11. [Configuración y personalización](#configuración-y-personalización)
12. [Tecnologías utilizadas](#tecnologías-utilizadas)

---

## Inicio rápido

### Requisitos previos

- Python 3.10 o superior
- pip (incluido con Python)
- Navegador moderno (Chrome, Firefox, Edge, Safari)

### Instalación

```bash
# 1. Descomprime el proyecto y entra a la carpeta
cd subasta_sistema

# 2. Instala las dependencias
pip install -r requirements.txt

# 3. Ejecuta el servidor
python app.py
```

### Acceso

Abre tu navegador en: `http://127.0.0.1:5000`

El servidor inicializa la base de datos y carga datos de demostración automáticamente en el primer arranque.

---

## Credenciales demo

| Rol           | Correo            | Contraseña   |
|---------------|-------------------|--------------|
| Administrador | admin@subasta.mx  | Admin1234    |
| Comprador     | ana@mail.mx       | Ana12345     |
| Comprador 2   | carlos@mail.mx    | Carlos123    |
| Vendedor      | vend@mail.mx      | Vend1234     |

---

## Estructura del proyecto

```
subasta_sistema/
│
├── app.py               # Servidor Flask: rutas, lógica de negocio, decoradores
├── database.py          # Esquema SQLite (3FN), inicialización y datos demo
├── requirements.txt     # Dependencias: flask, werkzeug
├── subasta.db           # Base de datos SQLite (se genera automáticamente)
│
└── templates/           # Vistas Jinja2 con diseño estilo eBay
    ├── base.html                # Layout base: navbar, alertas, footer, JS común
    ├── index.html               # Página de inicio con subastas destacadas
    ├── catalogo.html            # Listado con filtros por categoría y búsqueda
    ├── detalle_subasta.html     # Vista de artículo: info + caja de puja (cambia según tipo de subasta)
    ├── login.html               # Inicio de sesión
    ├── registro.html            # Registro de nuevo comprador
    ├── publicar.html            # Formulario de publicación de artículo (rol Vendedor)
    ├── realizar_pago.html       # Subida de comprobante de pago
    ├── mi_historial.html        # Historial: ofertas, ganadas y pagos
    ├── notificaciones.html      # Centro de notificaciones internas
    ├── admin_dashboard.html     # Panel de administración principal
    ├── admin_validar.html       # Revisión de artículos pendientes
    └── admin_usuario_form.html  # Crear/editar usuario (admin)
```

---

## Arquitectura general

Las rutas son URLs del servidor Flask. Cuando el navegador hace una petición, Flask ejecuta la función correspondiente en `app.py` y devuelve el HTML renderizado. El acceso a cada ruta está controlado por decoradores que verifican si hay sesión activa y qué rol tiene el usuario.

```
Navegador  →  GET /catalogo
               │
               ▼
           Flask (app.py)
               │
               ├── @login_required   → si no hay sesión activa, redirige a /login
               └── @admin_required   → si el rol no es Administrador, bloquea el acceso
               │
               ├── Funciones automáticas (se ejecutan en cada carga de la página principal)
               │   ├── verificar_aprobacion_automatica()  → RN-02: aprueba artículos generales a los 30 min
               │   ├── verificar_pagos_vencidos()         → RN-17/18: reasigna al 2do postor o declara desierta
               │   └── verificar_cierre_subastas()        → RN-13: cierra subastas al vencer el tiempo
               │
               ├── Rutas públicas      →  /, /catalogo, /subasta/<id>, /login, /registro
               ├── Rutas de comprador  →  /oferta, /pago, /historial, /notificaciones
               ├── Rutas de vendedor   →  /publicar  (fuera del alcance del documento)
               └── Rutas de admin      →  /admin, /admin/validar, /admin/usuario/*, /admin/reporte
               │
               ▼
           database.py  →  subasta.db (SQLite, 3FN, 20 tablas)
```

---

## Base de datos

Normalizada en **Tercera Forma Normal (3FN)**. Toda información enumerada (tipos, estados, condiciones) se almacena en **tablas de catálogo** independientes: en lugar de guardar el texto `"Inglesa"` directamente en la tabla `subasta`, se guarda el ID numérico correspondiente y la tabla de catálogo resuelve el nombre. Esto evita redundancia y facilita cambios futuros.

Los valores calculados `precio_actual` (en `subasta`) y `reputacion` (en `usuario`) se mantienen como caché de rendimiento y se actualizan en cada operación correspondiente. Esto es una **desnormalización intencional documentada** para evitar recalcular `MAX(oferta)` y `AVG(calificacion)` en cada consulta.

### Tablas de catálogo

Estas tablas solo contienen listas de valores fijos. No se modifican en tiempo de ejecución.

| Tabla                    | Valores                                                          |
|--------------------------|------------------------------------------------------------------|
| `cat_tipo_usuario`       | Administrador, Comprador, Vendedor                               |
| `cat_tipo_articulo`      | General, Vehículo, Inmueble, Digital, Entrada                    |
| `cat_tipo_subasta`       | Inglesa, Holandesa, Sellada                                      |
| `cat_estado_articulo`    | Pendiente, Aprobado, Rechazado, Publicado                        |
| `cat_estado_subasta`     | Activa, Finalizada, Desierta, Cancelada                          |
| `cat_estado_cuenta`      | Activa, Suspendida, Cancelada                                    |
| `cat_estado_pago`        | Pendiente, EnVerificacion, Verificado, Vencido                   |
| `cat_condicion_articulo` | Nuevo, Usado, Reacondicionado                                    |

### Tablas principales

| Tabla          | Descripción                                                                                                    |
|----------------|----------------------------------------------------------------------------------------------------------------|
| `usuario`      | Todos los usuarios con rol, estado y reputación. Incluye flag `en_lista_negra`.                               |
| `articulo`     | Artículos publicados para subasta. El tipo de subasta (inglesa/holandesa/sellada) se guarda aquí como FK a `cat_tipo_subasta`. |
| `vehiculo`     | Extensión de `articulo`: marca, modelo, km, número de serie, documentación legal.                             |
| `inmueble`     | Extensión de `articulo`: superficies, habitaciones, ubicación detallada, documentación legal.                 |
| `validacion`   | Decisiones del administrador sobre artículos, con timer de 30 minutos para artículos generales.               |
| `subasta`      | Subastas activas y cerradas. Guarda `precio_actual` (caché) y FK al ganador.                                  |
| `oferta`       | Cada oferta realizada por un comprador. Las ofertas selladas tienen `es_privada = TRUE`.                      |
| `plan_pago`    | Configuración de pagos a plazos: total de cuotas, meses y tasa de interés. Solo para artículos > $10,000 MXN (excepto inmuebles). |
| `pago`         | Pagos y comprobantes del ganador. Soporta pagos escalonados con `numero_pago`. FK opcional a `plan_pago`.     |
| `calificacion` | Calificaciones mutuas (1–5) al finalizar cada transacción.                                                    |
| `notificacion` | Alertas internas por usuario: tipo, canal y estado de lectura.                                                |
| `lista_negra`  | Correos de cuentas canceladas por fraude. Impide nuevos registros con el mismo correo.                        |
| `log_admin`    | Registro de auditoría de todas las acciones administrativas relevantes.                                       |

### Relaciones clave

```
usuario     ──<  articulo       (id_vendedor)
usuario     ──<  oferta         (id_comprador)
usuario     ──<  pago           (id_comprador)
usuario     ──<  notificacion
usuario     ──○  lista_negra
articulo    ────  subasta       (1:1)
articulo    ────  validacion
articulo    ─○──  vehiculo      (1:1 opcional)
articulo    ─○──  inmueble      (1:1 opcional)
subasta     ──<  oferta
subasta     ──<  pago
subasta     ──○  plan_pago      (1:1 opcional, solo si aplica pago a plazos)
subasta     ──<  calificacion
plan_pago   ──<  pago
```

### Consulta rápida desde terminal

```bash
# Abrir la base de datos
sqlite3 subasta.db

# Ver todos los usuarios (contraseñas almacenadas como hash, nunca en texto claro)
SELECT id_usuario, nombre, correo, tipo, estado FROM usuario;

# Ver subastas activas con su tipo
SELECT s.id_subasta, a.titulo, c.nombre AS tipo, s.precio_actual, s.fecha_fin
FROM subasta s
JOIN articulo a ON s.id_articulo = a.id_articulo
JOIN cat_tipo_subasta c ON a.id_tipo_subasta = c.id_tipo_subasta
WHERE s.estado = 'Activa';

# Ver log de auditoría del administrador
SELECT * FROM log_admin ORDER BY fecha DESC LIMIT 10;

# Salir
.quit
```

---

## Rutas y funcionalidades

### Públicas — accesibles sin autenticación

| Ruta            | Método   | Descripción                                                              |
|-----------------|----------|--------------------------------------------------------------------------|
| `/`             | GET      | Página de inicio con subastas destacadas. Ejecuta funciones automáticas. |
| `/catalogo`     | GET      | Catálogo con filtro por categoría y búsqueda por texto.                  |
| `/subasta/<id>` | GET      | Detalle del artículo: precio actual, tiempo restante, caja de oferta. La interfaz cambia según el tipo de subasta (inglesa muestra campo de monto; holandesa muestra botón "Aceptar precio"; sellada muestra campo de monto sin revelar otras pujas). |
| `/login`        | GET/POST | Formulario de inicio de sesión para todos los roles.                     |
| `/registro`     | GET/POST | Registro de nuevo Comprador. Valida que el correo no esté en lista negra antes de crear la cuenta. |
| `/logout`       | GET      | Cierra la sesión activa y redirige a `/`.                                |

### Comprador — requieren sesión activa (`@login_required`)

| Ruta                            | Método   | Descripción                                                                                         |
|---------------------------------|----------|-----------------------------------------------------------------------------------------------------|
| `/oferta/<id_sub>`              | POST     | Registra oferta. Valida: monto mínimo (inglesa), pagos pendientes, estado de la subasta y tipo. En holandesa cierra la subasta inmediatamente al aceptar. |
| `/pago/<id_sub>`                | GET/POST | Sube comprobante de pago (JPG/PNG/PDF, máx. 5 MB). Soporta pagos a plazos (crea `plan_pago`) y pagos escalonados para inmuebles. |
| `/confirmar_recepcion/<id_sub>` | POST     | Confirma entrega con imágenes obligatorias y registra calificación al vendedor (1–5).               |
| `/mi_historial`                 | GET      | Historial en tres pestañas: ofertas realizadas, subastas ganadas, pagos completados.                |
| `/notificaciones`               | GET      | Lista de notificaciones internas. Marca todas como leídas al acceder.                               |
| `/api/notificaciones_count`     | GET      | Devuelve `{"count": N}`. Polleado cada 30 s desde el navbar para actualizar el contador.            |

> **Nota:** la ruta `/publicar` permite al rol Vendedor publicar artículos. Este actor está fuera del alcance del documento técnico pero se incluye para que el sistema sea demostrable de extremo a extremo.

### Administrador — requieren rol Administrador (`@admin_required`)

| Ruta                               | Método   | Descripción                                                                                          |
|------------------------------------|----------|------------------------------------------------------------------------------------------------------|
| `/admin`                           | GET      | Panel principal: artículos pendientes de validación, subastas activas, listado de usuarios.          |
| `/admin/validar/<id_art>`          | GET/POST | Aprobar, rechazar (con motivo obligatorio) o extender plazo. Aplica lógica diferenciada por tipo de artículo (general con timer, vehículo/inmueble sin límite). |
| `/admin/cancelar_subasta/<id_sub>` | POST     | Cancela subasta activa. Motivo obligatorio. Notifica a vendedor y compradores. Registra en `log_admin`. |
| `/admin/usuario/<id>`              | POST     | Suspender, cancelar (registra en lista negra si es por fraude y cancela subastas activas) o reactivar cuenta. |
| `/admin/usuario/nuevo`             | GET/POST | Crear usuario manualmente con cualquier rol.                                                         |
| `/admin/usuario/<id>/editar`       | GET/POST | Editar nombre, correo, rol y/o contraseña.                                                           |
| `/admin/usuario/<id>/eliminar`     | POST     | Eliminar permanentemente. Solo disponible si el usuario no tiene actividad registrada.               |
| `/admin/reporte`                   | GET/POST | Genera reporte mensual: subastas por estado, validaciones y transacciones por período. (CU-A08)      |

---

## Actores y casos de uso

### Administrador

| CU     | Descripción                                                              | Ruta                               |
|--------|--------------------------------------------------------------------------|------------------------------------|
| CU-A01 | Iniciar sesión                                                           | `/login`                           |
| CU-A02 | Validar artículo general (aprobación automática a los 30 min)           | `/admin/validar/<id>`              |
| CU-A03 | Validar vehículo (revisión documental obligatoria, sin límite de tiempo) | `/admin/validar/<id>`              |
| CU-A04 | Validar inmueble (revisión documental obligatoria, sin límite de tiempo) | `/admin/validar/<id>`              |
| CU-A05 | Extender plazo de validación                                             | `/admin/validar/<id>`              |
| CU-A06 | Cancelar subasta activa por política                                     | `/admin/cancelar_subasta/<id>`     |
| CU-A07 | Gestionar usuarios (crear, editar, suspender, cancelar, lista negra)    | `/admin/usuario/*`                 |
| CU-A08 | Monitorear subastas y generar reporte mensual                            | `/admin` + `/admin/reporte`        |

### Comprador

| CU     | Descripción                                                  | Ruta                          |
|--------|--------------------------------------------------------------|-------------------------------|
| CU-C01 | Registrarse en la plataforma                                 | `/registro`                   |
| CU-C02 | Iniciar sesión                                               | `/login`                      |
| CU-C03 | Consultar catálogo y detalle de artículo                     | `/catalogo`, `/subasta/<id>`  |
| CU-C04 | Realizar oferta (inglesa / holandesa / sellada)              | `/oferta/<id>`                |
| CU-C05 | Recibir notificaciones                                       | `/notificaciones`             |
| CU-C06 | Realizar pago y adjuntar comprobante                         | `/pago/<id>`                  |
| CU-C07 | Confirmar recepción y calificar vendedor                     | `/confirmar_recepcion/<id>`   |
| CU-C08 | Consultar historial personal                                 | `/mi_historial`               |

---

## Reglas de negocio implementadas

| ID          | Regla                                                                                                 | Implementación en `app.py`                                        |
|-------------|-------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| RN-01       | Todo artículo debe pasar por revisión del administrador antes de ser visible para los compradores     | `publicar_articulo()` — estado inicial `Pendiente`; `catalogo()` solo muestra artículos `Publicado` |
| RN-02       | Aprobación automática de artículos generales a los 30 minutos si el admin no actúa                   | `verificar_aprobacion_automatica()`                               |
| RN-03       | Vehículos e inmuebles requieren revisión documental obligatoria; no aplica aprobación automática      | `admin_validar()` — rama por tipo de artículo                     |
| RN-04       | Al rechazar, el administrador registra el motivo; el sistema actualiza el estado a `Rechazado`        | `admin_validar()` — acción rechazar con motivo obligatorio        |
| RN-05       | Cancelación de subasta activa solo por política con motivo obligatorio                                | `admin_cancelar_subasta()`                                        |
| RN-06       | Una vez iniciada la subasta, el artículo y sus condiciones no pueden modificarse                      | `detalle_subasta()` — artículo en solo lectura si subasta activa  |
| RN-07       | Las ofertas son irreversibles                                                                          | `realizar_oferta()` — no existe ruta de cancelación de oferta     |
| RN-08       | Cada oferta en subasta inglesa debe superar la puja actual más el incremento mínimo                   | `realizar_oferta()` — validación de monto                         |
| RN-09       | Subasta holandesa: el precio baja cada hora; el primero en aceptar gana y la subasta cierra de inmediato | `realizar_oferta()` — rama holandesa + cierre inmediato        |
| RN-10       | El comprador solo ve la puja actual más alta, no el historial completo de ofertas                     | `detalle_subasta()` — historial solo visible para administrador   |
| RN-11       | No se puede realizar una oferta si el comprador tiene pagos pendientes                                | `realizar_oferta()` — consulta tabla `pago`                       |
| RN-12       | No se puede cancelar una cuenta con subastas activas o pagos pendientes                               | `admin_eliminar_usuario()`                                        |
| RN-13       | Cierre automático de subasta al vencer el tiempo establecido                                          | `verificar_cierre_subastas()`                                     |
| RN-14       | Plazo de pago para artículo general: 48 horas                                                         | `realizar_pago()`                                                 |
| RN-15       | Plazo de pago para vehículo: 72 horas                                                                 | `realizar_pago()`                                                 |
| RN-16       | Plazo de pago para inmueble: 7 días                                                                   | `realizar_pago()`                                                 |
| RN-17       | Sin penalización económica por no pagar; el artículo se reasigna al segundo mejor postor             | `verificar_pagos_vencidos()`                                      |
| RN-18       | Si el segundo postor tampoco paga, la subasta se declara desierta                                     | `verificar_pagos_vencidos()`                                      |
| RN-19       | Solo usuarios con cuenta activa y correo no registrado en lista negra pueden registrarse y ofertar    | `@login_required` + validación de lista negra en `/registro`      |
| RN-20       | No se permite publicar artículos de categorías prohibidas                                             | `publicar_articulo()` — validación de categoría                   |
| RN-21       | Solo el administrador puede cancelar publicaciones fraudulentas; el sistema no bloquea automáticamente | `admin_cancelar_subasta()` — no existe bloqueo automático        |
| RN-22/23/24 | Duración válida por tipo: general 1–7 días, vehículo 3–14 días, inmueble 7–30 días                   | `publicar_articulo()` — validación de rango de días              |
| RN-26       | Fraude: cancela cuenta + todas las subastas activas del usuario + registra correo en lista negra      | `admin_usuario()` — acción cancelar con fraude                    |
| RN-27       | Pagos a plazos disponibles para artículos > $10,000 MXN (3/6/12 meses); no aplica para inmuebles     | `realizar_pago()` — crea registro en `plan_pago` si aplica        |

---

## Sistema de notificaciones

Las notificaciones son **internas** (panel web, sin correo en esta versión). Se generan con:

```python
notificar(db, id_usuario, mensaje, tipo, id_ref)
# tipo: "Exito" | "Info" | "Advertencia" | "Error"
```

El contador de notificaciones no leídas en el navbar se actualiza cada **30 segundos** mediante `fetch` al endpoint `/api/notificaciones_count`.

| MSG    | Evento                                           | Destinatario               |
|--------|--------------------------------------------------|----------------------------|
| MSG-01 | Registro exitoso                                 | Comprador                  |
| MSG-02 | Inicio de sesión                                 | Comprador / Administrador  |
| MSG-03 | Oferta registrada — mejor postor actual          | Comprador                  |
| MSG-04 | Oferta superada                                  | Postores anteriores        |
| MSG-05 | Subasta próxima a cerrar (menos de 1 hora)       | Postores activos           |
| MSG-06 | Subasta ganada + plazo de pago                   | Ganador                    |
| MSG-07 | Aprobación automática de artículo                | Vendedor                   |
| MSG-08 | Artículo rechazado con motivo                    | Vendedor                   |
| MSG-09 | Comprobante de pago recibido                     | Comprador y Vendedor       |
| MSG-10 | Plazo de pago vencido + reasignación             | Comprador                  |
| MSG-11 | Cuenta suspendida                                | Usuario afectado           |
| MSG-12 | Subasta cancelada por administrador              | Vendedor y Compradores     |
| MSG-13 | Subasta declarada desierta                       | Vendedor                   |
| MSG-14 | Entrega confirmada                               | Comprador                  |

> **Nota de implementación:** todas las notificaciones se gestionan como alertas internas. Para producción real se recomendaría integrar SMTP (SendGrid o AWS SES) para los eventos MSG-06, MSG-09 y MSG-10 según las reglas de negocio documentadas.

---

## Seguridad

### Contraseñas — bcrypt vía Werkzeug

Las contraseñas nunca se almacenan en texto claro. Al registrarse se genera un hash con salida aleatoria:

```python
from werkzeug.security import generate_password_hash, check_password_hash

# Al registrar
hash_guardado = generate_password_hash("Ana12345")
# Resultado en BD: pbkdf2:sha256:260000$sal_aleatoria$hash

# Al iniciar sesión
check_password_hash(hash_guardado, "Ana12345")  # True
check_password_hash(hash_guardado, "otra")      # False
```

### Sesiones — Flask session

Al autenticarse, Flask guarda `id_usuario` y `rol` en una cookie firmada con `secret_key`. El contenido está codificado en base64, pero la firma criptográfica impide que el usuario lo modifique sin ser detectado.

### Control de acceso — decoradores

Cada ruta protegida verifica la sesión antes de ejecutar cualquier lógica:

```python
@login_required   # requiere sesión activa; si no, redirige a /login
@admin_required   # requiere rol Administrador; si no, devuelve 403
```

### Verificar desde terminal

```bash
# Abrir la base de datos
sqlite3 subasta.db

# Usuarios: las contraseñas aparecen como hash, nunca en texto claro
SELECT id_usuario, nombre, correo, contrasena_hash FROM usuario;

# Subastas activas con tipo resuelto desde catálogo
SELECT s.id_subasta, a.titulo, c.nombre AS tipo, s.precio_actual
FROM subasta s
JOIN articulo a ON s.id_articulo = a.id_articulo
JOIN cat_tipo_subasta c ON a.id_tipo_subasta = c.id_tipo_subasta
WHERE s.estado = 'Activa';

# Log de auditoría del administrador
SELECT * FROM log_admin ORDER BY fecha DESC LIMIT 10;

# Lista negra
SELECT * FROM lista_negra;

.quit
```

---

## Configuración y personalización

### Colores del sitio

Edita el bloque `:root` al inicio de `templates/base.html`:

```css
:root {
  --eb-blue:   #3665f3;  /* botones primarios, links */
  --eb-red:    #e53238;  /* alertas urgentes */
  --eb-green:  #86b817;  /* botón "Hacer oferta" */
  --eb-yellow: #f5af02;  /* estrellas, advertencias */
  --eb-bg:     #f3f3f3;  /* fondo general */
  --eb-text:   #191919;  /* texto principal */
}
```

### Fuente tipográfica

Agrega un `<link>` de Google Fonts antes del `<style>` en `base.html` y actualiza `font-family` en el selector `body`.

### Usuarios demo

Edita el arreglo `usuarios` en `database.py → seed_demo()`. Luego borra `subasta.db` y ejecuta:

```bash
python database.py
```

### Clave secreta de Flask

```python
# app.py línea ~14
app.secret_key = "TU_NUEVA_CLAVE_AQUÍ"
```

### Tamaño máximo de archivos

```python
# app.py línea ~18
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB
```

---

## Tecnologías utilizadas

| Componente             | Tecnología                 | Versión     |
|------------------------|----------------------------|-------------|
| Lenguaje               | Python                     | 3.10+       |
| Framework web          | Flask                      | 3.0+        |
| Cifrado de contraseñas | Werkzeug (bcrypt)          | 3.0+        |
| Base de datos          | SQLite                     | 3           |
| Plantillas HTML        | Jinja2                     | con Flask   |
| CSS y componentes      | Bootstrap                  | 5.3.2 CDN   |
| Diseño UI              | Estilo eBay personalizado  | —           |

> **Nota académica:** no se usa ORM; todas las consultas son SQL directo con `sqlite3` para mayor transparencia pedagógica. Para un entorno de producción real se recomendaría PostgreSQL, almacenamiento externo para comprobantes y un servicio de correo transaccional.

---

*Sistema de Gestión de Subastas — ESCOM-IPN | Análisis y Diseño de Sistemas 2026*
