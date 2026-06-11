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
