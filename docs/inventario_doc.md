# Inventario para Documentación — Sistema de Gestión de Subastas

> **Fuente:** extraído del código real (`app.py`, `database.py`) y consolidado con
> `docs/decisiones.md`. Nada en este documento es inventado: cada ítem apunta a la función,
> ruta o tabla que lo implementa.

---

## 1. Requerimientos Funcionales (RF)

| ID | Nombre | Descripción | Implementación |
|----|--------|-------------|----------------|
| RF-001 | Registro de comprador | Alta de cuenta con nombre, correo y contraseña; valida aceptación de términos, contraseña ≥8, correo único y que no esté en lista negra | `registro()` |
| RF-002 | Inicio de sesión | Autenticación por correo/contraseña; verifica hash y que la cuenta esté activa; redirige según rol | `login()` |
| RF-003 | Cierre de sesión | Limpia la sesión activa | `logout()` |
| RF-004 | Consultar catálogo | Lista subastas activas con filtro por categoría y búsqueda por texto | `catalogo()` |
| RF-005 | Ver detalle de subasta | Muestra datos del artículo, precio vigente y caja de oferta según el tipo de subasta | `detalle_subasta()` |
| RF-006 | Publicar artículo | El vendedor crea un artículo y su subasta; valida la duración permitida por tipo | `publicar_articulo()` |
| RF-007 | Capturar datos de vehículo/inmueble | Registra atributos extendidos (marca, km, superficie, etc.) según el tipo | `publicar_articulo()` |
| RF-008 | Oferta en subasta Inglesa | Puja ascendente que debe superar precio actual + incremento mínimo | `realizar_oferta()` (rama Inglesa) |
| RF-009 | Oferta en subasta Holandesa | Aceptar el precio vigente (recalculado en servidor); gana y cierra de inmediato | `realizar_oferta()` (rama Holandesa) |
| RF-010 | Oferta en subasta Sellada | Oferta privada, una por usuario; no revela montos ni competencia | `realizar_oferta()` (rama Sellada) |
| RF-011 | Cierre automático por tiempo | Al vencer `fecha_fin`, cierra con ganador (MAX) o declara desierta | `verificar_cierre_subastas()` |
| RF-012 | Descenso horario de holandesa | Recalcula `precio_actual` por horas transcurridas hasta el piso | `verificar_decremento_holandesa()` |
| RF-013 | Realizar pago | El ganador sube comprobante (JPG/PNG/PDF ≤5MB); estado pasa a EnVerificacion | `realizar_pago()` |
| RF-014 | Pago a plazos | Genera 3/6/12 cuotas sin interés si el monto >$10,000 y no es inmueble | `realizar_pago()` + `plan_pago` |
| RF-015 | Confirmar recepción | Confirma entrega adjuntando ≥1 imagen de evidencia | `confirmar_recepcion()` |
| RF-016 | Calificar al vendedor | Registra puntuación 1–5 y recalcula la reputación promedio | `confirmar_recepcion()` |
| RF-017 | Historial personal | Muestra ofertas, subastas ganadas, pagos, cuotas e imágenes de recepción | `mi_historial()` |
| RF-018 | Ver notificaciones | Lista las notificaciones del usuario y las marca como leídas | `notificaciones()` |
| RF-019 | Contador de no leídas | Endpoint JSON consultado por el navbar | `notificaciones_count()` |
| RF-020 | Panel de administración | Lista artículos pendientes, subastas y usuarios | `admin_dashboard()` |
| RF-021 | Validar artículo | Aprobar, rechazar (con motivo) o extender plazo de validación | `admin_validar()` |
| RF-022 | Aprobación automática | Aprueba artículos Generales si vence el plazo de 30 min sin acción | `verificar_aprobacion_automatica()` |
| RF-023 | Cancelar subasta | El admin cancela una subasta activa con motivo y notifica a participantes | `admin_cancelar_subasta()` |
| RF-024 | Gestionar usuarios | Suspender, cancelar o reactivar cuentas | `admin_gestionar_usuario()` |
| RF-025 | Cancelación por fraude | Lista negra del correo + cancela subastas activas + suspende cuenta | `admin_gestionar_usuario()` (CancelarFraude) |
| RF-026 | CRUD de usuarios (admin) | Crear, editar (incl. contraseña) y eliminar usuarios sin actividad | `admin_nuevo_usuario()`, `admin_editar_usuario()`, `admin_eliminar_usuario()` |
| RF-027 | Reasignación por impago | Al vencer el pago, reasigna al 2º postor o declara desierta | `verificar_pagos_vencidos()` |
| RF-028 | Reportes mensuales | Resumen de subastas, validaciones y pagos por período (mes/año) | `admin_reportes()` |
| RF-029 | Bandeja de correos | Registra/visualiza correos simulados (al ganar y al vencer pago) | `enviar_correo()`, `admin_correos()` |
| RF-030 | Auditoría administrativa | Registra toda acción relevante del admin | tabla `log_admin` (todas las rutas admin) |

