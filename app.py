"""
app.py - Sistema de Gestión de Subastas
Actores: Administrador y Comprador (Vendedor incluido para coherencia del flujo)
Tecnología: Python 3 + Flask + SQLite
"""
import os
import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, g)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import get_db, init_db, seed_demo

app = Flask(__name__)
app.secret_key = "SUB4ST4_S3CR3T_K3Y_2024"
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # 30MB: permite varias imagenes/request (5MB c/u validado en handler)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Helpers ────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Inicia sesión para continuar.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_tipo") != 1:
            flash("Acceso restringido a administradores.", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return login_required(decorated)


def notificar(db, id_usuario, mensaje, tipo="Info", id_ref=None):
    db.execute(
        "INSERT INTO notificacion (id_usuario,mensaje,tipo,id_ref) VALUES(?,?,?,?)",
        (id_usuario, mensaje, tipo, id_ref)
    )


def now_str():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def add_months(dt, months):
    """Suma meses a una fecha (día acotado a 28 para evitar desbordes de mes)."""
    m = dt.month - 1 + months
    y = dt.year + m // 12
    m = m % 12 + 1
    return dt.replace(year=y, month=m, day=min(dt.day, 28))


def verificar_aprobacion_automatica(db):
    """RN-02: aprueba artículos generales si venció el plazo sin acción."""
    pendientes = db.execute(
        """SELECT v.id_validacion, v.id_articulo, a.id_vendedor
           FROM validacion v
           JOIN articulo a ON a.id_articulo = v.id_articulo
           JOIN cat_tipo_articulo t ON t.id = a.id_tipo
           WHERE v.decision IS NULL
             AND t.tipo = 'General'
             AND v.fecha_limite <= ?""",
        (now_str(),)
    ).fetchall()
    for p in pendientes:
        db.execute(
            "UPDATE articulo SET id_estado=2 WHERE id_articulo=?",
            (p["id_articulo"],)
        )
        db.execute(
            "UPDATE validacion SET decision='Automatico', fecha_decision=? WHERE id_validacion=?",
            (now_str(), p["id_validacion"])
        )
        notificar(db, p["id_vendedor"],
                  f"MSG-07: Tu artículo fue aprobado automáticamente al vencer el plazo.",
                  "Info", p["id_articulo"])
    if pendientes:
        db.commit()


def verificar_pagos_vencidos(db):
    """RN-17/18: reasigna o declara desierta si vence plazo de pago."""
    vencidos = db.execute(
        """SELECT p.id_pago, p.id_subasta, p.id_comprador, p.monto, p.es_segundo
           FROM pago p
           WHERE p.id_estado=1 AND p.fecha_limite <= ?""",
        (now_str(),)
    ).fetchall()
    for p in vencidos:
        db.execute("UPDATE pago SET id_estado=4 WHERE id_pago=?", (p["id_pago"],))
        notificar(db, p["id_comprador"],
                  "MSG-10: El plazo de pago venció. La compra fue reasignada.", "Advertencia",
                  p["id_subasta"])
        if not p["es_segundo"]:
            seg = db.execute(
                """SELECT o.id_comprador, o.monto
                   FROM oferta o
                   WHERE o.id_subasta=? AND o.id_comprador!=?
                   ORDER BY o.monto DESC LIMIT 1""",
                (p["id_subasta"], p["id_comprador"])
            ).fetchone()
            if seg:
                sub = db.execute("SELECT id_articulo FROM subasta WHERE id_subasta=?",
                                 (p["id_subasta"],)).fetchone()
                tipo_id = db.execute("SELECT id_tipo FROM articulo WHERE id_articulo=?",
                                     (sub["id_articulo"],)).fetchone()["id_tipo"]
                plazos = {1: 48, 2: 72, 3: 168}
                horas = plazos.get(tipo_id, 48)
                limite = (datetime.datetime.utcnow() +
                          datetime.timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
                db.execute(
                    """INSERT INTO pago (id_subasta,id_comprador,monto,id_estado,fecha_limite,es_segundo)
                       VALUES(?,?,?,1,?,1)""",
                    (p["id_subasta"], seg["id_comprador"], seg["monto"], limite)
                )
                db.execute("UPDATE subasta SET id_ganador=? WHERE id_subasta=?",
                           (seg["id_comprador"], p["id_subasta"]))
                notificar(db, seg["id_comprador"],
                          f"MSG-06: ¡Ganaste la subasta! Completa tu pago antes de {limite}.",
                          "Exito", p["id_subasta"])
            else:
                db.execute("UPDATE subasta SET id_estado=3 WHERE id_subasta=?",
                           (p["id_subasta"],))
                sub2 = db.execute(
                    "SELECT s.id_articulo, a.id_vendedor FROM subasta s JOIN articulo a ON a.id_articulo=s.id_articulo WHERE s.id_subasta=?",
                    (p["id_subasta"],)
                ).fetchone()
                notificar(db, sub2["id_vendedor"],
                          "MSG-13: La subasta fue declarada desierta. Ningún postor completó el pago.",
                          "Info", p["id_subasta"])
        else:
            db.execute("UPDATE subasta SET id_estado=3 WHERE id_subasta=?", (p["id_subasta"],))
    if vencidos:
        db.commit()


def cerrar_subasta_con_ganador(db, id_sub, id_ganador, monto, tipo_art):
    """RN-13/14/15/16: marca Finalizada, fija ganador y crea pago con plazo correcto al cierre."""
    plazos = {1: 48, 2: 72, 3: 168}
    horas = plazos.get(tipo_art, 48)
    limite = (datetime.datetime.utcnow() +
              datetime.timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE subasta SET id_estado=2, id_ganador=? WHERE id_subasta=?",
        (id_ganador, id_sub)
    )
    db.execute(
        """INSERT INTO pago (id_subasta, id_comprador, monto, id_estado, fecha_limite)
           VALUES (?, ?, ?, 1, ?)""",
        (id_sub, id_ganador, monto, limite)
    )
    notificar(db, id_ganador,
              f"MSG-06: ¡Ganaste la subasta! Completa tu pago antes de {limite}.",
              "Exito", id_sub)


def verificar_decremento_holandesa(db):
    """RN-09: recalcula precio_actual de holandesas activas según horas transcurridas.
    precio_actual = max(precio_piso, precio_base - decremento_hora * horas)."""
    holandesas = db.execute(
        """SELECT id_subasta, precio_base, precio_piso, decremento_hora,
                  precio_actual, fecha_inicio
           FROM subasta
           WHERE id_estado = 1 AND id_tipo = 2"""
    ).fetchall()
    cambios = False
    for h in holandesas:
        if h["decremento_hora"] is None or h["precio_piso"] is None:
            continue
        inicio = datetime.datetime.strptime(h["fecha_inicio"], "%Y-%m-%d %H:%M:%S")
        horas = int((datetime.datetime.utcnow() - inicio).total_seconds() // 3600)
        if horas < 0:
            horas = 0
        nuevo = max(h["precio_piso"], h["precio_base"] - h["decremento_hora"] * horas)
        if nuevo != h["precio_actual"]:
            db.execute("UPDATE subasta SET precio_actual=? WHERE id_subasta=?",
                       (nuevo, h["id_subasta"]))
            cambios = True
    if cambios:
        db.commit()


def verificar_cierre_subastas(db):
    """RN-13: cierra subastas cuya fecha_fin ya pasó. Desempate: monto DESC, fecha_oferta ASC."""
    vencidas = db.execute(
        """SELECT s.id_subasta, a.id_tipo AS tipo_art, a.id_vendedor
           FROM subasta s
           JOIN articulo a ON a.id_articulo = s.id_articulo
           WHERE s.id_estado = 1 AND s.fecha_fin <= ?""",
        (now_str(),)
    ).fetchall()
    for s in vencidas:
        ganador = db.execute(
            """SELECT id_comprador, monto FROM oferta
               WHERE id_subasta = ?
               ORDER BY monto DESC, fecha_oferta ASC
               LIMIT 1""",
            (s["id_subasta"],)
        ).fetchone()
        if ganador:
            cerrar_subasta_con_ganador(
                db, s["id_subasta"], ganador["id_comprador"],
                ganador["monto"], s["tipo_art"]
            )
        else:
            db.execute("UPDATE subasta SET id_estado=3 WHERE id_subasta=?",
                       (s["id_subasta"],))
            notificar(db, s["id_vendedor"],
                      "MSG-13: Tu subasta venció sin ofertas y fue declarada desierta.",
                      "Info", s["id_subasta"])
    if vencidas:
        db.commit()


# ── Rutas principales ──────────────────────────────────────────────────────────
@app.route("/")
def index():
    db = get_db()
    verificar_decremento_holandesa(db)
    verificar_cierre_subastas(db)
    verificar_aprobacion_automatica(db)
    verificar_pagos_vencidos(db)
    subastas = db.execute(
        """SELECT s.id_subasta, a.titulo, a.ubicacion, s.precio_actual,
                  s.fecha_fin, t.tipo as tipo_subasta, a.imagen_path,
                  u.nombre as vendedor, u.reputacion
           FROM subasta s
           JOIN articulo a ON a.id_articulo = s.id_articulo
           JOIN cat_tipo_subasta t ON t.id = s.id_tipo
           JOIN usuario u ON u.id_usuario = a.id_vendedor
           WHERE s.id_estado = 1
           ORDER BY s.fecha_fin ASC"""
    ).fetchall()
    db.close()
    return render_template("index.html", subastas=subastas)


# ── Autenticación ──────────────────────────────────────────────────────────────
@app.route("/registro", methods=["GET", "POST"])
def registro():
    """CU-C01: Registrarse en la plataforma"""
    if request.method == "POST":
        nombre = request.form["nombre"].strip()
        correo = request.form["correo"].strip().lower()
        pwd    = request.form["password"]
        terminos = request.form.get("terminos")
        if not terminos:
            flash("Debes aceptar los términos y condiciones.", "danger")
            return render_template("registro.html")
        if len(pwd) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.", "danger")
            return render_template("registro.html")
        db = get_db()
        existente = db.execute("SELECT id_usuario FROM usuario WHERE correo=?", (correo,)).fetchone()
        if existente:
            flash("El correo ya está registrado. Intenta iniciar sesión.", "warning")
            db.close()
            return render_template("registro.html")
        # RN-26: rechazar correos en lista negra
        en_lista = db.execute("SELECT id_lista FROM lista_negra WHERE correo=?", (correo,)).fetchone()
        if en_lista:
            flash("ERR-12: Este correo no puede registrarse. Contacta al soporte.", "danger")
            db.close()
            return render_template("registro.html")
        db.execute(
            "INSERT INTO usuario (nombre,correo,password_hash,id_tipo,terminos_ok) VALUES(?,?,?,2,1)",
            (nombre, correo, generate_password_hash(pwd))
        )
        db.commit()
        db.close()
        flash("MSG-01: Cuenta creada exitosamente. ¡Bienvenido/a!", "success")
        return redirect(url_for("login"))
    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """CU-A01 / CU-C02: Iniciar sesión"""
    if request.method == "POST":
        correo = request.form["correo"].strip().lower()
        pwd    = request.form["password"]
        db     = get_db()
        user   = db.execute(
            "SELECT * FROM usuario WHERE correo=?", (correo,)
        ).fetchone()
        db.close()
        if not user or not check_password_hash(user["password_hash"], pwd):
            flash("ERR-01: Credenciales incorrectas. Verifique sus datos.", "danger")
            return render_template("login.html")
        if user["id_estado"] != 1:
            flash("ERR-07: Su cuenta no está activa. Contacte al soporte.", "danger")
            return render_template("login.html")
        session["user_id"]     = user["id_usuario"]
        session["user_nombre"] = user["nombre"]
        session["user_tipo"]   = user["id_tipo"]
        flash("MSG-02: Ha iniciado sesión correctamente.", "success")
        if user["id_tipo"] == 1:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("index"))


# ── Panel Administrador ────────────────────────────────────────────────────────
@app.route("/admin")
@admin_required
def admin_dashboard():
    """CU-A01: Panel principal del administrador"""
    db = get_db()
    verificar_decremento_holandesa(db)
    verificar_cierre_subastas(db)
    verificar_aprobacion_automatica(db)
    pendientes = db.execute(
        """SELECT a.id_articulo, a.titulo, t.tipo as tipo_art,
                  a.fecha_registro, v.fecha_limite, v.id_validacion
           FROM articulo a
           JOIN cat_tipo_articulo t ON t.id = a.id_tipo
           LEFT JOIN validacion v ON v.id_articulo = a.id_articulo AND v.decision IS NULL
           WHERE a.id_estado = 1
           ORDER BY a.fecha_registro ASC"""
    ).fetchall()
    subastas_activas = db.execute(
        """SELECT s.id_subasta, a.titulo, s.fecha_fin, s.precio_actual,
                  e.estado, s.id_estado
           FROM subasta s
           JOIN articulo a ON a.id_articulo = s.id_articulo
           JOIN cat_estado_subasta e ON e.id = s.id_estado
           ORDER BY s.fecha_fin ASC"""
    ).fetchall()
    usuarios = db.execute(
        """SELECT u.id_usuario, u.nombre, u.correo, t.tipo, e.estado, u.reputacion
           FROM usuario u
           JOIN cat_tipo_usuario t ON t.id = u.id_tipo
           JOIN cat_estado_cuenta e ON e.id = u.id_estado
           ORDER BY u.fecha_registro DESC"""
    ).fetchall()
    db.close()
    return render_template("admin_dashboard.html",
                           pendientes=pendientes,
                           subastas=subastas_activas,
                           usuarios=usuarios)


MESES_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


@app.route("/admin/reportes")
@admin_required
def admin_reportes():
    """CU-A08: Reportes mensuales del administrador."""
    db = get_db()
    hoy = datetime.datetime.utcnow()
    try:
        anio = int(request.args.get("anio", hoy.year))
        mes  = int(request.args.get("mes", hoy.month))
    except ValueError:
        anio, mes = hoy.year, hoy.month
    periodo = f"{anio:04d}-{mes:02d}"

    # 1. Subastas por estado
    filas_sub = db.execute(
        """SELECT e.estado, COUNT(*) AS total
           FROM subasta s JOIN cat_estado_subasta e ON e.id = s.id_estado
           WHERE strftime('%Y-%m', s.fecha_inicio) = ?
           GROUP BY s.id_estado""", (periodo,)).fetchall()
    sub_d = {r["estado"]: r["total"] for r in filas_sub}
    subastas = {e: sub_d.get(e, 0) for e in ["Activa", "Finalizada", "Desierta", "Cancelada"]}

    # 2. Validaciones realizadas
    filas_val = db.execute(
        """SELECT decision, COUNT(*) AS total
           FROM validacion
           WHERE decision IS NOT NULL AND strftime('%Y-%m', fecha_decision) = ?
           GROUP BY decision""", (periodo,)).fetchall()
    val_d = {r["decision"]: r["total"] for r in filas_val}
    validaciones = {
        "Aprobado":   val_d.get("Aprobado", 0),
        "Rechazado":  val_d.get("Rechazado", 0),
        "Automatico": val_d.get("Automatico", 0),
    }

    # 3. Pagos / transacciones
    filas_pago = db.execute(
        """SELECT id_estado, COUNT(*) AS total, COALESCE(SUM(monto),0) AS suma
           FROM pago
           WHERE strftime('%Y-%m', fecha_limite) = ?
           GROUP BY id_estado""", (periodo,)).fetchall()
    pago_d = {r["id_estado"]: r for r in filas_pago}
    def pc(*ids): return sum(pago_d[i]["total"] for i in ids if i in pago_d)
    pagos = {
        "completados": pc(3),
        "pendientes":  pc(1, 2),
        "vencidos":    pc(4),
        "monto_transado": pago_d[3]["suma"] if 3 in pago_d else 0,
    }

    anios = list(range(hoy.year - 2, hoy.year + 1))
    db.close()
    return render_template("admin_reportes.html",
                           subastas=subastas, validaciones=validaciones, pagos=pagos,
                           anio=anio, mes=mes, nombre_mes=MESES_ES[mes],
                           meses=MESES_ES, anios=anios)


@app.route("/admin/validar/<int:id_art>", methods=["GET", "POST"])
@admin_required
def admin_validar(id_art):
    """CU-A02/A03/A04/A05: Validar artículo"""
    db = get_db()
    articulo = db.execute(
        """SELECT a.*, t.tipo as tipo_art, c.condicion,
                  u.nombre as vendedor_nombre,
                  v.id_validacion, v.fecha_limite
           FROM articulo a
           JOIN cat_tipo_articulo t ON t.id = a.id_tipo
           JOIN cat_condicion_articulo c ON c.id = a.id_condicion
           JOIN usuario u ON u.id_usuario = a.id_vendedor
           LEFT JOIN validacion v ON v.id_articulo=a.id_articulo AND v.decision IS NULL
           WHERE a.id_articulo=?""",
        (id_art,)
    ).fetchone()
    vehiculo = db.execute("SELECT * FROM vehiculo WHERE id_articulo=?", (id_art,)).fetchone()
    inmueble = db.execute("SELECT * FROM inmueble WHERE id_articulo=?", (id_art,)).fetchone()
    if request.method == "POST":
        accion    = request.form["accion"]       # Aprobar | Rechazar | Extender
        comentario = request.form.get("comentario", "")
        if accion == "Extender":
            nueva_limite = (datetime.datetime.utcnow() +
                            datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
            db.execute("UPDATE validacion SET fecha_limite=?, extendida=1 WHERE id_validacion=?",
                       (nueva_limite, articulo["id_validacion"]))
            db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
                       (session["user_id"], "ExtenderValidacion", f"Artículo {id_art}"))
            db.commit()
            flash("Plazo de validación extendido 30 minutos más.", "success")
        elif accion == "Aprobar":
            db.execute("UPDATE articulo SET id_estado=2 WHERE id_articulo=?", (id_art,))
            db.execute(
                "UPDATE validacion SET decision='Aprobado',id_admin=?,comentario=?,fecha_decision=? WHERE id_validacion=?",
                (session["user_id"], comentario, now_str(), articulo["id_validacion"])
            )
            notificar(db, articulo["id_vendedor"],
                      f"Tu artículo '{articulo['titulo']}' fue aprobado.", "Exito", id_art)
            db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
                       (session["user_id"], "AprobarArticulo", f"Artículo {id_art}"))
            db.commit()
            flash("Artículo aprobado correctamente.", "success")
            return redirect(url_for("admin_dashboard"))
        elif accion == "Rechazar":
            if not comentario:
                flash("Debes indicar el motivo del rechazo.", "danger")
            else:
                db.execute("UPDATE articulo SET id_estado=3 WHERE id_articulo=?", (id_art,))
                db.execute(
                    "UPDATE validacion SET decision='Rechazado',id_admin=?,comentario=?,fecha_decision=? WHERE id_validacion=?",
                    (session["user_id"], comentario, now_str(), articulo["id_validacion"])
                )
                notificar(db, articulo["id_vendedor"],
                          f"MSG-08: Tu artículo fue rechazado. Motivo: {comentario}", "Error", id_art)
                db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
                           (session["user_id"], "RechazarArticulo", f"Artículo {id_art}: {comentario}"))
                db.commit()
                flash("Artículo rechazado. El vendedor fue notificado.", "warning")
                return redirect(url_for("admin_dashboard"))
        db.close()
        return redirect(url_for("admin_validar", id_art=id_art))
    db.close()
    return render_template("admin_validar.html",
                           articulo=articulo, vehiculo=vehiculo, inmueble=inmueble)


