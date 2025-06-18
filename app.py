from flask import Flask, request, jsonify
import psycopg2
import requests
import base64

app = Flask(__name__)

DB_URL = "postgresql://requisitoriados_user:x0xLGMH3N71ZfUG9UX7rcBiujKiELzKY@dpg-d114ho2li9vc738covqg-a.oregon-postgres.render.com/requisitoriados"
NOTIFICACIONES_URL = "https://notificaciones-identity.onrender.com/notificaciones"

def connect_db():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_reportes_table():
    conn = connect_db()
    cur = conn.cursor()

    # Tabla de reportes exitosos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reportes_exitosos (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            requisitoriado_id INTEGER NOT NULL
        );
    """)

    # Tabla de denuncias exitosas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS denuncias_exitosas (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            requisitoriado_id INTEGER NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

def enviar_notificacion(usuario_id, tipo, mensaje):
    try:
        requests.post(NOTIFICACIONES_URL, json={
            "usuario_id": usuario_id,
            "tipo": tipo,
            "mensaje": mensaje
        })
    except Exception as e:
        print(f"Error al enviar notificación: {e}")

@app.route('/requisitoriados', methods=['GET'])
def get_requisitoriados():
    try:
        page = max(int(request.args.get('page', 1)), 1)
        limit = min(int(request.args.get('limit', 5)), 50)
        nombre_filtro = request.args.get('nombre', '').strip()
    except ValueError:
        return jsonify({"exito": False, "error": "Parámetros inválidos"}), 400

    offset = (page - 1) * limit

    conn = connect_db()
    cur = conn.cursor()

    params = []
    filtro_sql = ""

    if nombre_filtro:
        filtro_sql = "WHERE nombre ILIKE %s"
        params.append(f"%{nombre_filtro}%")

    # Conteo total con filtro
    cur.execute(f"SELECT COUNT(*) FROM requisitoriados {filtro_sql};", params)
    total_registros = cur.fetchone()[0]

    # Consulta de datos con filtro + paginación
    params.extend([limit, offset])
    cur.execute(f"""
        SELECT id, nombre, recompensa, imagen
        FROM requisitoriados
        {filtro_sql}
        ORDER BY id
        LIMIT %s OFFSET %s;
    """, params)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    lista = []
    for row in rows:
        imagen_binaria = row[3]
        imagen_base64 = base64.b64encode(imagen_binaria).decode('utf-8') if imagen_binaria else ""
        imagen_data_uri = f"data:image/png;base64,{imagen_base64}" if imagen_base64 else ""

        lista.append({
            "id": row[0],
            "nombre": row[1],
            "recompensa": row[2],
            "imagen": imagen_data_uri
        })

    total_paginas = (total_registros + limit - 1) // limit

    return jsonify({
        "exito": True,
        "pagina": page,
        "por_pagina": limit,
        "total_registros": total_registros,
        "total_paginas": total_paginas,
        "tiene_anterior": page > 1,
        "tiene_siguiente": page < total_paginas,
        "requisitoriados": lista
    })

@app.route('/requisitoriado_id_por_person', methods=['POST'])
def obtener_id_por_person_id():
    data = request.get_json()
    person_id = data.get("personId")

    if not person_id:
        return jsonify({"exito": False, "error": "personId es requerido"}), 400

    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id
        FROM requisitoriados
        WHERE azure_person_id = %s;
    """, (person_id,))
    resultado = cur.fetchone()
    cur.close()
    conn.close()

    if not resultado:
        return jsonify({"exito": False, "error": "No se encontró requisitoriado con ese personId"}), 404

    return jsonify({
        "exito": True,
        "id": resultado[0]
    })