---

## 2. Requerimientos No Funcionales (RNF)

| ID | Categoría | Descripción | Evidencia en el código |
|----|-----------|-------------|------------------------|
| RNF-01 | Seguridad | Contraseñas almacenadas con hash + sal (nunca en claro) | `generate_password_hash` / `check_password_hash` (Werkzeug) |
| RNF-02 | Seguridad | Control de acceso por rol mediante decoradores | `@login_required`, `@admin_required` |
| RNF-03 | Seguridad | Sesiones firmadas con clave secreta | `app.secret_key` + Flask session |
| RNF-04 | Seguridad | Integridad referencial garantizada por el motor | `PRAGMA foreign_keys = ON` |
| RNF-05 | Seguridad | El precio de la holandesa se recalcula en el servidor (no confía en el cliente) | `realizar_oferta()` rama Holandesa |
| RNF-06 | Seguridad | Bloqueo de correos fraudulentos en el registro | `lista_negra` + `registro()` |
| RNF-07 | Seguridad / Capacidad | Validación de tipo y tamaño de archivos subidos | `allowed_file`, `MAX_CONTENT_LENGTH` (30MB), 5MB por imagen |
| RNF-08 | Rendimiento | Valores calculados cacheados para evitar recálculos | `subasta.precio_actual`, `usuario.reputacion`/`total_cal` |
| RNF-09 | Rendimiento | Los barridos solo escriben si hay filas afectadas | `if pendientes/vencidos/cambios: db.commit()` |
| RNF-10 | Usabilidad | Mensajes del sistema codificados (MSG-/ERR-) y categorizados | `flash(...)`, `notificar(...)` |
| RNF-11 | Usabilidad | Actualización del contador de notificaciones sin recargar | `/api/notificaciones_count` (poll desde navbar) |
| RNF-12 | Usabilidad | Interfaz y mensajes en español | plantillas + textos de `flash` |
| RNF-13 | Mantenibilidad | Base de datos normalizada en 3FN con catálogos | `database.py` (tablas `cat_*`) |
| RNF-14 | Mantenibilidad | Decisiones de diseño documentadas por arreglo | `docs/decisiones.md` |
| RNF-15 | Auditabilidad | Registro permanente de acciones administrativas | tabla `log_admin` |
| RNF-16 | Portabilidad | Base embebida sin servidor externo | SQLite (`subasta.db`) |

---

## 3. Reglas de Negocio (consolidadas de `docs/decisiones.md` + código)

