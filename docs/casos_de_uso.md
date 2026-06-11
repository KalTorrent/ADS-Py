# Capítulo 4 — Especificación Formal de Casos de Uso

> **Fuente:** cada caso de uso se extrae de la ruta/función real en `app.py`. Las precondiciones,
> validaciones, errores y flujos corresponden exactamente al código implementado (Arreglos 1–8).
> Los códigos RF, RN, ERR y AC referencian `docs/inventario_doc.md` y `docs/decisiones.md`.

**Actores:** Administrador (`id_tipo = 1`) y Comprador (`id_tipo = 2`). El Vendedor (`id_tipo = 3`)
existe para dar coherencia al flujo pero está fuera del alcance documentado.

---

# Casos de Uso — ADMINISTRADOR

## CU-A01: Iniciar sesión (Administrador)
- **Identificador:** CU-A01
- **Actor:** Administrador
- **Descripción:** El administrador se autentica con correo y contraseña para acceder a su panel de gestión.
- **Datos de entrada:** `correo`, `password` (formulario POST).
- **Datos de salida:** Sesión iniciada (`user_id`, `user_nombre`, `user_tipo=1`); mensaje MSG-02; redirección a `/admin`.
- **Precondición:** Existe una cuenta con rol Administrador y estado de cuenta Activa.
- **Postcondición:** Sesión activa con privilegios de administrador.
- **Errores asociados:** ERR-01 (Credenciales incorrectas), ERR-07 (Cuenta no activa).
- **Reglas de negocio:** —
- **Requerimientos asociados:** RF-002.
- **Criterios de aceptación:** AC-34 (existen 2 administradores en el seed con los mismos permisos).
- **Trayectoria principal:**
  1. El admin abre `/login` (GET) y ve el formulario.
  2. Envía correo y contraseña (POST).
  3. El sistema busca el usuario por correo y verifica el hash de la contraseña.
  4. Verifica que `id_estado = 1` (Activa).
  5. Guarda la sesión y muestra MSG-02.
  6. Como `id_tipo = 1`, redirige a `/admin`.
- **Trayectorias alternativas:**
  - **TA-1:** Correo inexistente o contraseña inválida → ERR-01, permanece en login.
  - **TA-2:** Cuenta suspendida/cancelada (`id_estado ≠ 1`) → ERR-07.

## CU-A02: Validar artículo general
- **Identificador:** CU-A02
- **Actor:** Administrador
- **Descripción:** El administrador aprueba o rechaza un artículo de tipo General pendiente de validación.
- **Datos de entrada:** `id_art` (URL); `accion` = Aprobar | Rechazar; `comentario` (obligatorio al rechazar).
- **Datos de salida:** `articulo.id_estado` → 2 (Aprobado) o 3 (Rechazado); `validacion` actualizada con `decision`, `id_admin`, `comentario`, `fecha_decision`; notificación al vendedor (MSG-08 si rechazo); registro en `log_admin`.
- **Precondición:** Administrador autenticado; el artículo está en estado Pendiente con una validación cuyo `decision IS NULL`.
- **Postcondición:** El artículo queda Aprobado o Rechazado; la validación registra la decisión.
- **Errores asociados:** — (el rechazo sin motivo se bloquea con un aviso, sin código ERR).
- **Reglas de negocio:** RN-02 (aprobación automática si vence el plazo sin acción).
- **Requerimientos asociados:** RF-021, RF-022.
- **Criterios de aceptación:** —
- **Trayectoria principal:**
  1. El admin abre `/admin/validar/<id_art>` (GET) y revisa el artículo.
  2. Selecciona "Aprobar" y envía (POST).
  3. El sistema actualiza el artículo a Aprobado y la validación con `decision='Aprobado'`.
  4. Notifica al vendedor y registra en `log_admin`.
  5. Redirige al panel con confirmación.
- **Trayectorias alternativas:**
  - **TA-1:** Acción "Rechazar" con comentario → artículo Rechazado, MSG-08 al vendedor, log.
  - **TA-2:** "Rechazar" sin comentario → aviso "Debes indicar el motivo del rechazo"; no se aplica el cambio.
  - **TA-3:** El admin no actúa y vence el plazo de 30 min → el barrido `verificar_aprobacion_automatica()` aprueba el artículo (`decision='Automatico'`) y emite MSG-07 (RN-02).

