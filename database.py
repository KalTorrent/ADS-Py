"""
database.py - Esquema y creacion de la base de datos (SQLite, 3FN)
Sistema de Gestion de Subastas
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "subasta.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    # ── Catalogos (3FN) ────────────────────────────────────────────────────────
    c.executescript("""
    CREATE TABLE IF NOT EXISTS cat_tipo_usuario (
        id   INTEGER PRIMARY KEY,
        tipo TEXT NOT NULL UNIQUE   -- Administrador, Comprador, Vendedor
    );
    INSERT OR IGNORE INTO cat_tipo_usuario VALUES (1,'Administrador'),(2,'Comprador'),(3,'Vendedor');

    CREATE TABLE IF NOT EXISTS cat_tipo_articulo (
        id   INTEGER PRIMARY KEY,
        tipo TEXT NOT NULL UNIQUE   -- General, Vehiculo, Inmueble, Digital, Entrada
    );
    INSERT OR IGNORE INTO cat_tipo_articulo VALUES (1,'General'),(2,'Vehiculo'),(3,'Inmueble'),(4,'Digital'),(5,'Entrada');

    CREATE TABLE IF NOT EXISTS cat_tipo_subasta (
        id   INTEGER PRIMARY KEY,
        tipo TEXT NOT NULL UNIQUE   -- Inglesa, Holandesa, Sellada
    );
    INSERT OR IGNORE INTO cat_tipo_subasta VALUES (1,'Inglesa'),(2,'Holandesa'),(3,'Sellada');

    CREATE TABLE IF NOT EXISTS cat_estado_articulo (
        id     INTEGER PRIMARY KEY,
        estado TEXT NOT NULL UNIQUE  -- Pendiente, Aprobado, Rechazado, Publicado
    );
    INSERT OR IGNORE INTO cat_estado_articulo VALUES
        (1,'Pendiente'),(2,'Aprobado'),(3,'Rechazado'),(4,'Publicado');

    CREATE TABLE IF NOT EXISTS cat_estado_subasta (
        id     INTEGER PRIMARY KEY,
        estado TEXT NOT NULL UNIQUE
    );
    INSERT OR IGNORE INTO cat_estado_subasta VALUES
        (1,'Activa'),(2,'Finalizada'),(3,'Desierta'),(4,'Cancelada');

    CREATE TABLE IF NOT EXISTS cat_estado_cuenta (
        id     INTEGER PRIMARY KEY,
        estado TEXT NOT NULL UNIQUE
    );
    INSERT OR IGNORE INTO cat_estado_cuenta VALUES (1,'Activa'),(2,'Suspendida'),(3,'Cancelada');

    CREATE TABLE IF NOT EXISTS cat_estado_pago (
        id     INTEGER PRIMARY KEY,
        estado TEXT NOT NULL UNIQUE
    );
    INSERT OR IGNORE INTO cat_estado_pago VALUES
        (1,'Pendiente'),(2,'EnVerificacion'),(3,'Verificado'),(4,'Vencido'),(5,'Reasignado');

    CREATE TABLE IF NOT EXISTS cat_condicion_articulo (
        id        INTEGER PRIMARY KEY,
        condicion TEXT NOT NULL UNIQUE
    );
    INSERT OR IGNORE INTO cat_condicion_articulo VALUES (1,'Nuevo'),(2,'Usado'),(3,'Reacondicionado');
    """)

    # ── Entidades principales ──────────────────────────────────────────────────
    c.executescript("""
    -- AC-USR: Usuarios (Administrador, Comprador, Vendedor)
    CREATE TABLE IF NOT EXISTS usuario (
        id_usuario      INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre          TEXT    NOT NULL,
        correo          TEXT    NOT NULL UNIQUE,
        password_hash   TEXT    NOT NULL,
        id_tipo         INTEGER NOT NULL REFERENCES cat_tipo_usuario(id),
        id_estado       INTEGER NOT NULL DEFAULT 1 REFERENCES cat_estado_cuenta(id),
        reputacion      REAL    NOT NULL DEFAULT 0,
        total_cal       INTEGER NOT NULL DEFAULT 0,
        fecha_registro  TEXT    NOT NULL DEFAULT (datetime('now')),
        terminos_ok     INTEGER NOT NULL DEFAULT 0
    );

    -- AC-ART: Articulos publicados
    CREATE TABLE IF NOT EXISTS articulo (
        id_articulo     INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo          TEXT    NOT NULL,
        descripcion     TEXT    NOT NULL,
        id_tipo         INTEGER NOT NULL REFERENCES cat_tipo_articulo(id),
        id_condicion    INTEGER NOT NULL REFERENCES cat_condicion_articulo(id),
        ubicacion       TEXT,
        id_vendedor     INTEGER NOT NULL REFERENCES usuario(id_usuario),
        id_estado       INTEGER NOT NULL DEFAULT 1 REFERENCES cat_estado_articulo(id),
        fecha_registro  TEXT    NOT NULL DEFAULT (datetime('now')),
        imagen_path     TEXT
    );

    -- AC-VEH: Extension para vehiculos
    CREATE TABLE IF NOT EXISTS vehiculo (
        id_articulo     INTEGER PRIMARY KEY REFERENCES articulo(id_articulo),
        marca           TEXT,
        modelo          TEXT,
        anio            INTEGER,
        kilometraje     INTEGER,
        num_serie       TEXT,
        doc_path        TEXT
    );

    -- AC-INM: Extension para inmuebles
    CREATE TABLE IF NOT EXISTS inmueble (
        id_articulo         INTEGER PRIMARY KEY REFERENCES articulo(id_articulo),
        tipo_propiedad      TEXT,
        superficie_terreno  REAL,
        superficie_construida REAL,
        num_habitaciones    INTEGER,
        ubicacion_detallada TEXT,
        doc_path            TEXT
    );

    -- AC-VAL: Validaciones administrativas
    CREATE TABLE IF NOT EXISTS validacion (
        id_validacion   INTEGER PRIMARY KEY AUTOINCREMENT,
        id_articulo     INTEGER NOT NULL REFERENCES articulo(id_articulo),
        id_admin        INTEGER REFERENCES usuario(id_usuario),
        decision        TEXT,               -- Aprobado, Rechazado, Automatico
        comentario      TEXT,
        fecha_limite    TEXT,               -- para control del temporizador
        fecha_decision  TEXT,
        extendida       INTEGER DEFAULT 0
    );

    -- AC-SUB: Subastas
    CREATE TABLE IF NOT EXISTS subasta (
        id_subasta      INTEGER PRIMARY KEY AUTOINCREMENT,
        id_articulo     INTEGER NOT NULL REFERENCES articulo(id_articulo),
        id_tipo         INTEGER NOT NULL REFERENCES cat_tipo_subasta(id),
        precio_base     REAL    NOT NULL,   -- Holandesa: precio de ARRANQUE alto (inmutable)
        precio_actual   REAL    NOT NULL,
        incremento_min  REAL    NOT NULL DEFAULT 1,
        precio_piso     REAL,               -- Holandesa: piso del descenso (RN-09)
        decremento_hora REAL,               -- Holandesa: decremento por hora (RN-09)
        fecha_inicio    TEXT    NOT NULL,
        fecha_fin       TEXT    NOT NULL,
        id_estado       INTEGER NOT NULL DEFAULT 1 REFERENCES cat_estado_subasta(id),
        id_ganador      INTEGER REFERENCES usuario(id_usuario),
        motivo_cancel   TEXT
    );

    -- AC-OFE: Ofertas
    CREATE TABLE IF NOT EXISTS oferta (
        id_oferta       INTEGER PRIMARY KEY AUTOINCREMENT,
        id_subasta      INTEGER NOT NULL REFERENCES subasta(id_subasta),
        id_comprador    INTEGER NOT NULL REFERENCES usuario(id_usuario),
        monto           REAL    NOT NULL,
        fecha_oferta    TEXT    NOT NULL DEFAULT (datetime('now')),
        es_sellada      INTEGER NOT NULL DEFAULT 0
    );

    -- AC-PAG: Pagos
    CREATE TABLE IF NOT EXISTS pago (
        id_pago         INTEGER PRIMARY KEY AUTOINCREMENT,
        id_subasta      INTEGER NOT NULL REFERENCES subasta(id_subasta),
        id_comprador    INTEGER NOT NULL REFERENCES usuario(id_usuario),
        monto           REAL    NOT NULL,
        id_estado       INTEGER NOT NULL DEFAULT 1 REFERENCES cat_estado_pago(id),
        comprobante     TEXT,
        fecha_limite    TEXT    NOT NULL,
        fecha_pago      TEXT,
        es_segundo      INTEGER NOT NULL DEFAULT 0
    );

    -- AC-CAL: Calificaciones
    CREATE TABLE IF NOT EXISTS calificacion (
        id_calificacion INTEGER PRIMARY KEY AUTOINCREMENT,
        id_subasta      INTEGER NOT NULL REFERENCES subasta(id_subasta),
        id_calificador  INTEGER NOT NULL REFERENCES usuario(id_usuario),
        id_calificado   INTEGER NOT NULL REFERENCES usuario(id_usuario),
        puntuacion      INTEGER NOT NULL CHECK(puntuacion BETWEEN 1 AND 5),
        comentario      TEXT,
        fecha           TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- AC-NOT: Notificaciones
    CREATE TABLE IF NOT EXISTS notificacion (
        id_notificacion INTEGER PRIMARY KEY AUTOINCREMENT,
        id_usuario      INTEGER NOT NULL REFERENCES usuario(id_usuario),
        mensaje         TEXT    NOT NULL,
        tipo            TEXT    NOT NULL DEFAULT 'Info',  -- Exito, Info, Advertencia, Error
        leida           INTEGER NOT NULL DEFAULT 0,
        fecha           TEXT    NOT NULL DEFAULT (datetime('now')),
        id_ref          INTEGER             -- id de subasta o articulo relacionado
    );

    -- AC-LOG: Log de acciones administrativas (RNF-10)
    CREATE TABLE IF NOT EXISTS log_admin (
        id_log          INTEGER PRIMARY KEY AUTOINCREMENT,
        id_admin        INTEGER NOT NULL REFERENCES usuario(id_usuario),
        accion          TEXT    NOT NULL,
        detalle         TEXT,
        fecha           TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- AC-LN: Lista negra de correos (RN-26)
    CREATE TABLE IF NOT EXISTS lista_negra (
        id_lista    INTEGER PRIMARY KEY AUTOINCREMENT,
        correo      TEXT    NOT NULL UNIQUE,
        motivo      TEXT,
        fecha       TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- AC-IMG: Imagenes de evidencia al confirmar recepcion (CU-C07)
    CREATE TABLE IF NOT EXISTS imagen_recepcion (
        id_imagen   INTEGER PRIMARY KEY AUTOINCREMENT,
        id_pago     INTEGER NOT NULL REFERENCES pago(id_pago),
        ruta        TEXT    NOT NULL,
        fecha       TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- AC-PLAN: Plan de pagos a plazos (RN-27)
    CREATE TABLE IF NOT EXISTS plan_pago (
        id_plan           INTEGER PRIMARY KEY AUTOINCREMENT,
        id_pago           INTEGER NOT NULL REFERENCES pago(id_pago),
        num_cuota         INTEGER NOT NULL,
        monto_cuota       REAL    NOT NULL,
        fecha_vencimiento TEXT    NOT NULL,
        id_estado         INTEGER NOT NULL DEFAULT 1 REFERENCES cat_estado_pago(id)
    );

    -- AC-MAIL: Bandeja de correos de salida (stub C10, sin SMTP real)
    CREATE TABLE IF NOT EXISTS correo_salida (
        id_correo       INTEGER PRIMARY KEY AUTOINCREMENT,
        id_destinatario INTEGER NOT NULL REFERENCES usuario(id_usuario),
        correo_destino  TEXT    NOT NULL,
        asunto          TEXT    NOT NULL,
        cuerpo          TEXT,
        fecha           TEXT    NOT NULL DEFAULT (datetime('now')),
        enviado         INTEGER NOT NULL DEFAULT 0
    );
    """)

    conn.commit()
    conn.close()


def seed_demo():
    """Inserta datos de demostración si la BD está vacía."""
    from werkzeug.security import generate_password_hash
    conn = get_db()
    c = conn.cursor()

    if c.execute("SELECT COUNT(*) FROM usuario").fetchone()[0] > 0:
        conn.close()
        return

    usuarios = [
        ("Admin Sistema", "admin@subasta.mx", generate_password_hash("Admin1234"), 1, 1, 0, 0, 1),
        ("Ana Compradora", "ana@mail.mx",     generate_password_hash("Ana12345"),  2, 1, 4.5, 2, 1),
        ("Carlos Compra",  "carlos@mail.mx",  generate_password_hash("Carlos1234"), 2, 1, 0, 0, 1),
        ("Vendedor Demo",  "vend@mail.mx",    generate_password_hash("Vend1234"),  3, 1, 4.2, 5, 1),
        # A1: el profesor pidió 2 administradores con los mismos permisos
        ("Admin Dos",      "admin2@subasta.mx", generate_password_hash("Admin1234"), 1, 1, 0, 0, 1),
    ]
    c.executemany(
        "INSERT INTO usuario (nombre,correo,password_hash,id_tipo,id_estado,reputacion,total_cal,terminos_ok) VALUES(?,?,?,?,?,?,?,?)",
        usuarios
    )

    # Articulos demo
    c.execute(
        "INSERT INTO articulo (titulo,descripcion,id_tipo,id_condicion,ubicacion,id_vendedor,id_estado) VALUES(?,?,?,?,?,?,?)",
        ("Laptop Gaming MSI", "Laptop en excelente estado, 16GB RAM, RTX 3060", 1, 2, "CDMX", 4, 4)
    )
    id_art1 = c.lastrowid

    c.execute(
        "INSERT INTO articulo (titulo,descripcion,id_tipo,id_condicion,ubicacion,id_vendedor,id_estado) VALUES(?,?,?,?,?,?,?)",
        ("Honda Civic 2020", "Vehículo en buen estado, documentos completos", 2, 2, "Guadalajara", 4, 1)
    )
    id_art2 = c.lastrowid
    c.execute("INSERT INTO vehiculo VALUES(?,?,?,?,?,?,?)", (id_art2, "Honda","Civic",2020,45000,"VIN12345XYZ", None))

    # Subasta activa
    c.execute(
        """INSERT INTO subasta (id_articulo,id_tipo,precio_base,precio_actual,incremento_min,fecha_inicio,fecha_fin,id_estado)
           VALUES(?,?,?,?,?,datetime('now','-1 hour'),datetime('now','+2 days'),1)""",
        (id_art1, 1, 8000, 8500, 100)
    )
    id_sub = c.lastrowid

    # Oferta demo
    c.execute(
        "INSERT INTO oferta (id_subasta,id_comprador,monto) VALUES(?,?,?)",
        (id_sub, 2, 8500)
    )

    # Notificacion demo
    c.execute(
        "INSERT INTO notificacion (id_usuario,mensaje,tipo,id_ref) VALUES(?,?,?,?)",
        (2, "¡Su oferta de $8,500 ha sido registrada!", "Exito", id_sub)
    )

    # ── Subasta HOLANDESA activa (RN-09): arranque 1000, piso 500, decremento 100/h ──
    # fecha_inicio backdateada 3 h → precio_actual ya muestra 1000 - 100*3 = 700
    c.execute(
        "INSERT INTO articulo (titulo,descripcion,id_tipo,id_condicion,ubicacion,id_vendedor,id_estado) VALUES(?,?,?,?,?,?,?)",
        ("Reloj de colección vintage", "Subasta holandesa: el precio baja $100 cada hora hasta un piso de $500", 1, 2, "CDMX", 4, 4)
    )
    id_art3 = c.lastrowid
    c.execute(
        """INSERT INTO subasta (id_articulo,id_tipo,precio_base,precio_actual,incremento_min,precio_piso,decremento_hora,fecha_inicio,fecha_fin,id_estado)
           VALUES(?,?,?,?,?,?,?,datetime('now','-3 hours'),datetime('now','+1 day'),1)""",
        (id_art3, 2, 1000, 700, 1, 500, 100)
    )

    # ── Subasta SELLADA activa (RN-10): precio_base 800, cierra en 2 días ──
    c.execute(
        "INSERT INTO articulo (titulo,descripcion,id_tipo,id_condicion,ubicacion,id_vendedor,id_estado) VALUES(?,?,?,?,?,?,?)",
        ("Cuadro original firmado", "Subasta sellada: ofertas privadas, el ganador se revela al cierre", 1, 1, "Monterrey", 4, 4)
    )
    id_art4 = c.lastrowid
    c.execute(
        """INSERT INTO subasta (id_articulo,id_tipo,precio_base,precio_actual,incremento_min,fecha_inicio,fecha_fin,id_estado)
           VALUES(?,?,?,?,?,datetime('now','-1 hour'),datetime('now','+2 days'),1)""",
        (id_art4, 3, 800, 800, 1)
    )

    # Validacion pendiente para vehiculo (A3/RN-03: vehiculos/inmuebles SIN limite de tiempo)
    c.execute(
        "INSERT INTO validacion (id_articulo,fecha_limite) VALUES(?,?)",
        (id_art2, None)
    )

    # Lista negra demo (RN-26): correo bloqueado para probar rechazo en registro
    c.execute(
        "INSERT INTO lista_negra (correo,motivo) VALUES(?,?)",
        ("fraude@mail.mx", "Cuenta fraudulenta de demostración")
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    seed_demo()
    print("Base de datos inicializada con datos de demo.")
