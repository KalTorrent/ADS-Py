# Capítulo 5 — Diagrama de Clases

> **Fuente:** los **atributos** se derivan del esquema real (`database.py`) y los **métodos** de
> las funciones/rutas implementadas en `app.py`. Al final hay una tabla de trazabilidad
> método → función real. El sistema no usa ORM (SQL directo), por lo que el diagrama es un
> **modelo conceptual** de las entidades del dominio, no una transcripción de clases Python.

## Diagrama PlantUML

```plantuml
@startuml diagrama_clases
skinparam classAttributeIconSize 0
skinparam shadowing false
hide empty members

' ───────────── USUARIO ─────────────
class Usuario {
  - id_usuario : int
  - nombre : str
  - correo : str
  - password_hash : str
  - id_tipo : int  ' 1=Admin 2=Comprador 3=Vendedor
  - id_estado : int ' 1=Activa 2=Suspendida 3=Cancelada
  - reputacion : float
  - total_cal : int
  - fecha_registro : str
  - terminos_ok : bool
  --
  + registrar()
  + iniciarSesion()
  + cerrarSesion()
  + suspender()
  + cancelar()
  + reactivar()
  + cancelarPorFraude()
  + actualizarReputacion()
  + crear()  ' admin
  + editar() ' admin
  + eliminar() ' admin, solo sin actividad
}

' ───────────── ARTICULO + extensiones ─────────────
class Articulo {
  - id_articulo : int
  - titulo : str
  - descripcion : str
  - id_tipo : int
  - id_condicion : int
  - ubicacion : str
  - id_vendedor : int
  - id_estado : int ' 1=Pendiente 2=Aprobado 3=Rechazado 4=Publicado
  - fecha_registro : str
  - imagen_path : str
  --
  + publicar()
  + aprobar()
  + rechazar()
  + aprobarAutomatico()
}

class Vehiculo {
  - id_articulo : int
  - marca : str
  - modelo : str
  - anio : int
  - kilometraje : int
  - num_serie : str
  - doc_path : str
}

class Inmueble {
  - id_articulo : int
  - tipo_propiedad : str
  - superficie_terreno : float
  - superficie_construida : float
  - num_habitaciones : int
  - ubicacion_detallada : str
  - doc_path : str
}

' ───────────── VALIDACION ─────────────
class Validacion {
  - id_validacion : int
  - id_articulo : int
  - id_admin : int
  - decision : str ' Aprobado|Rechazado|Automatico
  - comentario : str
  - fecha_limite : str ' NULL para vehiculo/inmueble
  - fecha_decision : str
  - extendida : bool
  --
  + aprobar()
  + rechazar()
  + extenderPlazo()
  + verificarAprobacionAutomatica()
}

' ───────────── SUBASTA ─────────────
class Subasta {
  - id_subasta : int
  - id_articulo : int
  - id_tipo : int ' 1=Inglesa 2=Holandesa 3=Sellada
  - precio_base : float
  - precio_actual : float
  - incremento_min : float
  - precio_piso : float
  - decremento_hora : float
  - fecha_inicio : str
  - fecha_fin : str
  - id_estado : int ' 1=Activa 2=Finalizada 3=Desierta 4=Cancelada
  - id_ganador : int
  - motivo_cancel : str
  --
  + crear()
  + cancelar()
  + cerrar()
  + verificarCierre()
  + declararDesierta()
  + recalcularPrecioHolandesa()
  + determinarGanador()
}

' ───────────── OFERTA ─────────────
class Oferta {
  - id_oferta : int
  - id_subasta : int
  - id_comprador : int
  - monto : float
  - fecha_oferta : str
  - es_sellada : bool
  --
  + registrar()        ' Inglesa
  + aceptarPrecio()    ' Holandesa
  + registrarSellada() ' Sellada (privada)
}

' ───────────── PAGO ─────────────
class Pago {
  - id_pago : int
  - id_subasta : int
  - id_comprador : int
  - monto : float
  - id_estado : int ' 1=Pend 2=EnVerif 3=Verif 4=Vencido 5=Reasignado
  - comprobante : str
  - fecha_limite : str
  - fecha_pago : str
  - es_segundo : bool
  --
  + crear()
  + registrarComprobante()
  + verificarVencidos()
  + reasignarSegundoPostor()
}

' ───────────── PLAN_PAGO ─────────────
class PlanPago {
  - id_plan : int
  - id_pago : int
  - num_cuota : int
  - monto_cuota : float
  - fecha_vencimiento : str
  - id_estado : int
  --
  + generarCuotas()  ' 3/6/12 meses, RN-27
}

' ───────────── CALIFICACION ─────────────
class Calificacion {
  - id_calificacion : int
  - id_subasta : int
  - id_calificador : int
  - id_calificado : int
  - puntuacion : int ' 1..5
  - comentario : str
  - fecha : str
  --
  + registrar()
}

' ───────────── IMAGEN_RECEPCION ─────────────
class ImagenRecepcion {
  - id_imagen : int
  - id_pago : int
  - ruta : str
  - fecha : str
  --
  + guardar()
}

' ───────────── NOTIFICACION ─────────────
class Notificacion {
  - id_notificacion : int
  - id_usuario : int
  - mensaje : str
  - tipo : str ' Exito|Info|Advertencia|Error
  - leida : bool
  - fecha : str
  - id_ref : int
  --
  + crear()
  + marcarLeidas()
  + contarNoLeidas()
}

' ───────────── CORREO_SALIDA ─────────────
class CorreoSalida {
  - id_correo : int
  - id_destinatario : int
  - correo_destino : str
  - asunto : str
  - cuerpo : str
  - fecha : str
  - enviado : bool
  --
  + enviar()      ' stub: registra en bandeja
  + verBandeja()  ' admin
}

' ───────────── ListaNegra ─────────────
class ListaNegra {
  - id_lista : int
  - correo : str
  - motivo : str
  - fecha : str
  --
  + agregar()
  + estaBloqueado()
}

' ───────────── RELACIONES Y CARDINALIDAD ─────────────
Usuario "1" --> "0..*" Articulo        : vende
Articulo "1" --> "0..1" Vehiculo       : extiende
Articulo "1" --> "0..1" Inmueble       : extiende
Articulo "1" --> "0..*" Validacion     : se valida
Usuario  "1" --> "0..*" Validacion     : valida (admin)
Articulo "1" --> "1"    Subasta        : se subasta
Subasta  "1" --> "0..*" Oferta         : recibe
Usuario  "1" --> "0..*" Oferta         : puja
Subasta  "1" --> "0..*" Pago           : genera
Usuario  "1" --> "0..*" Pago           : paga
Usuario  "0..1" <-- "0..*" Subasta     : gana
Pago     "1" --> "0..*" PlanPago       : se divide en cuotas
Pago     "1" --> "0..*" ImagenRecepcion: evidencia
Subasta  "1" --> "0..*" Calificacion   : se califica
Usuario  "1" --> "0..*" Calificacion   : emite/recibe
Usuario  "1" --> "0..*" Notificacion   : recibe
Usuario  "1" --> "0..*" CorreoSalida   : destinatario
Usuario  "1" --> "0..*" ListaNegra     : bloqueado por correo

@enduml
```