## CU-A03: Validar vehículo / inmueble
- **Identificador:** CU-A03
- **Actor:** Administrador
- **Descripción:** El administrador revisa la documentación de un vehículo o inmueble y lo aprueba o rechaza; este tipo no tiene aprobación automática.
- **Datos de entrada:** `id_art` (URL); `accion` = Aprobar | Rechazar; `comentario`.
- **Datos de salida:** `articulo.id_estado` → 2 o 3; `validacion` actualizada; notificación al vendedor; `log_admin`.
- **Precondición:** Administrador autenticado; artículo de tipo Vehículo o Inmueble en estado Pendiente; su validación se creó con `fecha_limite = NULL` (sin temporizador).
- **Postcondición:** Artículo Aprobado o Rechazado tras revisión documental manual.
- **Errores asociados:** —
- **Reglas de negocio:** RN-03 (validación obligatoria sin límite de tiempo; nunca se auto-aprueba).
- **Requerimientos asociados:** RF-021.
- **Criterios de aceptación:** AC-35 (validación de vehículo/inmueble sin `fecha_limite`; el dashboard muestra "Sin límite").
- **Trayectoria principal:**
  1. El admin abre `/admin/validar/<id_art>` y revisa los datos extendidos (vehículo: marca, modelo, año, km, n.º serie; inmueble: tipo, superficies, habitaciones).
  2. Aprueba o rechaza con comentario.
  3. El sistema actualiza artículo y validación, notifica y registra en log.
- **Trayectorias alternativas:**
  - **TA-1:** Rechazo sin motivo → aviso, sin aplicar cambio.
  - **TA-2:** El plazo nunca vence automáticamente (NULL) → el artículo permanece Pendiente hasta decisión manual (a diferencia de CU-A02).

## CU-A04: Extender plazo de validación
- **Identificador:** CU-A04
- **Actor:** Administrador
- **Descripción:** El administrador amplía 30 minutos el plazo de validación de un artículo General pendiente.
- **Datos de entrada:** `id_art` (URL); `accion` = Extender.
- **Datos de salida:** `validacion.fecha_limite` += 30 min; `validacion.extendida = 1`; registro en `log_admin`.
- **Precondición:** Administrador autenticado; existe una validación pendiente (`decision IS NULL`) con `fecha_limite` (artículo General).
- **Postcondición:** El temporizador de aprobación automática se pospone 30 minutos.
- **Errores asociados:** —
- **Reglas de negocio:** RN-02 (el plazo extendido difiere la aprobación automática).
- **Requerimientos asociados:** RF-021.
- **Criterios de aceptación:** —
- **Trayectoria principal:**
  1. En `/admin/validar/<id_art>` el admin elige "Extender" (POST).
  2. El sistema recalcula `fecha_limite = ahora + 30 min` y marca `extendida = 1`.
  3. Registra la acción en `log_admin` y muestra confirmación.
- **Trayectorias alternativas:**
  - **TA-1:** Tras extender, sigue en la pantalla de validación para decidir luego.

## CU-A05: Cancelar subasta activa
- **Identificador:** CU-A05
- **Actor:** Administrador
- **Descripción:** El administrador cancela una subasta activa por política, indicando el motivo, y notifica a los participantes.
- **Datos de entrada:** `id_sub` (URL); `motivo` (obligatorio).
- **Datos de salida:** `subasta.id_estado` → 4 (Cancelada) y `motivo_cancel`; MSG-12 a cada comprador participante; aviso al vendedor; registro en `log_admin`.
- **Precondición:** Administrador autenticado; la subasta existe y está Activa (`id_estado = 1`).
- **Postcondición:** Subasta cancelada; participantes notificados.
- **Errores asociados:** — (motivo vacío y subasta no activa se manejan con avisos, sin código ERR).
- **Reglas de negocio:** —
- **Requerimientos asociados:** RF-023.
- **Criterios de aceptación:** —
- **Trayectoria principal:**
  1. El admin envía POST a `/admin/cancelar_subasta/<id_sub>` con el motivo.
  2. El sistema valida que el motivo no esté vacío.
  3. Verifica que la subasta esté Activa.
  4. La marca Cancelada con el motivo.
  5. Notifica a todos los compradores (MSG-12) y al vendedor; registra en log.
- **Trayectorias alternativas:**
  - **TA-1:** Motivo vacío → aviso "Debes indicar el motivo de cancelación"; no cancela.
  - **TA-2:** Subasta inexistente o no activa → aviso "La subasta no está activa o no existe".

