from flask import Flask, request, jsonify
import psycopg2
import requests
import base64

app = Flask(__name__)

DB_URL = "postgresql://requisitoriados_user:x0xLGMH3N71ZfUG9UX7rcBiujKiELzKY@dpg-d114ho2li9vc738covqg-a.oregon-postgres.render.com/requisitoriados"
NOTIFICACIONES_URL = "https://notificaciones-identity.onrender.com/notificaciones"  # Asegúrate de que este puerto sea correcto

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
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, nombre, recompensa, imagen
        FROM requisitoriados
        ORDER BY id;
    """)
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

    return jsonify({
        "exito": True,
        "total": len(lista),
        "requisitoriados": lista
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

    cur.execute("""
        INSERT INTO reportes_exitosos (usuario_id, requisitoriado_id)
        VALUES (%s, %s) RETURNING id;
    """, (usuario_id, requisitoriado_id))
    nuevo_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    enviar_notificacion(usuario_id, "reporte_exitoso", f"Has creado un reporte exitoso del requisitoriado {requisitoriado_id}")
    return jsonify({"exito": True, "mensaje": "Reporte creado", "reporte_id": nuevo_id})

@app.route('/reportes/<int:reporte_id>', methods=['DELETE'])
def eliminar_reporte(reporte_id):
    conn = connect_db()
    cur = conn.cursor()
    
    # Obtener usuario_id y requisitoriado_id
    cur.execute("SELECT usuario_id, requisitoriado_id FROM reportes_exitosos WHERE id = %s;", (reporte_id,))
    resultado = cur.fetchone()

    if not resultado:
        cur.close()
        conn.close()
        return jsonify({"exito": False, "error": "Reporte no encontrado"}), 404

    usuario_id, requisitoriado_id = resultado

    # Eliminar el reporte
    cur.execute("DELETE FROM reportes_exitosos WHERE id = %s;", (reporte_id,))
    conn.commit()
    cur.close()
    conn.close()

    enviar_notificacion(usuario_id, "reporte_eliminado", f"Has eliminado el reporte del requisitoriado {requisitoriado_id}")
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
    # Producción (Gunicorn, etc.)
    init_reportes_table()
else:
    # Desarrollo local
    init_reportes_table()
    app.run(debug=True)
