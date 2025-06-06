from flask import Flask, request, jsonify
import psycopg2
import os

app = Flask(__name__)

DB_URL = "postgresql://requisitoriados_user:x0xLGMH3N71ZfUG9UX7rcBiujKiELzKY@dpg-d114ho2li9vc738covqg-a.oregon-postgres.render.com/requisitoriados"

def connect_db():
    return psycopg2.connect(DB_URL, sslmode='require')

def init_reportes_table():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reportes_exitosos (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            requisitoriado_id INTEGER NOT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.route('/requisitoriados', methods=['GET'])
def get_requisitoriados():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, recompensa, imagen FROM requisitoriados;")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    lista = []
    for row in rows:
        lista.append({
            "id": row[0],
            "nombre": row[1],
            "recompensa": row[2],
            "imagen": row[3]
        })
    return jsonify({"exito": True, "requisitoriados": lista})

@app.route('/reportes/<int:usuario_id>', methods=['GET'])
def get_reportes(usuario_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, req.id, req.nombre, req.recompensa, req.imagen
        FROM reportes_exitosos r
        JOIN requisitoriados req ON r.requisitoriado_id = req.id
        WHERE r.usuario_id = %s;
    """, (usuario_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    reportes = []
    for row in rows:
        reportes.append({
            "reporte_id": row[0],
            "requisitoriado_id": row[1],
            "nombre": row[2],
            "recompensa": row[3],
            "imagen": row[4]
        })

    return jsonify({"exito": True, "reportes": reportes})

@app.route('/reportes', methods=['POST'])
def crear_reporte():
    data = request.get_json()
    usuario_id = data.get('usuario_id')
    requisitoriado_id = data.get('requisitoriado_id')

    if not usuario_id or not requisitoriado_id:
        return jsonify({"exito": False, "error": "usuario_id y requisitoriado_id son requeridos"}), 400

    conn = connect_db()
    cur = conn.cursor()

    # Verificar si el reporte ya existe para evitar duplicados
    cur.execute("""
        SELECT id FROM reportes_exitosos WHERE usuario_id = %s AND requisitoriado_id = %s;
    """, (usuario_id, requisitoriado_id))
    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"exito": False, "error": "Reporte ya existe"}), 409

    # Insertar el reporte
    cur.execute("""
        INSERT INTO reportes_exitosos (usuario_id, requisitoriado_id)
        VALUES (%s, %s) RETURNING id;
    """, (usuario_id, requisitoriado_id))
    nuevo_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"exito": True, "mensaje": "Reporte creado", "reporte_id": nuevo_id})

@app.route('/reportes/<int:reporte_id>', methods=['DELETE'])
def eliminar_reporte(reporte_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM reportes_exitosos WHERE id = %s;", (reporte_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"exito": False, "error": "Reporte no encontrado"}), 404

    cur.execute("DELETE FROM reportes_exitosos WHERE id = %s;", (reporte_id,))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"exito": True, "mensaje": "Reporte eliminado"})

if __name__ != '__main__':
    # Producción (Gunicorn, etc.)
    init_reportes_table()
else:
    # Desarrollo local
    init_reportes_table()
    app.run(debug=True)