## CU-A06: Gestionar usuarios (suspender / cancelar / reactivar)
- **Identificador:** CU-A06
- **Actor:** Administrador
- **Descripción:** El administrador cambia el estado de la cuenta de un usuario: suspender, cancelar o reactivar.
- **Datos de entrada:** `id_usr` (URL); `accion` = Suspender | Cancelar | Reactivar.
- **Datos de salida:** `usuario.id_estado` → 2 (Suspendida), 3 (Cancelada) o 1 (Activa); MSG-11 al suspender; registro en `log_admin`.
- **Precondición:** Administrador autenticado; el usuario objetivo existe.
- **Postcondición:** El estado de la cuenta queda modificado.
- **Errores asociados:** — (usuario inexistente → aviso, sin código ERR).
- **Reglas de negocio:** —
- **Requerimientos asociados:** RF-024.
- **Criterios de aceptación:** —
- **Trayectoria principal:**
  1. El admin envía POST a `/admin/usuario/<id_usr>` con la acción.
  2. El sistema verifica que el usuario exista.
  3. Suspender → `id_estado=2` + MSG-11; Cancelar → `id_estado=3`; Reactivar → `id_estado=1`.
  4. Registra en `log_admin` y muestra confirmación.
- **Trayectorias alternativas:**
  - **TA-1:** Usuario no encontrado → aviso "Usuario no encontrado".

## CU-A07: Cancelar usuario por fraude
- **Identificador:** CU-A07
- **Actor:** Administrador
- **Descripción:** Ante un fraude, el administrador bloquea el correo del usuario, suspende su cuenta y cancela todas sus subastas activas.
- **Datos de entrada:** `id_usr` (URL); `accion` = CancelarFraude.
- **Datos de salida:** Correo insertado en `lista_negra`; `usuario.id_estado` → 2 (Suspendida); subastas activas del usuario → 4 (Cancelada) con MSG-12 a sus participantes; MSG-11 al usuario; registro en `log_admin`.
- **Precondición:** Administrador autenticado; el usuario objetivo existe.
- **Postcondición:** Usuario suspendido, correo en lista negra, subastas activas canceladas.
- **Errores asociados:** —
- **Reglas de negocio:** RN-26 (cancelación por fraude).
- **Requerimientos asociados:** RF-025.
- **Criterios de aceptación:** AC-15 (correo en lista negra + cuenta suspendida + subastas canceladas con notificación).
- **Trayectoria principal:**
  1. El admin envía POST a `/admin/usuario/<id_usr>` con `accion=CancelarFraude`.
  2. El sistema inserta el correo en `lista_negra` (`INSERT OR IGNORE`).
  3. Suspende la cuenta (`id_estado=2`).
  4. Busca las subastas activas donde el usuario es vendedor y las cancela una a una, notificando a los participantes con MSG-12.
  5. Notifica al usuario con MSG-11 y registra en `log_admin` (incluye el número de subastas canceladas).
- **Trayectorias alternativas:**
  - **TA-1:** El usuario no tiene subastas activas → solo se bloquea el correo y se suspende la cuenta.
  - **TA-2 (efecto posterior):** Si ese correo intenta registrarse de nuevo → ERR-12 (ver CU-C01).

## CU-A08: Generar reportes mensuales
- **Identificador:** CU-A08
- **Actor:** Administrador
- **Descripción:** El administrador consulta un reporte mensual con subastas por estado, validaciones realizadas y pagos/transacciones del período.
- **Datos de entrada:** `anio`, `mes` (query string; por defecto el mes actual).
- **Datos de salida:** Render de `admin_reportes.html` con: subastas por estado (Activa/Finalizada/Desierta/Cancelada), validaciones (Aprobado/Rechazado/Automatico), pagos (completados/pendientes/vencidos) y monto transado.
- **Precondición:** Administrador autenticado (`@admin_required`).
- **Postcondición:** Ninguna (consulta de solo lectura).
- **Errores asociados:** —
- **Reglas de negocio:** —
- **Requerimientos asociados:** RF-028.
- **Criterios de aceptación:** AC-18 (3 secciones del mes), AC-19 (los conteos cuadran con la BD), AC-20 (solo accesible para admin).
- **Trayectoria principal:**
  1. El admin abre `/admin/reportes` (opcionalmente con `?anio=&mes=`).
  2. El sistema arma el período `YYYY-MM`.
  3. Agrupa subastas por estado (por `fecha_inicio`), validaciones con decisión (por `fecha_decision`) y pagos (por `fecha_limite`).
  4. Renderiza las tres secciones con el selector de mes/año.
- **Trayectorias alternativas:**
  - **TA-1:** `anio`/`mes` no numéricos → se usa el mes actual.
  - **TA-2:** Usuario no administrador → redirigido a `/` (decorador `@admin_required`).