@app.route("/admin/cancelar_subasta/<int:id_sub>", methods=["POST"])
@admin_required
def admin_cancelar_subasta(id_sub):
    """CU-A06: Cancelar subasta activa por política"""
    motivo = request.form.get("motivo", "").strip()
    if not motivo:
        flash("Debes indicar el motivo de cancelación.", "danger")
        return redirect(url_for("admin_dashboard"))
    db = get_db()
    sub = db.execute(
        "SELECT s.*,a.id_vendedor FROM subasta s JOIN articulo a ON a.id_articulo=s.id_articulo WHERE s.id_subasta=?",
        (id_sub,)
    ).fetchone()
    if not sub or sub["id_estado"] != 1:
        flash("La subasta no está activa o no existe.", "warning")
        db.close()
        return redirect(url_for("admin_dashboard"))
    db.execute("UPDATE subasta SET id_estado=4, motivo_cancel=? WHERE id_subasta=?", (motivo, id_sub))
    compradores = db.execute(
        "SELECT DISTINCT id_comprador FROM oferta WHERE id_subasta=?", (id_sub,)
    ).fetchall()
    for comp in compradores:
        notificar(db, comp["id_comprador"],
                  f"MSG-12: La subasta fue cancelada. Motivo: {motivo}", "Info", id_sub)
    notificar(db, sub["id_vendedor"], f"Tu subasta fue cancelada por el administrador. Motivo: {motivo}", "Advertencia", id_sub)
    db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
               (session["user_id"], "CancelarSubasta", f"Subasta {id_sub}: {motivo}"))
    db.commit()
    db.close()
    flash("Subasta cancelada. Participantes notificados.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/usuario/<int:id_usr>", methods=["POST"])
