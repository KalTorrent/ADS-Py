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
