# Decisiones de implementación — Arreglo 1: Cierre automático y lógica de subastas

## Reglas de negocio aplicadas

### RN-13 — Cierre automático por tiempo
**Fuente:** restricciones.txt, aud1.txt
**Regla:** Cuando `fecha_fin <= now()` y `id_estado = 1 (Activa)`, la subasta debe cerrarse
automáticamente. No se permiten más ofertas tras el vencimiento.
**Impacto:** se crea `verificar_cierre_subastas(db)` que se invoca en `index()`,
`admin_dashboard()`, `detalle_subasta()` y `catalogo()` siguiendo el patrón ya existente
de `verificar_aprobacion_automatica` y `verificar_pagos_vencidos`.

### RN-13 (variante desierta) — Sin ofertas al vencer
**Regla:** Si la subasta vence con 0 ofertas → `id_estado = 3 (Desierta)` + MSG-13 al vendedor.
**Impacto:** manejado dentro de `verificar_cierre_subastas`.

### RN-14 / RN-15 / RN-16 — Plazos de pago por tipo de artículo
**Fuente:** restricciones.txt
**Regla:** El plazo de pago arranca en el **momento del cierre** de la subasta, no cuando
el ganador abre la pantalla de pago.
- General (id_tipo = 1): 48 horas
- Vehículo (id_tipo = 2): 72 horas
- Inmueble (id_tipo = 3): 168 horas (7 días)
**Impacto:** se crea helper `cerrar_subasta_con_ganador(db, id_sub, id_ganador, monto, tipo_art)`
que inserta la fila `pago` con `fecha_limite` calculada desde `now()`.
Se ajusta `realizar_pago()` para reutilizar esa fila en lugar de crearla perezosamente.

### RN-08 — Incremento mínimo (solo Inglesa)
**Fuente:** aud1.txt
**Regla:** El chequeo `monto >= precio_actual + incremento_min` aplica **únicamente** a
subastas Inglesas (id_tipo = 1). Hoy se aplica a todos los tipos — esto rompe Holandesa
y complica Sellada. Se corrige en el Arreglo 2.

### RN-07 — Ofertas irreversibles
**Regla:** Una vez registrada la oferta no puede cancelarse.
**Impacto:** el endurecimiento en `realizar_oferta()` agrega la guardia `fecha_fin <= now`
**antes** de insertar la oferta, para no registrar una oferta en una subasta ya vencida
aunque el barrido `verificar_cierre_subastas` no haya corrido aún.

### ERR-03 — Subasta ya cerrada
**Regla:** Rechazar oferta con ERR-03 si `id_estado != 1` O si `fecha_fin <= now`.
Hoy solo se checa `id_estado`; se añade el chequeo de tiempo.

## Criterios de aceptación (Arreglo 1)

| # | Criterio |
|---|---|
| AC-01 | Subasta vencida con ≥1 oferta → `id_estado=2`, `id_ganador` = MAX(monto), fila `pago` creada con `fecha_limite` correcta, MSG-06 al ganador. |
| AC-02 | Subasta vencida con 0 ofertas → `id_estado=3`, MSG-13 al vendedor. |
| AC-03 | Plazo de pago calculado desde el momento del cierre, no desde la visita a `/pago`. |
| AC-04 | Intentar pujar en subasta con `fecha_fin` pasada → ERR-03, sin insertar oferta. |
| AC-05 | Las subastas Inglesas activas no se ven afectadas (no-regresión). |
| AC-06 | `realizar_pago()` usa la fila `pago` existente; no crea duplicado. |

## Cambios de esquema
Ninguno. `id_estado`, `id_ganador`, `fecha_fin` y la tabla `pago` ya existen.

## Orden de implementación
1. Helper `cerrar_subasta_con_ganador`
2. `verificar_cierre_subastas`
3. Wire-in en las 4 rutas
4. Endurecer `realizar_oferta`
5. Ajustar `realizar_pago`

---

# Decisiones de implementación — Arreglo 2: Subasta Holandesa y Sellada

## Reglas de negocio aplicadas