## CU-A09: Ver bandeja de correos de salida
- **Identificador:** CU-A09
- **Actor:** Administrador
- **Descripción:** El administrador consulta la bandeja de correos simulados que el sistema "habría enviado" (al ganar una subasta y al vencer un pago).
- **Datos de entrada:** Ninguno.
- **Datos de salida:** Render de `admin_correos.html` con la lista de `correo_salida` (destinatario, correo, asunto, cuerpo, fecha, estado).
- **Precondición:** Administrador autenticado (`@admin_required`).
- **Postcondición:** Ninguna (consulta de solo lectura).
- **Errores asociados:** —
- **Reglas de negocio:** —
- **Requerimientos asociados:** RF-029.
- **Criterios de aceptación:** AC-32 (`/admin/correos` muestra toda la bandeja), AC-33 (solo accesible para admin). Las filas se crean en AC-30 (cierre con ganador) y AC-31 (pago vencido).
- **Trayectoria principal:**
  1. El admin abre `/admin/correos`.
  2. El sistema lista los correos ordenados por fecha descendente.
- **Trayectorias alternativas:**
  - **TA-1:** Usuario no administrador → redirigido a `/`.

## CU-A10: Ver historial de pujas de una subasta
- **Identificador:** CU-A10
- **Actor:** Administrador
- **Descripción:** Al abrir el detalle de una subasta, el administrador ve el historial completo de ofertas (montos y postores), que está oculto para los compradores.
- **Datos de entrada:** `id_sub` (URL).
- **Datos de salida:** Lista de ofertas (monto, fecha, nombre del postor) ordenada por monto descendente, además del detalle de la subasta.
- **Precondición:** La subasta existe; la sesión es de un administrador (`user_tipo = 1`).
- **Postcondición:** Ninguna (consulta de solo lectura).
- **Errores asociados:** —
- **Reglas de negocio:** RN-10 (privacidad de ofertas: el historial completo solo es visible para el administrador).
- **Requerimientos asociados:** RF-005.
- **Criterios de aceptación:** —
- **Trayectoria principal:**
  1. El admin abre `/subasta/<id_sub>`.
  2. El sistema detecta `user_tipo = 1` y consulta todas las ofertas de la subasta.
  3. Renderiza el detalle incluyendo el historial de pujas.
- **Trayectorias alternativas:**
  - **TA-1:** Un comprador/visitante abre la misma vista → el historial se omite (queda `None`); solo ve la puja actual.
  - **TA-2:** Subasta inexistente → aviso y redirección a `/catalogo`.

---

# Casos de Uso — COMPRADOR

## CU-C01: Registrarse en la plataforma
- **Identificador:** CU-C01
- **Actor:** Comprador
- **Descripción:** Una persona crea una cuenta de comprador aceptando los términos y condiciones.
- **Datos de entrada:** `nombre`, `correo`, `password`, `terminos` (checkbox).
- **Datos de salida:** Nuevo `usuario` con `id_tipo=2` y `terminos_ok=1`; mensaje MSG-01; redirección a `/login`.
- **Precondición:** Ninguna (acceso público).
- **Postcondición:** Cuenta de comprador creada y activa.
- **Errores asociados:** ERR-12 (correo en lista negra).
- **Reglas de negocio:** RN-26 (bloqueo de correos en lista negra).
- **Requerimientos asociados:** RF-001.
- **Criterios de aceptación:** AC-16 (registro con correo en lista negra → rechazado con ERR-12), AC-17 (correo limpio → registro normal).
- **Trayectoria principal:**
  1. El usuario abre `/registro` (GET).
  2. Completa nombre, correo, contraseña y marca los términos; envía (POST).
  3. El sistema valida: términos aceptados, contraseña ≥ 8, correo no existente, correo no en lista negra.
  4. Crea el usuario con contraseña hasheada y muestra MSG-01.
  5. Redirige a `/login`.
- **Trayectorias alternativas:**
  - **TA-1:** No acepta términos → aviso "Debes aceptar los términos y condiciones".
  - **TA-2:** Contraseña < 8 caracteres → aviso "La contraseña debe tener al menos 8 caracteres".
  - **TA-3:** Correo ya registrado → aviso "El correo ya está registrado".
  - **TA-4:** Correo en lista negra → ERR-12, no se crea la cuenta.