| ID | Nombre | Descripción | Condición | Acción |
|----|--------|-------------|-----------|--------|
| RN-02 | Aprobación automática (General) | Los artículos Generales se aprueban solos si el admin no actúa a tiempo | `decision IS NULL` AND tipo=General AND `fecha_limite ≤ now` | Estado→Aprobado, `decision='Automatico'`, MSG-07 al vendedor |
| RN-03 | Validación obligatoria sin límite (Vehículo/Inmueble) | Vehículos e inmuebles requieren revisión documental manual | tipo=Vehículo o Inmueble | Se crea validación con `fecha_limite = NULL`; nunca se auto-aprueba |
| RN-07 | Ofertas irreversibles | Una oferta registrada no puede cancelarse | Oferta ya insertada | No existe ruta de cancelación; guardia de `fecha_fin` antes de insertar |
| RN-08 | Incremento mínimo (solo Inglesa) | La puja debe superar el precio actual más el incremento | tipo=Inglesa AND `monto < precio_actual + incremento_min` | Rechaza con ERR-02 |
| RN-09 | Subasta Holandesa | El precio baja por hora hasta un piso; el primero en aceptar gana | tipo=Holandesa | `precio_actual = max(precio_piso, precio_base − decremento_hora × horas)`; aceptar cierra de inmediato + MSG-06 |
| RN-10 | Subasta Sellada / privacidad de ofertas | Ofertas privadas; el comprador no ve el historial ni montos ajenos | tipo=Sellada (o usuario no-admin en detalle) | Una oferta por usuario (ERR-11), `monto ≥ precio_base` (ERR-02); no actualiza precio ni ganador; gana MAX al cierre; nunca MSG-04 |
| RN-11 | Bloqueo de oferta con pago pendiente | No se puede ofertar con un pago sin completar | Existe `pago` del comprador con `id_estado=1` | Rechaza con ERR-10 |
| RN-13 | Cierre automático por tiempo | La subasta se cierra al vencer su plazo | `id_estado=1` AND `fecha_fin ≤ now` | Con ofertas→Finalizada + ganador (MAX, desempate `fecha_oferta ASC`); sin ofertas→Desierta + MSG-13 |
| RN-14 | Plazo de pago — General | El ganador de un artículo General tiene 48 h para pagar | Cierre con ganador, tipo=General | `pago.fecha_limite = cierre + 48 h` |
| RN-15 | Plazo de pago — Vehículo | Vehículo: 72 h para pagar | Cierre con ganador, tipo=Vehículo | `pago.fecha_limite = cierre + 72 h` |
| RN-16 | Plazo de pago — Inmueble | Inmueble: 168 h (7 días) para pagar | Cierre con ganador, tipo=Inmueble | `pago.fecha_limite = cierre + 168 h` |
| RN-17 | Sin penalización + reasignación | Si el ganador no paga, no hay multa y se ofrece al siguiente | `pago.id_estado=1` AND `fecha_limite ≤ now` | Pago→Vencido, MSG-10; reasigna al 2º postor con nuevo pago + MSG-06 |
| RN-18 | Subasta desierta | Si nadie completa el pago, la subasta queda desierta | 2º postor tampoco paga (o no hay 2º) | Subasta→Desierta + MSG-13 al vendedor |
| RN-22 | Duración — General | Duración válida de la subasta General | tipo=General | Entre 1 y 7 días; fuera de rango se rechaza |
| RN-23 | Duración — Vehículo | Duración válida de la subasta de Vehículo | tipo=Vehículo | Entre 3 y 14 días; fuera de rango se rechaza |
| RN-24 | Duración — Inmueble | Duración válida de la subasta de Inmueble | tipo=Inmueble | Entre 7 y 30 días; fuera de rango se rechaza |
| RN-26 | Cancelación por fraude | Ante fraude, se bloquea al usuario y se limpian sus subastas | Admin ejecuta acción `CancelarFraude` | Correo→`lista_negra`, cuenta→Suspendida, subastas activas→Cancelada + notificación, MSG-11; registro posterior de ese correo→ERR-12 |
| RN-27 | Pagos a plazos | Compras grandes (no inmuebles) pueden pagarse en cuotas | `monto > $10,000` AND tipo≠Inmueble | Ofrece 3/6/12 cuotas sin interés; crea filas en `plan_pago` |