### RN-09 — Subasta Holandesa (precio descendente)
**Fuente:** aud1.txt, restricciones.txt
**Regla:** El precio arranca alto y **decrece cada hora** hasta un piso. El primer comprador
que acepte el precio vigente **gana y la subasta cierra de inmediato**. No hay incremento
mínimo ni pujas ascendentes.
**Semántica de columnas (decisión de equipo):**
- `precio_base` = precio de **arranque alto** (inmutable; ej. 1000).
- `precio_piso` = **piso/mínimo** al que puede llegar el descenso (ej. 500). [NUEVA columna]
- `decremento_hora` = cuánto baja por cada hora transcurrida (ej. 100). [NUEVA columna]
- `precio_actual` = valor **derivado**, recalculado en cada barrido:
  `precio_actual = max(precio_piso, precio_base - decremento_hora * horas_transcurridas)`.
**Impacto:**
- Nueva `verificar_decremento_holandesa(db)`, invocada junto a las demás `verificar_*`.
- Rama Holandesa en `realizar_oferta()`: omite RN-08, **recalcula el precio vigente en el
  servidor** (no confía en el campo oculto del cliente), registra la oferta y cierra de
  inmediato con `cerrar_subasta_con_ganador` (Arreglo 1) + MSG-06.

### RN-10 — Subasta Sellada (ofertas privadas)
**Fuente:** aud1.txt, restricciones.txt
**Regla:** Cada oferta es **privada**; el ganador se revela **solo al cierre** por tiempo.
Ningún postor ve el monto ni la existencia de otras ofertas.
**Decisiones de equipo:**
- **Una sola oferta por usuario** por subasta sellada (se rechaza la segunda con ERR-11).
- Validación mínima: `monto >= precio_base` (no hay incremento sobre ofertas ajenas).
- **NO** se actualiza `precio_actual` (no se filtra el estado de la puja).
- **NO** se actualiza `id_ganador` durante la subasta (se determina al cierre, Arreglo 1).
- Solo MSG-03 (confirmación al ofertante). **Nunca MSG-04** (delataría que hay competencia).
**Impacto:** la revelación del ganador la realiza `verificar_cierre_subastas` (Arreglo 1),
que toma el `MAX(monto)`.

### RN-08 — Incremento mínimo (ahora restringido a Inglesa)
**Regla:** El chequeo `monto >= precio_actual + incremento_min` queda **exclusivo de la
Inglesa (id_tipo=1)**. Holandesa y Sellada tienen su propia rama en `realizar_oferta()`.

## Criterios de aceptación (Arreglo 2)

| # | Criterio |
|---|---|
| AC-07 | Holandesa: `precio_actual` baja `decremento_hora` por cada hora y **nunca** baja de `precio_piso`. |
| AC-08 | Holandesa: aceptar el precio vigente cierra la subasta de inmediato (`id_estado=2`), fija ganador, crea pago y MSG-06. |
| AC-09 | Holandesa: tras la aceptación, una segunda puja se rechaza (subasta ya no activa). |
| AC-10 | Sellada: dos compradores ofertan; `precio_actual` **no cambia** y `id_ganador` queda NULL hasta el cierre. |
| AC-11 | Sellada: un segundo intento del mismo usuario se rechaza (ERR-11). |
| AC-12 | Sellada: no se genera MSG-04 a ningún postor. |
| AC-13 | Sellada: al vencer por tiempo gana el `MAX(monto)` y se revela (vía Arreglo 1). |
| AC-14 | Inglesa: sigue funcionando con incremento mínimo (no-regresión). |

## Cambios de esquema
- `subasta.precio_piso REAL` — piso del descenso holandés (NULL para otros tipos).
- `subasta.decremento_hora REAL` — decremento por hora (NULL para otros tipos).
- **Migración:** borrar `subasta.db` y regenerar con `seed_demo()` (decisión de equipo).

## Datos demo sembrados (seed_demo)
- INGLESA activa: Laptop Gaming MSI (precio_actual 8500).
- HOLANDESA activa: arranque 1000, piso 500, decremento 100, iniciada hace 3 h → muestra 700.
- SELLADA activa: precio_base 800, cierra en 2 días.
- Segundo comprador: carlos@mail.mx / Carlos1234 (para probar sellada con dos usuarios).