## CU-C02: Iniciar sesión (Comprador)
- **Identificador:** CU-C02
- **Actor:** Comprador
- **Descripción:** El comprador se autentica para acceder a las funciones de oferta, pago e historial.
- **Datos de entrada:** `correo`, `password`.
- **Datos de salida:** Sesión iniciada (`user_tipo=2`); MSG-02; redirección a `/` (inicio).
- **Precondición:** Existe una cuenta con ese correo y estado Activa.
- **Postcondición:** Sesión de comprador activa.
- **Errores asociados:** ERR-01 (Credenciales incorrectas), ERR-07 (Cuenta no activa).
- **Reglas de negocio:** —
- **Requerimientos asociados:** RF-002.
- **Criterios de aceptación:** —
- **Trayectoria principal:**
  1. Abre `/login`, envía correo y contraseña.
  2. El sistema verifica hash y estado de cuenta.
  3. Inicia sesión, muestra MSG-02 y redirige a `/`.
- **Trayectorias alternativas:**
  - **TA-1:** Credenciales inválidas → ERR-01.
  - **TA-2:** Cuenta no activa → ERR-07.

## CU-C03: Consultar catálogo
- **Identificador:** CU-C03
- **Actor:** Comprador (acceso público).
- **Descripción:** El comprador explora las subastas activas, con filtro por categoría y búsqueda por texto.
- **Datos de entrada:** `categoria` (opcional), `q` (texto de búsqueda, opcional) — query string.
- **Datos de salida:** Lista de subastas activas con título, ubicación, precio actual, tipo, vendedor y reputación.
- **Precondición:** Ninguna (acceso público).
- **Postcondición:** Ninguna (consulta). Como efecto, se ejecutan los barridos `verificar_decremento_holandesa()` y `verificar_cierre_subastas()`.
- **Errores asociados:** —
- **Reglas de negocio:** RN-09 (precio holandés recalculado), RN-13 (cierre por tiempo) ejecutados en la carga.
- **Requerimientos asociados:** RF-004.
- **Criterios de aceptación:** —
- **Trayectoria principal:**
  1. El usuario abre `/catalogo` (opcionalmente con `?categoria=&q=`).
  2. El sistema actualiza precios holandeses y cierra subastas vencidas.
  3. Consulta subastas Activas aplicando los filtros.
  4. Renderiza el listado con las categorías disponibles.
- **Trayectorias alternativas:**
  - **TA-1:** Filtro por categoría → solo subastas de ese tipo de artículo.
  - **TA-2:** Búsqueda por texto → coincidencias en título o descripción.

## CU-C04: Realizar oferta en subasta Inglesa
- **Identificador:** CU-C04
- **Actor:** Comprador
- **Descripción:** El comprador puja en una subasta Inglesa con un monto que debe superar el precio actual más el incremento mínimo.
- **Datos de entrada:** `id_sub` (URL); `monto` (formulario).
- **Datos de salida:** Nueva `oferta` (`es_sellada=0`); `subasta.precio_actual` y `id_ganador` actualizados; MSG-03 al ofertante; MSG-04 a los postores anteriores.
- **Precondición:** Comprador autenticado (no administrador); subasta de tipo Inglesa Activa y no vencida por tiempo; el comprador no tiene pagos pendientes.
- **Postcondición:** Oferta registrada; el comprador es el mejor postor.
- **Errores asociados:** ERR-02 (oferta por debajo del mínimo), ERR-03 (subasta cerrada/vencida), ERR-10 (pagos pendientes).
- **Reglas de negocio:** RN-07 (oferta irreversible), RN-08 (incremento mínimo), RN-11 (bloqueo con pago pendiente), RN-13 (rechazo si venció por tiempo).
- **Requerimientos asociados:** RF-008.
- **Criterios de aceptación:** AC-14 (la Inglesa sigue funcionando con incremento mínimo — no-regresión).
- **Trayectoria principal:**
  1. El comprador envía POST a `/oferta/<id_sub>` con el monto.
  2. El sistema verifica que no sea administrador.
  3. Verifica que la subasta esté Activa y que `fecha_fin` no haya pasado.
  4. Verifica que el comprador no tenga pagos pendientes.
  5. Valida `monto ≥ precio_actual + incremento_min`.
  6. Inserta la oferta, actualiza `precio_actual` e `id_ganador`.
  7. Emite MSG-03 al ofertante y MSG-04 a los postores anteriores.