---

## Trazabilidad: método de clase → función real en `app.py`

| Clase.método | Función / ruta real | Notas |
|--------------|---------------------|-------|
| `Usuario.registrar()` | `registro()` | Valida términos, longitud ≥8, correo único y lista negra (RN-26) |
| `Usuario.iniciarSesion()` | `login()` | Verifica hash y estado de cuenta |
| `Usuario.cerrarSesion()` | `logout()` | `session.clear()` |
| `Usuario.suspender()` / `cancelar()` / `reactivar()` | `admin_gestionar_usuario()` | Acciones Suspender/Cancelar/Reactivar |
| `Usuario.cancelarPorFraude()` | `admin_gestionar_usuario()` (acción `CancelarFraude`) | Lista negra + cancela subastas + suspende (RN-26) |
| `Usuario.actualizarReputacion()` | `confirmar_recepcion()` | `AVG`/`COUNT` de calificaciones |
| `Usuario.crear()` / `editar()` / `eliminar()` | `admin_nuevo_usuario()` / `admin_editar_usuario()` / `admin_eliminar_usuario()` | Eliminar solo si no hay actividad |
| `Articulo.publicar()` | `publicar_articulo()` | Valida duración por tipo (RN-22/23/24) |
| `Articulo.aprobar()` / `rechazar()` | `admin_validar()` | Rechazo exige motivo |
| `Articulo.aprobarAutomatico()` | `verificar_aprobacion_automatica()` | Solo General a los 30 min (RN-02) |
| `Validacion.extenderPlazo()` | `admin_validar()` (acción `Extender`) | +30 min, marca `extendida` |
| `Validacion.verificarAprobacionAutomatica()` | `verificar_aprobacion_automatica()` | Barrido |
| `Subasta.crear()` | `publicar_articulo()` | Inserta también `precio_piso`/`decremento_hora` si es holandesa |
| `Subasta.cancelar()` | `admin_cancelar_subasta()` | Motivo obligatorio (RN-05/CU-A06) |
| `Subasta.cerrar()` | `cerrar_subasta_con_ganador()` | Fija ganador + crea `pago` con plazo (RN-13/14/15/16) |
| `Subasta.verificarCierre()` | `verificar_cierre_subastas()` | Cierra por `fecha_fin` vencida (RN-13) |
| `Subasta.declararDesierta()` | `verificar_cierre_subastas()` / `verificar_pagos_vencidos()` | 0 ofertas o 2º no paga (RN-18) |
| `Subasta.recalcularPrecioHolandesa()` | `verificar_decremento_holandesa()` | Descenso horario (RN-09) |
| `Subasta.determinarGanador()` | `verificar_cierre_subastas()` | `MAX(monto)`, desempate por `fecha_oferta ASC` |
| `Oferta.registrar()` | `realizar_oferta()` rama Inglesa | Incremento mínimo (RN-08) |
| `Oferta.aceptarPrecio()` | `realizar_oferta()` rama Holandesa | Recalcula precio en servidor + cierre inmediato (RN-09) |
| `Oferta.registrarSellada()` | `realizar_oferta()` rama Sellada | Una por usuario, privada (RN-10) |
| `Pago.crear()` | `cerrar_subasta_con_ganador()` | Plazo según tipo de artículo |
| `Pago.registrarComprobante()` | `realizar_pago()` | Sube comprobante, estado→EnVerificacion |
| `Pago.verificarVencidos()` | `verificar_pagos_vencidos()` | Marca Vencido (RN-17) |
| `Pago.reasignarSegundoPostor()` | `verificar_pagos_vencidos()` | Nuevo pago al 2º postor (RN-17/18) |
| `PlanPago.generarCuotas()` | `realizar_pago()` | 3/6/12 cuotas si monto>$10k y no inmueble (RN-27) |
| `Calificacion.registrar()` | `confirmar_recepcion()` | Puntuación 1–5 |
| `ImagenRecepcion.guardar()` | `confirmar_recepcion()` | ≥1 imagen JPG/PNG ≤5MB obligatoria |
| `Notificacion.crear()` | `notificar()` | Helper interno |
| `Notificacion.marcarLeidas()` | `notificaciones()` | Marca todas leídas al abrir |
| `Notificacion.contarNoLeidas()` | `notificaciones_count()` | API JSON (poll navbar) |
| `CorreoSalida.enviar()` | `enviar_correo()` | Stub: registra en `correo_salida` (sin SMTP) |
| `CorreoSalida.verBandeja()` | `admin_correos()` | Vista admin |
| `ListaNegra.agregar()` | `admin_gestionar_usuario()` (CancelarFraude) | `INSERT OR IGNORE` |
| `ListaNegra.estaBloqueado()` | `registro()` | Bloquea correo en lista negra (ERR-12) |