## Orden de implementación (Arreglo 2)
1. Esquema (`precio_piso`, `decremento_hora`) en `database.py` + ajuste del INSERT de `publicar_articulo`.
2. `verificar_decremento_holandesa` + wire-in.
3. Rama Holandesa en `realizar_oferta`.
4. Rama Sellada en `realizar_oferta`.
5. Plantillas (`publicar.html`, `detalle_subasta.html`).
6. Seed: una holandesa (1000/500/100) y una sellada.

---

# Decisiones de implementación — Arreglo 3: Lista negra y flujo de fraude (A6 + C1)

## Reglas de negocio aplicadas

### RN-26 — Cancelación por fraude
**Fuente:** restricciones.txt, aud1.txt
**Regla:** Cuando el administrador detecta fraude, debe:
1. Agregar el correo del usuario a la **lista negra**.
2. Cancelar **todas** las subastas activas del usuario (estado Cancelada + notificar a participantes).
3. Suspender la cuenta del usuario.
**Nota de estado:** el equipo aplica **Suspendida (id_estado=2)** según AC-15. RN-26 textual
dice "Cancelada"; cambiar a id_estado=3 es un solo número si se prefiere.

### RN-26 (registro) — Bloqueo de correos en lista negra
**Regla:** Un correo presente en `lista_negra` no puede registrarse. `registro()` lo valida
antes de crear la cuenta y rechaza con ERR-12.

## Cambios de esquema
- Nueva tabla `lista_negra (id_lista, correo UNIQUE, motivo, fecha)`.

## Criterios de aceptación (Arreglo 3)
| # | Criterio |
|---|---|
| AC-15 | Cancelar por fraude → correo en lista_negra + cuenta suspendida + subastas activas canceladas con notificación. |
| AC-16 | Registro con correo en lista_negra → rechazado con ERR-12. |
| AC-17 | Registro con correo limpio → funciona normal (no-regresión). |

## Orden de implementación (Arreglo 3)
1. Tabla `lista_negra` en `database.py` + seed de un correo de prueba.
2. Acción "CancelarFraude" en `admin_gestionar_usuario()`.
3. Validación de lista negra en `registro()`.

---

# Decisiones de implementación — Arreglo 4: Reportes mensuales del admin (CU-A08)

## Funcionalidad
**Fuente:** CU-A08 (DCU-01), restricciones.txt
Nueva ruta `/admin/reportes` que resume la actividad de un mes:
1. **Subastas por estado** (Activa, Finalizada, Desierta, Cancelada).
2. **Validaciones realizadas** (Aprobado, Rechazado, Automatico).
3. **Transacciones/pagos** (completados, pendientes, vencidos) + monto transado.

## Criterios de corte de período (para que los conteos sean reproducibles — AC-19)
- Subastas: `strftime('%Y-%m', fecha_inicio) = periodo`.
- Validaciones realizadas: `decision IS NOT NULL AND strftime('%Y-%m', fecha_decision) = periodo`.
- Pagos: `strftime('%Y-%m', fecha_limite) = periodo`.
  - Completados = Verificado (id_estado=3); Pendientes = Pendiente(1)+EnVerificacion(2);
    Vencidos = Vencido(4). Monto transado = SUM(monto) de completados.

## Acceso
- Protegida con `@admin_required` (AC-20): un no-admin es redirigido a `index`.

## Criterios de aceptación (Arreglo 4)
| # | Criterio |
|---|---|
| AC-18 | `/admin/reportes` muestra las 3 secciones con datos del mes actual. |
| AC-19 | Los conteos cuadran con la BD (verificado con SQL). |
| AC-20 | Solo accesible para admin; redirige si no lo es. |

## Orden de implementación (Arreglo 4)
1. Ruta `/admin/reportes` en `app.py`.
2. Template `admin_reportes.html` (Bootstrap).
3. Enlace en el navbar admin (`base.html`).
4. Filtro mes/año (form GET).

---