- **Trayectorias alternativas:**
  - **TA-1:** Es administrador → aviso "Los administradores no pueden realizar ofertas".
  - **TA-2:** Subasta no activa → ERR-03.
  - **TA-3:** `fecha_fin` ya pasó → ERR-03 ("ya venció por tiempo").
  - **TA-4:** Tiene un pago pendiente → ERR-10.
  - **TA-5:** Monto no numérico → aviso "Monto inválido".
  - **TA-6:** Monto por debajo del mínimo → ERR-02.

## CU-C05: Aceptar precio en subasta Holandesa
- **Identificador:** CU-C05
- **Actor:** Comprador
- **Descripción:** El comprador acepta el precio vigente (descendente) de una subasta Holandesa; con ello gana y la subasta cierra de inmediato.
- **Datos de entrada:** `id_sub` (URL). *(El monto se recalcula en el servidor; no se confía en el valor del cliente.)*
- **Datos de salida:** Nueva `oferta` con el precio vigente; `subasta` → Finalizada con `id_ganador`; fila `pago` creada con plazo según tipo; MSG-06 al ganador; correo stub de "ganaste"; `subasta.precio_actual` actualizado.
- **Precondición:** Comprador autenticado (no administrador); subasta de tipo Holandesa Activa; sin pagos pendientes.
- **Postcondición:** Subasta finalizada; el comprador es el ganador; pago pendiente generado.
- **Errores asociados:** ERR-03 (subasta cerrada/vencida), ERR-10 (pagos pendientes).
- **Reglas de negocio:** RN-09 (subasta holandesa; precio = `max(precio_piso, precio_base − decremento_hora × horas)`; cierre inmediato).
- **Requerimientos asociados:** RF-009.
- **Criterios de aceptación:** AC-07 (el precio baja por hora y nunca por debajo del piso), AC-08 (aceptar cierra de inmediato, fija ganador, crea pago y MSG-06), AC-09 (una segunda puja posterior se rechaza).
- **Trayectoria principal:**
  1. El comprador envía POST a `/oferta/<id_sub>`.
  2. El sistema verifica subasta Activa, no vencida y sin pagos pendientes del comprador.
  3. Detecta tipo Holandesa: recalcula el precio vigente según las horas transcurridas.
  4. Inserta la oferta con ese precio y actualiza `precio_actual`.
  5. Cierra la subasta con ganador (`cerrar_subasta_con_ganador`): estado Finalizada, crea `pago` con plazo, MSG-06 y correo stub.
  6. Muestra "¡Aceptaste $X y ganaste la subasta!".
- **Trayectorias alternativas:**
  - **TA-1:** Subasta ya cerrada → ERR-03; una segunda aceptación posterior falla (AC-09).
  - **TA-2:** Comprador con pago pendiente → ERR-10.
  - **TA-3:** Es administrador → aviso, no puede ofertar.

## CU-C06: Realizar oferta en subasta Sellada
- **Identificador:** CU-C06
- **Actor:** Comprador
- **Descripción:** El comprador envía una oferta privada en una subasta Sellada; solo se permite una por usuario y no se revelan los montos hasta el cierre.
- **Datos de entrada:** `id_sub` (URL); `monto` (formulario).
- **Datos de salida:** Nueva `oferta` privada (`es_sellada=1`); MSG-03 al ofertante. **No** se actualizan `precio_actual` ni `id_ganador`; **no** se emite MSG-04.
- **Precondición:** Comprador autenticado (no administrador); subasta de tipo Sellada Activa; sin pagos pendientes; el comprador no ha ofertado antes en esa subasta.
- **Postcondición:** Oferta privada registrada; el ganador se determinará al cierre por tiempo.
- **Errores asociados:** ERR-02 (monto menor al precio base), ERR-03 (subasta cerrada), ERR-10 (pagos pendientes), ERR-11 (segunda oferta del mismo usuario).
- **Reglas de negocio:** RN-10 (subasta sellada: ofertas privadas, una por usuario, sin filtrar el estado de la puja).
- **Requerimientos asociados:** RF-010.
- **Criterios de aceptación:** AC-10 (`precio_actual` no cambia y `id_ganador` queda NULL), AC-11 (segundo intento del mismo usuario → ERR-11), AC-12 (no se genera MSG-04), AC-13 (al vencer gana el MAX y se revela).
- **Trayectoria principal:**
  1. El comprador envía POST a `/oferta/<id_sub>` con el monto.
  2. El sistema verifica subasta Activa, no vencida y sin pagos pendientes.
  3. Detecta tipo Sellada y verifica que el usuario no haya ofertado antes.
  4. Valida `monto ≥ precio_base`.
  5. Inserta la oferta privada (`es_sellada=1`) y emite MSG-03; no toca precio ni ganador.