@app.route('/reportes', methods=['POST'])
def crear_reporte():
    data = request.get_json()
    usuario_id = data.get('usuario_id')
    requisitoriado_id = data.get('requisitoriado_id')

    if not usuario_id or not requisitoriado_id:
        return jsonify({"exito": False, "error": "usuario_id y requisitoriado_id son requeridos"}), 400

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM reportes_exitosos WHERE usuario_id = %s AND requisitoriado_id = %s;", (usuario_id, requisitoriado_id))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"exito": False, "error": "Reporte ya existe"}), 409

    cur.execute("SELECT nombre FROM requisitoriados WHERE id = %s;", (requisitoriado_id,))
    resultado = cur.fetchone()
    nombre = resultado[0] if resultado else "desconocido"

    cur.execute("""
        INSERT INTO reportes_exitosos (usuario_id, requisitoriado_id)
        VALUES (%s, %s) RETURNING id;
    """, (usuario_id, requisitoriado_id))
    nuevo_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    enviar_notificacion(usuario_id, "reporte_exitoso", f"Has creado un reporte exitoso del requisitoriado {nombre}")
    return jsonify({"exito": True, "mensaje": "Reporte creado", "reporte_id": nuevo_id})

@app.route('/denuncias', methods=['POST'])
def crear_denuncia():
    data = request.get_json()
    usuario_id = data.get('usuario_id')
    requisitoriado_id = data.get('requisitoriado_id')

    if not usuario_id or not requisitoriado_id:
        return jsonify({"exito": False, "error": "usuario_id y requisitoriado_id son requeridos"}), 400

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT nombre FROM requisitoriados WHERE id = %s;", (requisitoriado_id,))
    resultado = cur.fetchone()
    nombre = resultado[0] if resultado else "desconocido"

    cur.execute("""
        INSERT INTO denuncias_exitosas (usuario_id, requisitoriado_id)
        VALUES (%s, %s) RETURNING id;
    """, (usuario_id, requisitoriado_id))
    nuevo_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    enviar_notificacion(usuario_id, "denuncia_exitosa", f"Has denunciado exitosamente al requisitoriado {nombre}")
    return jsonify({"exito": True, "mensaje": "Denuncia creada", "denuncia_id": nuevo_id})

@app.route('/reportes/<int:reporte_id>', methods=['DELETE'])
def eliminar_reporte(reporte_id):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT usuario_id, requisitoriado_id FROM reportes_exitosos WHERE id = %s;", (reporte_id,))
    resultado = cur.fetchone()

    if not resultado:
        cur.close()
        conn.close()
        return jsonify({"exito": False, "error": "Reporte no encontrado"}), 404

    usuario_id, requisitoriado_id = resultado

    cur.execute("SELECT nombre FROM requisitoriados WHERE id = %s;", (requisitoriado_id,))
    nombre_resultado = cur.fetchone()
    nombre = nombre_resultado[0] if nombre_resultado else "desconocido"

    cur.execute("DELETE FROM reportes_exitosos WHERE id = %s;", (reporte_id,))
    conn.commit()
    cur.close()
    conn.close()

    enviar_notificacion(usuario_id, "reporte_eliminado", f"Has eliminado el reporte del requisitoriado {nombre}")
    return jsonify({"exito": True, "mensaje": "Reporte eliminado"})

@app.route('/reportes/<int:usuario_id>', methods=['GET'])
def obtener_reportes_por_usuario(usuario_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.requisitoriado_id, req.nombre, req.recompensa, req.imagen
        FROM reportes_exitosos r
        JOIN requisitoriados req ON r.requisitoriado_id = req.id
        WHERE r.usuario_id = %s;
    """, (usuario_id,))
    resultados = cur.fetchall()
    cur.close()
    conn.close()

    reportes = []
    for r in resultados:
        imagen_binaria = r[4]
        imagen_base64 = base64.b64encode(imagen_binaria).decode('utf-8') if imagen_binaria else ""
        imagen_data_uri = f"data:image/png;base64,{imagen_base64}" if imagen_base64 else ""
        
        reportes.append({
            "id": r[0],
            "requisitoriado_id": r[1],
            "nombre": r[2],
            "recompensa": r[3],
            "imagen": imagen_data_uri
        })

    return jsonify({
        "exito": True,
        "reportes": reportes
    })


if __name__ != '__main__':
    init_reportes_table()
else:
    init_reportes_table()
    app.run(debug=True)