# Decisiones de implementación — Arreglo 5: Imágenes obligatorias al confirmar recepción (CU-C07/C08)

## Funcionalidad
**Fuente:** CU-C07, restricciones.txt
Al confirmar recepción, el comprador debe **adjuntar evidencia fotográfica** (≥1 imagen).
`confirmar_recepcion()` pasa de solo-POST a GET (muestra formulario) + POST (procesa).

## Reglas
- Mínimo **1 imagen** obligatoria; sin imagen → rechazo (AC-21).
- Extensiones permitidas: `.jpg`, `.jpeg`, `.png` (AC-23). Otras → rechazo.
- Tamaño máximo **5 MB por imagen** (validado con seek/tell en el handler).
- `MAX_CONTENT_LENGTH` global sube a 30 MB para permitir varias imágenes por request.
- Archivos en `static/uploads/recepciones/`, nombre `recepcion_{id_pago}_{n}.ext`,
  servibles por `/static/...` (AC-24).
- Las rutas se registran en la nueva tabla `imagen_recepcion`.
- Se mantiene: marcar subasta Finalizada, registrar calificación, actualizar reputación, MSG-14.

## Cambios de esquema
- Nueva tabla `imagen_recepcion (id_imagen, id_pago, ruta, fecha)`.

## Criterios de aceptación (Arreglo 5)
| # | Criterio |
|---|---|
| AC-21 | Confirmar SIN imagen → rechazado con error. |
| AC-22 | Confirmar CON imagen(es) → guardadas en disco + en `imagen_recepcion` + calificación registrada. |
| AC-23 | Extensión no permitida → rechazada. |
| AC-24 | Imágenes accesibles desde el historial. |

## Orden (Arreglo 5)
1. Tabla `imagen_recepcion` en `database.py`.
2. Carpeta `static/uploads/recepciones/`.
3. `confirmar_recepcion()` GET+POST con validación y guardado.
4. `mi_historial()` pasa las imágenes al template; enlace a la página de confirmación.
5. Templates `confirmar_recepcion.html` (nuevo) y `mi_historial.html` (enlace + miniaturas).

---

# Decisiones de implementación — Arreglo 6: Pagos a plazos >$10,000 (CU-C06/C07, RN-27)

## Regla RN-27
**Fuente:** restricciones.txt, aud1.txt
Si el monto a pagar **> $10,000 MXN** y el artículo **NO es inmueble** (id_tipo ≠ 3),
el comprador puede pagar a **3, 6 o 12 meses** (sin intereses) o en un solo pago.
Inmuebles y montos ≤ $10,000 → solo pago completo.

## Diseño
- `realizar_pago()` GET: calcula `aplica_plazos = monto > 10000 and tipo_art != 3` y ofrece opciones.
- POST: si el comprador elige 3/6/12 (y aplica), crea N filas en `plan_pago`:
  - `monto_cuota = round(monto/N, 2)`; la última cuota se ajusta para que la suma sea exacta.
  - `fecha_vencimiento` = hoy + n meses (cuota n).
  - Estado inicial de cada cuota: Pendiente (cat_estado_pago=1).
- La validación de elegibilidad también se aplica en el servidor (AC-26/27): si el plan pedido
  no aplica, se ignora y se trata como pago completo.
- `mi_historial()` muestra, por pago a plazos, cuántas cuotas van pagadas (X/N).

## Cambios de esquema
- Nueva tabla `plan_pago (id_plan, id_pago, num_cuota, monto_cuota, fecha_vencimiento, id_estado)`.

## Criterios de aceptación (Arreglo 6)
| # | Criterio |
|---|---|
| AC-25 | Artículo >$10,000 no-inmueble → se ofrecen 3/6/12. |
| AC-26 | Artículo >$10,000 inmueble → NO se ofrecen plazos. |
| AC-27 | Artículo ≤$10,000 → NO se ofrecen plazos. |
| AC-28 | Elegir 6 meses → 6 cuotas con fechas y montos correctos (suman el total). |
| AC-29 | Las cuotas aparecen en el historial del comprador. |