@admin_required
def admin_gestionar_usuario(id_usr):
    """CU-A07: Gestionar usuarios"""
    accion = request.form["accion"]    # Suspender | Cancelar | Reactivar
    db = get_db()
    usuario = db.execute("SELECT * FROM usuario WHERE id_usuario=?", (id_usr,)).fetchone()
    if not usuario:
        flash("Usuario no encontrado.", "danger")
        db.close()
        return redirect(url_for("admin_dashboard"))
    if accion == "Suspender":
        db.execute("UPDATE usuario SET id_estado=2 WHERE id_usuario=?", (id_usr,))
        notificar(db, id_usr, "MSG-11: Tu cuenta ha sido suspendida por incumplimiento de políticas.", "Error")
        db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
                   (session["user_id"], "SuspenderUsuario", f"Usuario {id_usr}"))
        flash(f"Cuenta de {usuario['nombre']} suspendida.", "warning")
    elif accion == "Cancelar":
        db.execute("UPDATE usuario SET id_estado=3 WHERE id_usuario=?", (id_usr,))
        db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
                   (session["user_id"], "CancelarCuenta", f"Usuario {id_usr}"))
        flash(f"Cuenta de {usuario['nombre']} cancelada.", "warning")
    elif accion == "Reactivar":
        db.execute("UPDATE usuario SET id_estado=1 WHERE id_usuario=?", (id_usr,))
        db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
                   (session["user_id"], "ReactivarCuenta", f"Usuario {id_usr}"))
        flash(f"Cuenta de {usuario['nombre']} reactivada.", "success")
    elif accion == "CancelarFraude":
        # RN-26: lista negra + cancelar subastas activas + suspender cuenta
        db.execute("INSERT OR IGNORE INTO lista_negra (correo,motivo) VALUES(?,?)",
                   (usuario["correo"], "Cuenta cancelada por fraude"))
        db.execute("UPDATE usuario SET id_estado=2 WHERE id_usuario=?", (id_usr,))
        # Cancelar todas las subastas activas donde el usuario es vendedor
        activas = db.execute(
            """SELECT s.id_subasta FROM subasta s
               JOIN articulo a ON a.id_articulo = s.id_articulo
               WHERE a.id_vendedor=? AND s.id_estado=1""",
            (id_usr,)
        ).fetchall()
        for s in activas:
            db.execute("UPDATE subasta SET id_estado=4, motivo_cancel=? WHERE id_subasta=?",
                       ("Cancelada por fraude del vendedor (RN-26)", s["id_subasta"]))
            participantes = db.execute(
                "SELECT DISTINCT id_comprador FROM oferta WHERE id_subasta=?", (s["id_subasta"],)
            ).fetchall()
            for p in participantes:
                notificar(db, p["id_comprador"],
                          "MSG-12: La subasta fue cancelada por fraude del vendedor.",
                          "Advertencia", s["id_subasta"])
        db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
                   (session["user_id"], "CancelarFraude",
                    f"Usuario {id_usr} ({usuario['correo']}): {len(activas)} subasta(s) cancelada(s)"))
        notificar(db, id_usr,
                  "MSG-11: Tu cuenta fue suspendida por fraude y tus subastas canceladas.", "Error")
        flash(f"Usuario {usuario['nombre']} marcado por fraude: {len(activas)} subasta(s) cancelada(s) y correo en lista negra.", "warning")
    db.commit()
    db.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/usuario/nuevo", methods=["GET", "POST"])