> **Nota de numeración:** `RN-13` cubre tanto el cierre con ganador como la variante "desierta sin
> ofertas" (ambas en `verificar_cierre_subastas`). `RN-10` se usa en el código tanto para la subasta
> Sellada como para "el comprador solo ve la puja actual"; ambos conceptos comparten la idea de
> privacidad de ofertas. Reglas mencionadas en restricciones pero **sin código propio dedicado**
> (p. ej. validación previa genérica, no-modificación tras iniciar) se consideran cubiertas
> implícitamente por el flujo de estados y no se listan como RN implementadas para no inventar.

---

## 4. Mensajes del sistema (MSG)

> Todos presentes en `app.py`. Se emiten vía `flash(...)` (UI) y/o `notificar(...)` (panel de notificaciones).

| ID | Texto / evento | Destinatario | Origen |
|----|----------------|--------------|--------|
| MSG-01 | "Cuenta creada exitosamente" | Comprador | `registro()` |
| MSG-02 | "Ha iniciado sesión correctamente" | Cualquier usuario | `login()` |
| MSG-03 | "Tu oferta fue registrada / eres el mejor postor" (también oferta sellada) | Ofertante | `realizar_oferta()` |
| MSG-04 | "Tu oferta fue superada" | Postores anteriores (solo Inglesa) | `realizar_oferta()` |
| MSG-06 | "¡Ganaste la subasta! Completa tu pago antes de…" | Ganador | `cerrar_subasta_con_ganador()`, `verificar_pagos_vencidos()`, rama Holandesa |
| MSG-07 | "Tu artículo fue aprobado automáticamente" | Vendedor | `verificar_aprobacion_automatica()` |
| MSG-08 | "Tu artículo fue rechazado. Motivo: …" | Vendedor | `admin_validar()` |
| MSG-09 | "Comprobante recibido / en verificación" | Comprador y Vendedor | `realizar_pago()` |
| MSG-10 | "El plazo de pago venció. La compra fue reasignada" | Comprador | `verificar_pagos_vencidos()` |
| MSG-11 | "Tu cuenta ha sido suspendida" (incumplimiento / fraude) | Usuario afectado | `admin_gestionar_usuario()` |
| MSG-12 | "La subasta fue cancelada. Motivo: …" | Compradores participantes | `admin_cancelar_subasta()`, CancelarFraude |
| MSG-13 | "La subasta fue declarada desierta" | Vendedor | `verificar_cierre_subastas()`, `verificar_pagos_vencidos()` |
| MSG-14 | "Entrega confirmada exitosamente" | Comprador | `confirmar_recepcion()` |

> **No implementado:** `MSG-05` ("subasta próxima a cerrar") aparece en documentación previa pero
> **no existe en el código**. No se incluye para no inventar.

---

## 5. Errores del sistema (ERR)

> Todos presentes en `app.py`, emitidos vía `flash(..., "danger")`.

| ID | Texto / condición | Origen |
|----|-------------------|--------|
| ERR-01 | "Credenciales incorrectas" — correo/contraseña inválidos | `login()` |
| ERR-02 | "La oferta debe ser al menos $X" — monto por debajo del mínimo (Inglesa) o del precio base (Sellada) | `realizar_oferta()` |
| ERR-03 | "La subasta ya cerró / ya venció por tiempo" | `realizar_oferta()` |
| ERR-04 | "Solo se aceptan JPG/PNG/PDF (máx 5 MB)" — archivo no permitido o demasiado grande | `realizar_pago()`, `confirmar_recepcion()` |
| ERR-07 | "Su cuenta no está activa" — login con cuenta suspendida/cancelada | `login()` |
| ERR-10 | "Completa los pagos pendientes antes de participar" | `realizar_oferta()` |
| ERR-11 | "Ya enviaste tu oferta sellada (una por usuario)" | `realizar_oferta()` (rama Sellada) |
| ERR-12 | "Este correo no puede registrarse" — correo en lista negra | `registro()` |
| ERR-13 | "Debes adjuntar al menos una imagen de evidencia" | `confirmar_recepcion()` |

> **No usados:** `ERR-05`, `ERR-06`, `ERR-08`, `ERR-09` no existen en el código actual. La numeración
> tiene huecos a propósito (los códigos se reservaron pero no se llegaron a usar).