## Orden (Arreglo 6)
1. Tabla `plan_pago` en `database.py`.
2. Helper `add_months` + lógica en `realizar_pago()` (GET opciones, POST creación de cuotas).
3. Template `realizar_pago.html` (selector de plan + tabla de cuotas).
4. `mi_historial()` + `mi_historial.html` (indicador X/N cuotas).

---

# Decisiones de implementación — Arreglo 7: Correo stub / bandeja de salida (C10)

## Enfoque
**Fuente:** restricciones.txt (notificaciones por correo)
No se integra SMTP real. Se simula el envío con una **bandeja de salida** (`correo_salida`):
cada vez que el sistema "enviaría" un correo, registra el destinatario, asunto y cuerpo.
Esto demuestra que el sistema sabe *cuándo* y *a quién* notificar, sin depender de un mail server.

## Puntos de envío (los dos que pide el profesor)
- **Al GANAR una subasta** (dentro de `cerrar_subasta_con_ganador`):
  asunto `Has ganado la subasta: {titulo}`.
- **Al VENCER un pago** (dentro de `verificar_pagos_vencidos`):
  asunto `Tu pago ha vencido: {titulo}`.

## Cambios de esquema
- Nueva tabla `correo_salida (id_correo, id_destinatario, correo_destino, asunto, cuerpo, fecha, enviado)`.

## Acceso
- `/admin/correos` protegida con `@admin_required` (AC-33).

## Criterios de aceptación (Arreglo 7)
| # | Criterio |
|---|---|
| AC-30 | Cierre con ganador → fila en `correo_salida` con datos correctos. |
| AC-31 | Pago vencido → fila en `correo_salida`. |
| AC-32 | `/admin/correos` muestra toda la bandeja. |
| AC-33 | Solo accesible para admin. |

## Orden (Arreglo 7)
1. Tabla `correo_salida` en `database.py`.
2. Helper `enviar_correo(db, id_usuario, asunto, cuerpo)`.
3. Llamadas en `cerrar_subasta_con_ganador` y `verificar_pagos_vencidos`.
4. Ruta `/admin/correos` + template + enlace en navbar.

---

# Decisiones de implementación — Arreglo 8: Cosméticos y cierre

## Cambios
### A1 — Segundo administrador
**Fuente:** aud1.txt ("son 2 admins con los mismos permisos")
`seed_demo()` agrega `admin2@subasta.mx / Admin1234` ("Admin Dos"), insertado **al final**
de la lista de usuarios para no desplazar los IDs demo (Ana=2, Carlos=3, Vendedor=4).

### A3 — Validación de vehículo/inmueble sin fecha límite
**Fuente:** aud1.txt/restricciones.txt ("sin límite de tiempo" para vehículo/inmueble)
- `publicar_articulo()`: `fecha_limite` solo se fija para General (id_tipo=1); vehículo e
  inmueble se insertan con `fecha_limite = NULL`.
- Seed: la validación demo del vehículo pasa a `fecha_limite = NULL`.
- `admin_dashboard.html`: muestra "Sin límite" cuando `fecha_limite` es NULL (en vez de inferir
  por tipo), y la fecha con ⚠️ cuando existe.

### A — README alineado a la realidad
README reescrito para reflejar EXACTAMENTE lo implementado (3 tipos de subasta, cierre
automático, lista negra, reportes `/admin/reportes`, pagos a plazos, imágenes de recepción,
bandeja de correos). Se eliminaron funcionalidades fantasma del README anterior
(`/admin/reporte`, flag `en_lista_negra`, `plan_pago` con interés, columnas inexistentes).

### .gitignore
Nuevo: `subasta.db`, `__pycache__/`, `*.pyc`, `static/uploads/recepciones/`, `uploads/`, `.env`.

## Criterios de aceptación (Arreglo 8)
| # | Criterio |
|---|---|
| AC-34 | Existen 2 admins en el seed. |
| AC-35 | Validación de vehículo/inmueble sin `fecha_limite` (NULL); el dashboard dice "Sin límite". |
| AC-36 | README refleja el estado real del código (sin funcionalidades fantasma). |