@admin_required
def admin_nuevo_usuario():
    """Admin: Crear usuario manualmente"""
    db = get_db()
    tipos = db.execute("SELECT * FROM cat_tipo_usuario").fetchall()
    if request.method == "POST":
        nombre  = request.form["nombre"].strip()
        correo  = request.form["correo"].strip().lower()
        pwd     = request.form["password"].strip()
        id_tipo = int(request.form["id_tipo"])
        if not nombre or not correo or not pwd:
            flash("Todos los campos son obligatorios.", "danger")
            db.close()
            return render_template("admin_usuario_form.html", tipos=tipos, usuario=None)
        if len(pwd) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.", "danger")
            db.close()
            return render_template("admin_usuario_form.html", tipos=tipos, usuario=None)
        existente = db.execute("SELECT id_usuario FROM usuario WHERE correo=?", (correo,)).fetchone()
        if existente:
            flash("Ya existe un usuario con ese correo.", "warning")
            db.close()
            return render_template("admin_usuario_form.html", tipos=tipos, usuario=None)
        db.execute(
            "INSERT INTO usuario (nombre,correo,password_hash,id_tipo,id_estado,terminos_ok) VALUES(?,?,?,?,1,1)",
            (nombre, correo, generate_password_hash(pwd), id_tipo)
        )
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
                   (session["user_id"], "CrearUsuario", f"Usuario {new_id} ({correo})"))
        db.commit()
        db.close()
        flash(f"Usuario '{nombre}' creado exitosamente.", "success")
        return redirect(url_for("admin_dashboard"))
    db.close()
    return render_template("admin_usuario_form.html", tipos=tipos, usuario=None)


@app.route("/admin/usuario/<int:id_usr>/editar", methods=["GET", "POST"])
@admin_required
def admin_editar_usuario(id_usr):
    """Admin: Editar datos y credenciales de un usuario"""
    db = get_db()
    usuario = db.execute("SELECT * FROM usuario WHERE id_usuario=?", (id_usr,)).fetchone()
    tipos   = db.execute("SELECT * FROM cat_tipo_usuario").fetchall()
    if not usuario:
        flash("Usuario no encontrado.", "danger")
        db.close()
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        nombre   = request.form["nombre"].strip()
        correo   = request.form["correo"].strip().lower()
        id_tipo  = int(request.form["id_tipo"])
        nueva_pwd = request.form.get("password", "").strip()
        # Validar correo único (excluyendo al propio usuario)
        dup = db.execute(
            "SELECT id_usuario FROM usuario WHERE correo=? AND id_usuario!=?", (correo, id_usr)
        ).fetchone()
        if dup:
            flash("Ese correo ya está en uso por otro usuario.", "warning")
            db.close()
            return render_template("admin_usuario_form.html", tipos=tipos, usuario=usuario)
        if nueva_pwd:
            if len(nueva_pwd) < 8:
                flash("La nueva contraseña debe tener al menos 8 caracteres.", "danger")
                db.close()
                return render_template("admin_usuario_form.html", tipos=tipos, usuario=usuario)
            db.execute(
                "UPDATE usuario SET nombre=?,correo=?,id_tipo=?,password_hash=? WHERE id_usuario=?",
                (nombre, correo, id_tipo, generate_password_hash(nueva_pwd), id_usr)
            )
            detalle = f"Usuario {id_usr}: nombre, correo, tipo y contraseña actualizados"
        else:
            db.execute(
                "UPDATE usuario SET nombre=?,correo=?,id_tipo=? WHERE id_usuario=?",
                (nombre, correo, id_tipo, id_usr)
            )
            detalle = f"Usuario {id_usr}: nombre, correo y tipo actualizados"
        db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
                   (session["user_id"], "EditarUsuario", detalle))
        db.commit()
        db.close()
        flash(f"Usuario '{nombre}' actualizado correctamente.", "success")
        return redirect(url_for("admin_dashboard"))
    db.close()
    return render_template("admin_usuario_form.html", tipos=tipos, usuario=usuario)