- **Trayectorias alternativas:**
  - **TA-1:** El usuario ya tenía una oferta en esa subasta → ERR-11.
  - **TA-2:** Monto por debajo del precio base → ERR-02.
  - **TA-3:** Subasta no activa → ERR-03; pago pendiente → ERR-10.
  - **TA-4 (cierre):** Al vencer `fecha_fin`, `verificar_cierre_subastas()` revela y gana el MAX(monto) (AC-13).

## CU-C07: Realizar pago (completo o a plazos)
- **Identificador:** CU-C07
- **Actor:** Comprador
- **Descripción:** El ganador sube el comprobante de pago; si el monto supera $10,000 y no es inmueble, puede pagar en 3, 6 o 12 cuotas.
- **Datos de entrada:** `id_sub` (URL); `comprobante` (archivo JPG/PNG/PDF); `plan` = completo | 3 | 6 | 12.
- **Datos de salida:** `pago.comprobante` guardado, `id_estado` → 2 (EnVerificacion), `fecha_pago`; si aplica plazos, filas en `plan_pago` (cuotas con fechas y montos); MSG-09 al vendedor y al comprador.
- **Precondición:** Comprador autenticado y ganador de la subasta (`id_ganador`); existe una fila `pago` no vencida (creada al cierre de la subasta).
- **Postcondición:** Comprobante registrado; pago en verificación; cuotas creadas si se eligió plan.
- **Errores asociados:** ERR-04 (archivo no permitido o > 5 MB).
- **Reglas de negocio:** RN-14/15/16 (la fila de pago y su plazo se crean al cierre, no aquí), RN-27 (pagos a plazos si monto > $10,000 y no es inmueble).
- **Requerimientos asociados:** RF-013, RF-014.
- **Criterios de aceptación:** AC-25 (>$10,000 no inmueble → se ofrecen 3/6/12), AC-26 (>$10,000 inmueble → sin plazos), AC-27 (≤$10,000 → sin plazos), AC-28 (elegir 6 meses → 6 cuotas correctas que suman el total), AC-29 (las cuotas aparecen en el historial).
- **Trayectoria principal:**
  1. El comprador abre `/pago/<id_sub>` (GET); el sistema verifica que sea el ganador y muestra el monto y, si aplica, las opciones de plazos.
  2. Adjunta el comprobante y, opcionalmente, elige un plan de cuotas; envía (POST).
  3. El sistema valida la extensión del archivo y lo guarda; actualiza el pago a EnVerificacion con `fecha_pago`.
  4. Si eligió 3/6/12 y aplica (monto > $10,000 y tipo ≠ inmueble), crea las cuotas en `plan_pago` (la última se ajusta para que la suma sea exacta).
  5. Notifica al vendedor y al comprador con MSG-09 y redirige al historial.
- **Trayectorias alternativas:**
  - **TA-1:** El usuario no es el ganador de esa subasta → aviso y redirección al historial.
  - **TA-2:** No existe el registro de pago → aviso "No se encontró el registro de pago".
  - **TA-3:** Archivo con extensión no permitida → ERR-04.
  - **TA-4:** No adjunta comprobante → aviso "Debes adjuntar el comprobante de pago".
  - **TA-5:** Elige plazos pero no cumple las condiciones (≤$10,000 o inmueble) → se ignora el plan y se trata como pago completo.

## CU-C08: Confirmar recepción con evidencia fotográfica
- **Identificador:** CU-C08
- **Actor:** Comprador
- **Descripción:** El comprador confirma la entrega adjuntando al menos una imagen como evidencia y califica al vendedor.
- **Datos de entrada:** `id_sub` (URL); `puntuacion` (1–5); `comentario_cal`; `imagenes` (una o varias, JPG/PNG ≤ 5 MB c/u).
- **Datos de salida:** Filas en `imagen_recepcion`; `subasta.id_estado` → 2 (Finalizada); nueva `calificacion`; `reputacion`/`total_cal` del vendedor recalculados; MSG-14 al comprador.
- **Precondición:** Comprador autenticado y ganador de la subasta; existe un pago asociado (`id_pago` no nulo).
- **Postcondición:** Recepción confirmada con evidencia; vendedor calificado; reputación actualizada.
- **Errores asociados:** ERR-13 (falta imagen de evidencia), ERR-04 (extensión no permitida o > 5 MB).
- **Reglas de negocio:** — (la calificación 1–5 valida el rango sin código RN dedicado).
- **Requerimientos asociados:** RF-015, RF-016.
- **Criterios de aceptación:** AC-21 (confirmar sin imagen → rechazado), AC-22 (con imágenes → guardadas en disco y en `imagen_recepcion` + calificación registrada), AC-23 (extensión no permitida → rechazada), AC-24 (imágenes accesibles desde el historial).
- **Trayectoria principal:**
  1. El comprador abre `/confirmar_recepcion/<id_sub>` (GET) y ve el formulario.
  2. Indica la puntuación (1–5), un comentario opcional y adjunta una o más imágenes; envía (POST).
  3. El sistema valida el rango de la puntuación y que haya al menos una imagen.
  4. Valida extensión (JPG/PNG) y tamaño (≤ 5 MB) de **todas** las imágenes antes de guardar nada.
  5. Guarda las imágenes en `static/uploads/recepciones/` y registra sus rutas en `imagen_recepcion`.
  6. Marca la subasta Finalizada, inserta la calificación y recalcula la reputación del vendedor.
  7. Emite MSG-14 y redirige al historial.