@app.route("/admin/usuario/<int:id_usr>/eliminar", methods=["POST"])
@admin_required
def admin_eliminar_usuario(id_usr):
    """Admin: Eliminar usuario (solo si no tiene actividad)"""
    if id_usr == session["user_id"]:
        flash("No puedes eliminar tu propia cuenta.", "danger")
        return redirect(url_for("admin_dashboard"))
    db = get_db()
    usuario = db.execute("SELECT * FROM usuario WHERE id_usuario=?", (id_usr,)).fetchone()
    if not usuario:
        flash("Usuario no encontrado.", "danger")
        db.close()
        return redirect(url_for("admin_dashboard"))
    # Verificar actividad: ofertas, subastas ganadas, artículos
    actividad = db.execute(
        """SELECT
             (SELECT COUNT(*) FROM oferta WHERE id_comprador=?) +
             (SELECT COUNT(*) FROM articulo WHERE id_vendedor=?) +
             (SELECT COUNT(*) FROM subasta WHERE id_ganador=?) AS total""",
        (id_usr, id_usr, id_usr)
    ).fetchone()["total"]
    if actividad > 0:
        flash(f"No se puede eliminar: el usuario tiene {actividad} registro(s) de actividad. Usa Suspender o Cancelar.", "warning")
        db.close()
        return redirect(url_for("admin_dashboard"))
    nombre = usuario["nombre"]
    db.execute("DELETE FROM notificacion WHERE id_usuario=?", (id_usr,))
    db.execute("DELETE FROM calificacion WHERE id_calificador=? OR id_calificado=?", (id_usr, id_usr))
    db.execute("DELETE FROM usuario WHERE id_usuario=?", (id_usr,))
    db.execute("INSERT INTO log_admin (id_admin,accion,detalle) VALUES(?,?,?)",
               (session["user_id"], "EliminarUsuario", f"Usuario {id_usr} ({nombre}) eliminado"))
    db.commit()
    db.close()
    flash(f"Usuario '{nombre}' eliminado permanentemente.", "success")
    return redirect(url_for("admin_dashboard"))


# ── Comprador: Catálogo y detalle ──────────────────────────────────────────────
@app.route("/catalogo")
def catalogo():
    """CU-C03: Consultar catálogo"""
    categoria = request.args.get("categoria", "")
    busqueda  = request.args.get("q", "")
    db = get_db()
    verificar_decremento_holandesa(db)
    verificar_cierre_subastas(db)
    query = """
        SELECT s.id_subasta, a.titulo, a.ubicacion, s.precio_actual,
               s.fecha_fin, t.tipo as tipo_subasta, ta.tipo as tipo_art,
               a.imagen_path, u.nombre as vendedor, u.reputacion
        FROM subasta s
        JOIN articulo a ON a.id_articulo = s.id_articulo
        JOIN cat_tipo_subasta t ON t.id = s.id_tipo
        JOIN cat_tipo_articulo ta ON ta.id = a.id_tipo
        JOIN usuario u ON u.id_usuario = a.id_vendedor
        WHERE s.id_estado = 1
    """
    params = []
    if categoria:
        query += " AND ta.tipo = ?"
        params.append(categoria)
    if busqueda:
        query += " AND (a.titulo LIKE ? OR a.descripcion LIKE ?)"
        params += [f"%{busqueda}%", f"%{busqueda}%"]
    query += " ORDER BY s.fecha_fin ASC"
    subastas = db.execute(query, params).fetchall()
    categorias = db.execute("SELECT tipo FROM cat_tipo_articulo").fetchall()
    db.close()
    return render_template("catalogo.html", subastas=subastas,
                           categorias=categorias, categoria_sel=categoria, busqueda=busqueda)


@app.route("/subasta/<int:id_sub>")
def detalle_subasta(id_sub):
    """CU-C03/C04: Detalle de artículo (RN-10: solo puja actual)"""
    db = get_db()
    verificar_decremento_holandesa(db)
    verificar_cierre_subastas(db)
    subasta = db.execute(
        """SELECT s.*, a.titulo, a.descripcion, a.ubicacion, a.imagen_path,
                  a.id_vendedor, ta.tipo as tipo_art, ts.tipo as tipo_sub,
                  c.condicion, es.estado as estado_sub,
                  u.nombre as vendedor_nombre, u.reputacion,
                  (SELECT COUNT(*) FROM oferta o WHERE o.id_subasta=s.id_subasta) as total_ofertas
           FROM subasta s
           JOIN articulo a ON a.id_articulo = s.id_articulo
           JOIN cat_tipo_articulo ta ON ta.id = a.id_tipo
           JOIN cat_tipo_subasta ts ON ts.id = s.id_tipo
           JOIN cat_condicion_articulo c ON c.id = a.id_condicion
           JOIN cat_estado_subasta es ON es.id = s.id_estado
           JOIN usuario u ON u.id_usuario = a.id_vendedor
           WHERE s.id_subasta=?""",
        (id_sub,)
    ).fetchone()
    if not subasta:
        flash("Subasta no encontrada.", "danger")
        return redirect(url_for("catalogo"))
    vehiculo = db.execute("SELECT * FROM vehiculo WHERE id_articulo=?",
                          (subasta["id_articulo"],)).fetchone()
    inmueble = db.execute("SELECT * FROM inmueble WHERE id_articulo=?",
                          (subasta["id_articulo"],)).fetchone()
    # RN-10: historial solo visible para admin
    historial = None
    if session.get("user_tipo") == 1:
        historial = db.execute(
            """SELECT o.monto, o.fecha_oferta, u.nombre
               FROM oferta o JOIN usuario u ON u.id_usuario=o.id_comprador
               WHERE o.id_subasta=? ORDER BY o.monto DESC""",
            (id_sub,)
        ).fetchall()
    db.close()
    return render_template("detalle_subasta.html",
                           sub=subasta, vehiculo=vehiculo, inmueble=inmueble,
                           historial=historial)