- **Trayectorias alternativas:**
  - **TA-1:** No tiene una recepción pendiente para esa subasta → aviso y redirección al historial.
  - **TA-2:** Puntuación fuera de 1–5 → aviso "La calificación debe ser entre 1 y 5".
  - **TA-3:** No adjunta ninguna imagen → ERR-13.
  - **TA-4:** Imagen con extensión no permitida → ERR-04.
  - **TA-5:** Imagen mayor a 5 MB → ERR-04.

## CU-C09: Consultar historial personal
- **Identificador:** CU-C09
- **Actor:** Comprador
- **Descripción:** El comprador revisa sus ofertas realizadas, subastas ganadas, pagos, cuotas a plazos e imágenes de recepción.
- **Datos de entrada:** Ninguno (usa la sesión).
- **Datos de salida:** Render de `mi_historial.html` con: ofertas, pagos, subastas ganadas, mapa de imágenes de recepción por subasta y progreso de cuotas (pagadas/total).
- **Precondición:** Comprador autenticado.
- **Postcondición:** Ninguna (consulta de solo lectura).
- **Errores asociados:** —
- **Reglas de negocio:** RN-27 (muestra el avance de cuotas X/N).
- **Requerimientos asociados:** RF-017.
- **Criterios de aceptación:** AC-24 (imágenes de recepción accesibles desde el historial), AC-29 (cuotas visibles en el historial).
- **Trayectoria principal:**
  1. El comprador abre `/mi_historial`.
  2. El sistema consulta sus ofertas, pagos, subastas ganadas, imágenes de recepción y planes de pago.
  3. Renderiza las secciones con los datos.
- **Trayectorias alternativas:**
  - **TA-1:** Sin sesión activa → el decorador `@login_required` redirige a `/login`.

## CU-C10: Ver notificaciones
- **Identificador:** CU-C10
- **Actor:** Comprador
- **Descripción:** El comprador consulta sus notificaciones internas; al abrir la página, todas se marcan como leídas.
- **Datos de entrada:** Ninguno (usa la sesión).
- **Datos de salida:** Render de `notificaciones.html` con la lista de notificaciones; todas pasan a `leida=1`.
- **Precondición:** Comprador autenticado.
- **Postcondición:** Las notificaciones del usuario quedan marcadas como leídas.
- **Errores asociados:** —
- **Reglas de negocio:** —
- **Requerimientos asociados:** RF-018 (y RF-019 para el contador en el navbar vía `/api/notificaciones_count`).
- **Criterios de aceptación:** —
- **Trayectoria principal:**
  1. El comprador abre `/notificaciones`.
  2. El sistema lista sus notificaciones ordenadas por fecha descendente.
  3. Marca todas como leídas y renderiza la vista.
- **Trayectorias alternativas:**
  - **TA-1:** El navbar consulta `/api/notificaciones_count` periódicamente y muestra el número de no leídas sin recargar (RF-019).

---

## Nota de alcance

Además de los casos anteriores, en `app.py` existen rutas administrativas de **CRUD de usuarios**
no incluidas en la enumeración solicitada, pero implementadas: crear usuario
(`/admin/usuario/nuevo`), editar usuario y credenciales (`/admin/usuario/<id>/editar`) y eliminar
usuario sin actividad (`/admin/usuario/<id>/eliminar`), además del panel principal
(`/admin` → `admin_dashboard`). Se documentan aquí como referencia para no omitir funcionalidad real;
pueden especificarse con el mismo formato si se requiere ampliar el Capítulo 4.