# ── Comprador: Ofertas ─────────────────────────────────────────────────────────
@app.route("/oferta/<int:id_sub>", methods=["POST"])
@login_required
def realizar_oferta(id_sub):
    """CU-C04: Realizar oferta"""
    if session.get("user_tipo") == 1:
        flash("Los administradores no pueden realizar ofertas.", "danger")
        return redirect(url_for("detalle_subasta", id_sub=id_sub))
    db = get_db()
    sub = db.execute("SELECT * FROM subasta WHERE id_subasta=?", (id_sub,)).fetchone()
    if not sub or sub["id_estado"] != 1:
        flash("ERR-03: La subasta ya cerró.", "danger")
        db.close()
        return redirect(url_for("detalle_subasta", id_sub=id_sub))
    # RN-13: rechazar puja aunque el barrido aún no haya corrido
    if sub["fecha_fin"] <= now_str():
        flash("ERR-03: La subasta ya venció por tiempo.", "danger")
        db.close()
        return redirect(url_for("detalle_subasta", id_sub=id_sub))
    # RN-11: verificar pagos pendientes
    pago_pendiente = db.execute(
        "SELECT id_pago FROM pago WHERE id_comprador=? AND id_estado=1", (session["user_id"],)
    ).fetchone()
    if pago_pendiente:
        flash("ERR-10: Completa los pagos pendientes antes de participar en nuevas subastas.", "danger")
        db.close()
        return redirect(url_for("detalle_subasta", id_sub=id_sub))
    try:
        monto = float(request.form["monto"])
    except (ValueError, KeyError):
        flash("Monto inválido.", "danger")
        db.close()
        return redirect(url_for("detalle_subasta", id_sub=id_sub))
    # ── Rama por tipo de subasta ────────────────────────────────────────────
    if sub["id_tipo"] == 2:
        # RN-09 HOLANDESA: aceptar el precio vigente y cerrar de inmediato.
        # El precio se recalcula en el servidor (no se confía en el campo oculto del cliente).
        inicio = datetime.datetime.strptime(sub["fecha_inicio"], "%Y-%m-%d %H:%M:%S")
        horas = max(0, int((datetime.datetime.utcnow() - inicio).total_seconds() // 3600))
        piso = sub["precio_piso"] if sub["precio_piso"] is not None else sub["precio_base"]
        decr = sub["decremento_hora"] if sub["decremento_hora"] is not None else 0
        precio_vigente = max(piso, sub["precio_base"] - decr * horas)
        tipo_art = db.execute("SELECT id_tipo FROM articulo WHERE id_articulo=?",
                              (sub["id_articulo"],)).fetchone()["id_tipo"]
        db.execute(
            "INSERT INTO oferta (id_subasta,id_comprador,monto,es_sellada) VALUES(?,?,?,0)",
            (id_sub, session["user_id"], precio_vigente)
        )
        db.execute("UPDATE subasta SET precio_actual=? WHERE id_subasta=?",
                   (precio_vigente, id_sub))
        cerrar_subasta_con_ganador(db, id_sub, session["user_id"], precio_vigente, tipo_art)
        db.commit()
        db.close()
        flash(f"MSG-06: ¡Aceptaste ${precio_vigente:,.2f} y ganaste la subasta!", "success")
        return redirect(url_for("detalle_subasta", id_sub=id_sub))

    if sub["id_tipo"] == 3:
        # RN-10 SELLADA: oferta privada, una por usuario, sin actualizar precio ni ganador.
        ya = db.execute(
            "SELECT id_oferta FROM oferta WHERE id_subasta=? AND id_comprador=?",
            (id_sub, session["user_id"])
        ).fetchone()
        if ya:
            flash("ERR-11: Ya enviaste tu oferta sellada. Solo se permite una por usuario.", "danger")
            db.close()
            return redirect(url_for("detalle_subasta", id_sub=id_sub))
        if monto < sub["precio_base"]:
            flash(f"ERR-02: La oferta debe ser al menos ${sub['precio_base']:,.2f}.", "danger")
            db.close()
            return redirect(url_for("detalle_subasta", id_sub=id_sub))
        db.execute(
            "INSERT INTO oferta (id_subasta,id_comprador,monto,es_sellada) VALUES(?,?,?,1)",
            (id_sub, session["user_id"], monto)
        )
        notificar(db, session["user_id"],
                  f"MSG-03: Tu oferta sellada de ${monto:,.2f} fue registrada. Se revelará al cierre.",
                  "Exito", id_sub)
        db.commit()
        db.close()
        flash("MSG-03: Tu oferta privada fue registrada.", "success")
        return redirect(url_for("detalle_subasta", id_sub=id_sub))

    # RN-08 INGLESA (id_tipo=1): incremento mínimo y puja ascendente.
    minimo_requerido = sub["precio_actual"] + sub["incremento_min"]
    if monto < minimo_requerido:
        flash(f"ERR-02: La oferta debe ser al menos ${minimo_requerido:,.2f}.", "danger")
        db.close()
        return redirect(url_for("detalle_subasta", id_sub=id_sub))
    db.execute(
        "INSERT INTO oferta (id_subasta,id_comprador,monto,es_sellada) VALUES(?,?,?,0)",
        (id_sub, session["user_id"], monto)
    )
    db.execute("UPDATE subasta SET precio_actual=?, id_ganador=? WHERE id_subasta=?",
               (monto, session["user_id"], id_sub))
    notificar(db, session["user_id"],
              f"MSG-03: Tu oferta de ${monto:,.2f} fue registrada. Eres el mejor postor.",
              "Exito", id_sub)
    # Notificar a postores anteriores
    anteriores = db.execute(
        "SELECT DISTINCT id_comprador FROM oferta WHERE id_subasta=? AND id_comprador!=?",
        (id_sub, session["user_id"])
    ).fetchall()
    for ant in anteriores:
        notificar(db, ant["id_comprador"],
                  "MSG-04: Tu oferta fue superada. Realiza una nueva para continuar.",
                  "Advertencia", id_sub)
    db.commit()
    db.close()
    flash(f"MSG-03: ¡Oferta de ${monto:,.2f} registrada! Eres el mejor postor.", "success")
    return redirect(url_for("detalle_subasta", id_sub=id_sub))


# ── Comprador: Pagos ───────────────────────────────────────────────────────────
@app.route("/pago/<int:id_sub>", methods=["GET", "POST"])
@login_required
def realizar_pago(id_sub):
    """CU-C06: Realizar pago"""
    db = get_db()
    sub = db.execute(
        """SELECT s.*, a.titulo, a.id_tipo as tipo_art
           FROM subasta s JOIN articulo a ON a.id_articulo=s.id_articulo
           WHERE s.id_subasta=? AND s.id_ganador=?""",
        (id_sub, session["user_id"])
    ).fetchone()
    if not sub:
        flash("No tienes una subasta ganada con ese ID.", "warning")
        db.close()
        return redirect(url_for("mi_historial"))
    pago = db.execute(
        "SELECT * FROM pago WHERE id_subasta=? AND id_comprador=? AND id_estado!=4",
        (id_sub, session["user_id"])
    ).fetchone()
    if request.method == "POST":
        # RN-14/15/16: la fila pago fue creada al cerrar la subasta (cerrar_subasta_con_ganador)
        if not pago:
            flash("No se encontró el registro de pago. Contacta al administrador.", "danger")
            db.close()
            return redirect(url_for("mi_historial"))
        pago_id = pago["id_pago"]
        comprobante = request.files.get("comprobante")
        if comprobante and comprobante.filename:
            if not allowed_file(comprobante.filename):
                flash("ERR-04: Solo se aceptan JPG, PNG o PDF (máx 5 MB).", "danger")
                db.close()
                return redirect(url_for("realizar_pago", id_sub=id_sub))
            fname = secure_filename(f"comp_{pago_id}_{comprobante.filename}")
            comprobante.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
            db.execute(
                "UPDATE pago SET comprobante=?, id_estado=2, fecha_pago=? WHERE id_pago=?",
                (fname, now_str(), pago_id)
            )
            # RN-27: si eligió plazos y aplica, crear las cuotas
            plan = request.form.get("plan", "completo")
            if plan in ("3", "6", "12") and pago["monto"] > 10000 and sub["tipo_art"] != 3:
                ya = db.execute("SELECT COUNT(*) c FROM plan_pago WHERE id_pago=?", (pago_id,)).fetchone()["c"]
                if not ya:
                    n = int(plan)
                    base = round(pago["monto"] / n, 2)
                    for i in range(1, n + 1):
                        venc = add_months(datetime.datetime.utcnow(), i).strftime("%Y-%m-%d %H:%M:%S")
                        cuota_monto = base if i < n else round(pago["monto"] - base * (n - 1), 2)
                        db.execute(
                            "INSERT INTO plan_pago (id_pago,num_cuota,monto_cuota,fecha_vencimiento,id_estado) VALUES(?,?,?,?,1)",
                            (pago_id, i, cuota_monto, venc)
                        )
            # Notificar al vendedor
            sub_full = db.execute(
                "SELECT a.id_vendedor FROM subasta s JOIN articulo a ON a.id_articulo=s.id_articulo WHERE s.id_subasta=?",
                (id_sub,)
            ).fetchone()
            notificar(db, sub_full["id_vendedor"],
                      "MSG-09: Hay un comprobante de pago pendiente de verificación.", "Info", id_sub)
            notificar(db, session["user_id"],
                      "MSG-09: Tu pago fue recibido y está siendo verificado.", "Info", id_sub)
            db.commit()
            db.close()
            flash("MSG-09: Comprobante enviado. En verificación por el vendedor.", "success")
            return redirect(url_for("mi_historial"))
        else:
            flash("Debes adjuntar el comprobante de pago.", "danger")
    monto_pago = pago["monto"] if pago else sub["precio_actual"]
    aplica_plazos = monto_pago > 10000 and sub["tipo_art"] != 3
    opciones = [{"n": n, "cuota": round(monto_pago / n, 2)} for n in (3, 6, 12)] if aplica_plazos else []
    cuotas = []
    if pago:
        cuotas = db.execute(
            "SELECT num_cuota, monto_cuota, fecha_vencimiento, id_estado FROM plan_pago WHERE id_pago=? ORDER BY num_cuota",
            (pago["id_pago"],)
        ).fetchall()
    db.close()
    return render_template("realizar_pago.html", sub=sub, pago=pago,
                           monto_pago=monto_pago, aplica_plazos=aplica_plazos,
                           opciones=opciones, cuotas=cuotas)


# ── Comprador: Confirmar recepción y calificar ─────────────────────────────────
IMG_EXT = {"png", "jpg", "jpeg"}


@app.route("/confirmar_recepcion/<int:id_sub>", methods=["GET", "POST"])
@login_required
def confirmar_recepcion(id_sub):
    """CU-C07: Confirmar recepción con evidencia fotográfica y calificar vendedor."""
    db = get_db()
    info = db.execute(
        """SELECT s.id_subasta, a.titulo, a.id_vendedor, u.nombre AS vendedor,
                  p.id_pago, p.monto
           FROM subasta s
           JOIN articulo a ON a.id_articulo = s.id_articulo
           JOIN usuario u ON u.id_usuario = a.id_vendedor
           LEFT JOIN pago p ON p.id_subasta = s.id_subasta AND p.id_comprador = ?
           WHERE s.id_subasta = ? AND s.id_ganador = ?""",
        (session["user_id"], id_sub, session["user_id"])
    ).fetchone()
    if not info or info["id_pago"] is None:
        flash("No tienes una recepción pendiente para esa subasta.", "warning")
        db.close()
        return redirect(url_for("mi_historial"))

    if request.method == "POST":
        try:
            puntuacion = int(request.form.get("puntuacion", 0))
        except ValueError:
            puntuacion = 0
        comentario = request.form.get("comentario_cal", "")
        if puntuacion < 1 or puntuacion > 5:
            flash("La calificación debe ser entre 1 y 5.", "danger")
            db.close()
            return redirect(url_for("confirmar_recepcion", id_sub=id_sub))

        imagenes = [f for f in request.files.getlist("imagenes") if f and f.filename]
        # AC-21: al menos una imagen
        if not imagenes:
            flash("ERR-13: Debes adjuntar al menos una imagen como evidencia de recepción.", "danger")
            db.close()
            return redirect(url_for("confirmar_recepcion", id_sub=id_sub))
        # AC-23 + tamaño: validar TODO antes de guardar nada
        for f in imagenes:
            ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
            if ext not in IMG_EXT:
                flash(f"ERR-04: '{f.filename}' tiene una extensión no permitida (solo JPG/PNG).", "danger")
                db.close()
                return redirect(url_for("confirmar_recepcion", id_sub=id_sub))
            f.seek(0, os.SEEK_END); size = f.tell(); f.seek(0)
            if size > 5 * 1024 * 1024:
                flash(f"ERR-04: '{f.filename}' supera el máximo de 5 MB.", "danger")
                db.close()
                return redirect(url_for("confirmar_recepcion", id_sub=id_sub))

        # Guardar imágenes y registrar rutas
        carpeta = os.path.join(app.root_path, "static", "uploads", "recepciones")
        os.makedirs(carpeta, exist_ok=True)
        for n, f in enumerate(imagenes, 1):
            ext = f.filename.rsplit(".", 1)[-1].lower()
            fname = secure_filename(f"recepcion_{info['id_pago']}_{n}.{ext}")
            f.save(os.path.join(carpeta, fname))
            ruta = f"uploads/recepciones/{fname}"  # relativa a /static
            db.execute("INSERT INTO imagen_recepcion (id_pago, ruta) VALUES (?, ?)",
                       (info["id_pago"], ruta))

        # Confirmar recepción + calificación
        db.execute("UPDATE subasta SET id_estado=2 WHERE id_subasta=?", (id_sub,))
        db.execute(
            "INSERT INTO calificacion (id_subasta,id_calificador,id_calificado,puntuacion,comentario) VALUES(?,?,?,?,?)",
            (id_sub, session["user_id"], info["id_vendedor"], puntuacion, comentario)
        )
        stats = db.execute(
            "SELECT AVG(puntuacion) AS avg, COUNT(*) AS cnt FROM calificacion WHERE id_calificado=?",
            (info["id_vendedor"],)
        ).fetchone()
        db.execute("UPDATE usuario SET reputacion=?, total_cal=? WHERE id_usuario=?",
                   (round(stats["avg"], 2), stats["cnt"], info["id_vendedor"]))
        notificar(db, session["user_id"], "MSG-14: Entrega confirmada exitosamente.", "Exito", id_sub)
        db.commit()
        db.close()
        flash("MSG-14: Entrega confirmada con evidencia y vendedor calificado.", "success")
        return redirect(url_for("mi_historial"))

    db.close()
    return render_template("confirmar_recepcion.html", info=info)


# ── Comprador: Historial ───────────────────────────────────────────────────────
@app.route("/mi_historial")
@login_required
def mi_historial():
    """CU-C08: Historial personal"""
    db = get_db()
    ofertas = db.execute(
        """SELECT o.monto, o.fecha_oferta, a.titulo, s.id_subasta,
                  s.precio_actual, es.estado
           FROM oferta o
           JOIN subasta s ON s.id_subasta = o.id_subasta
           JOIN articulo a ON a.id_articulo = s.id_articulo
           JOIN cat_estado_subasta es ON es.id = s.id_estado
           WHERE o.id_comprador=?
           ORDER BY o.fecha_oferta DESC""",
        (session["user_id"],)
    ).fetchall()
    pagos = db.execute(
        """SELECT p.*, a.titulo, s.precio_actual, ep.estado as estado_pago
           FROM pago p
           JOIN subasta s ON s.id_subasta = p.id_subasta
           JOIN articulo a ON a.id_articulo = s.id_articulo
           JOIN cat_estado_pago ep ON ep.id = p.id_estado
           WHERE p.id_comprador=?
           ORDER BY p.fecha_limite DESC""",
        (session["user_id"],)
    ).fetchall()
    ganadas = db.execute(
        """SELECT s.id_subasta, a.titulo, s.precio_actual, s.fecha_fin,
                  es.estado, p.id_estado as id_estado_pago, ep.estado as estado_pago,
                  (SELECT COUNT(*) FROM calificacion c
                   WHERE c.id_subasta=s.id_subasta AND c.id_calificador=?) as ya_califiqu
           FROM subasta s
           JOIN articulo a ON a.id_articulo = s.id_articulo
           JOIN cat_estado_subasta es ON es.id = s.id_estado
           LEFT JOIN pago p ON p.id_subasta=s.id_subasta AND p.id_comprador=?
           LEFT JOIN cat_estado_pago ep ON ep.id=p.id_estado
           WHERE s.id_ganador=?
           ORDER BY s.fecha_fin DESC""",
        (session["user_id"], session["user_id"], session["user_id"])
    ).fetchall()
    # AC-24: imágenes de recepción accesibles desde el historial
    imgs = db.execute(
        """SELECT ir.ruta, p.id_subasta
           FROM imagen_recepcion ir
           JOIN pago p ON p.id_pago = ir.id_pago
           WHERE p.id_comprador = ?""",
        (session["user_id"],)
    ).fetchall()
    imagenes_recepcion = {}
    for r in imgs:
        imagenes_recepcion.setdefault(r["id_subasta"], []).append(r["ruta"])
    # RN-27: planes de pago a plazos (cuotas pagadas / total) por subasta
    planes = db.execute(
        """SELECT p.id_subasta, COUNT(pp.id_plan) AS total,
                  SUM(CASE WHEN pp.id_estado=3 THEN 1 ELSE 0 END) AS pagadas
           FROM plan_pago pp JOIN pago p ON p.id_pago = pp.id_pago
           WHERE p.id_comprador=?
           GROUP BY p.id_subasta""",
        (session["user_id"],)
    ).fetchall()
    planes_dict = {r["id_subasta"]: (r["pagadas"] or 0, r["total"]) for r in planes}
    db.close()
    return render_template("mi_historial.html",
                           ofertas=ofertas, pagos=pagos, ganadas=ganadas,
                           imagenes_recepcion=imagenes_recepcion, planes=planes_dict)


# ── Notificaciones ─────────────────────────────────────────────────────────────
@app.route("/notificaciones")
@login_required
def notificaciones():
    """CU-C05: Ver notificaciones"""
    db = get_db()
    notifs = db.execute(
        "SELECT * FROM notificacion WHERE id_usuario=? ORDER BY fecha DESC",
        (session["user_id"],)
    ).fetchall()
    db.execute("UPDATE notificacion SET leida=1 WHERE id_usuario=?", (session["user_id"],))
    db.commit()
    db.close()
    return render_template("notificaciones.html", notifs=notifs)


@app.route("/api/notificaciones_count")
@login_required
def notificaciones_count():
    db = get_db()
    cnt = db.execute(
        "SELECT COUNT(*) FROM notificacion WHERE id_usuario=? AND leida=0",
        (session["user_id"],)
    ).fetchone()[0]
    db.close()
    return jsonify({"count": cnt})


# ── Vendedor: publicar artículo (necesario para el flujo completo) ─────────────
@app.route("/publicar", methods=["GET", "POST"])
@login_required
def publicar_articulo():
    if session.get("user_tipo") == 1:
        flash("El administrador no puede publicar artículos.", "warning")
        return redirect(url_for("index"))
    db = get_db()
    tipos = db.execute("SELECT * FROM cat_tipo_articulo").fetchall()
    condiciones = db.execute("SELECT * FROM cat_condicion_articulo").fetchall()
    tipos_sub = db.execute("SELECT * FROM cat_tipo_subasta").fetchall()
    if request.method == "POST":
        titulo      = request.form["titulo"].strip()
        descripcion = request.form["descripcion"].strip()
        id_tipo     = int(request.form["id_tipo"])
        id_cond     = int(request.form["id_condicion"])
        ubicacion   = request.form.get("ubicacion", "")
        tipo_sub    = int(request.form["tipo_subasta"])
        precio_base = float(request.form["precio_base"])
        incr        = float(request.form.get("incremento", 1))
        dias        = int(request.form.get("dias_subasta", 3))
        # Validar duración según tipo (RN-22/23/24)
        limites = {1: (1,7), 2: (3,14), 3: (7,30)}
        lim = limites.get(id_tipo, (1,7))
        if not (lim[0] <= dias <= lim[1]):
            flash(f"La duración debe ser entre {lim[0]} y {lim[1]} días para ese tipo.", "danger")
            db.close()
            return render_template("publicar.html", tipos=tipos, condiciones=condiciones, tipos_sub=tipos_sub)
        db.execute(
            "INSERT INTO articulo (titulo,descripcion,id_tipo,id_condicion,ubicacion,id_vendedor) VALUES(?,?,?,?,?,?)",
            (titulo, descripcion, id_tipo, id_cond, ubicacion, session["user_id"])
        )
        id_art = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        if id_tipo == 2:  # Vehículo
            db.execute("INSERT INTO vehiculo (id_articulo,marca,modelo,anio,kilometraje,num_serie) VALUES(?,?,?,?,?,?)",
                       (id_art, request.form.get("marca",""), request.form.get("modelo",""),
                        request.form.get("anio",0), request.form.get("km",0), request.form.get("num_serie","")))
        elif id_tipo == 3:  # Inmueble
            db.execute("INSERT INTO inmueble (id_articulo,tipo_propiedad,superficie_terreno,superficie_construida,num_habitaciones,ubicacion_detallada) VALUES(?,?,?,?,?,?)",
                       (id_art, request.form.get("tipo_prop",""), request.form.get("sup_t",0),
                        request.form.get("sup_c",0), request.form.get("hab",0), request.form.get("ubic_det","")))
        # Crear validacion
        limite_val = (datetime.datetime.utcnow() +
                      datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute("INSERT INTO validacion (id_articulo,fecha_limite) VALUES(?,?)",
                   (id_art, limite_val))
        # Pre-crear subasta en estado "en espera" si es aprobado
        fecha_inicio = now_str()
        fecha_fin = (datetime.datetime.utcnow() +
                     datetime.timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
        if tipo_sub == 2:  # Holandesa: guardar piso y decremento por hora (RN-09)
            precio_piso     = float(request.form.get("precio_piso", precio_base))
            decremento_hora = float(request.form.get("decremento_hora", 0))
            db.execute(
                """INSERT INTO subasta (id_articulo,id_tipo,precio_base,precio_actual,incremento_min,precio_piso,decremento_hora,fecha_inicio,fecha_fin,id_estado)
                   VALUES(?,?,?,?,?,?,?,?,?,1)""",
                (id_art, tipo_sub, precio_base, precio_base, incr, precio_piso, decremento_hora, fecha_inicio, fecha_fin)
            )
        else:
            db.execute(
                """INSERT INTO subasta (id_articulo,id_tipo,precio_base,precio_actual,incremento_min,fecha_inicio,fecha_fin,id_estado)
                   VALUES(?,?,?,?,?,?,?,1)""",
                (id_art, tipo_sub, precio_base, precio_base, incr, fecha_inicio, fecha_fin)
            )
        db.commit()
        db.close()
        flash("Artículo enviado a validación. El administrador lo revisará en breve.", "success")
        return redirect(url_for("index"))
    db.close()
    return render_template("publicar.html", tipos=tipos, condiciones=condiciones, tipos_sub=tipos_sub)


if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    init_db()
    seed_demo()
    print("="*50)
    print(" Sistema de Gestión de Subastas")
    print(" http://127.0.0.1:5000")
    print(" Admin: admin@subasta.mx / Admin1234")
    print(" Comprador: ana@mail.mx / Ana12345")
    print("="*50)
    app.run(debug=True)
