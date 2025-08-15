import os
from flask import Flask, request, jsonify
from flask_httpauth import HTTPBasicAuth
import psycopg
from datetime import datetime
import logging

app = Flask(__name__)
auth = HTTPBasicAuth()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get credentials from environment variables
API_USERNAME = os.getenv('API_USERNAME')
API_PASSWORD = os.getenv('API_PASSWORD')
DATABASE_URL = os.getenv('DATABASE_URL')

@auth.verify_password
def verify_password(username, password):
    return username == API_USERNAME and password == API_PASSWORD

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})

@app.route('/data', methods=['POST'])
@auth.login_required
def save_data():
    """Save JSON payload to database"""
    try:
        # Validate JSON payload
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Empty JSON payload"}), 400
        
        # Save to database
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500

        try:
            with conn.cursor() as cur:
                page_name = data['page_name']
                page_id = data['page_id']
                request_ip = data['request_ip']
                logger.info(f"Saving {request_ip} {page_id} {page_name}")
                cur.execute("insert into tracker(page_name, page_id, request_ip) values (%s, %s, %s)",
                               (page_name, page_id, request_ip))
                # result = cur.fetchone()
                conn.commit()

                
                return jsonify({
                    "message": "Data saved successfully"
                }), 201
                
        except Exception as e:
            logger.error(f"Database insert error: {e}")
            conn.rollback()
            return jsonify({"error": "Failed to save data"}), 500
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Request processing error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/data', methods=['GET'])
@auth.login_required
def get_data():
    """Get all saved data (optional endpoint for testing)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("""
                        SELECT id, created_at,
                        page_name, page_id, request_ip 
                        FROM tracker 
                        ORDER BY created_at DESC 
                        LIMIT 1000;
                        """)
            results = cur.fetchall()
            
            # Convert to JSON-serializable format
            data = []
            for row in results:
                data.append({
                    "id": row['id'],
                    "created_at": row['created_at'].isoformat(),
                    "page_name": row['page_name'],
                    "page_id": row['page_id'],
                    "request_ip": row['request_ip']
                })
            
            return data, 200

    except Exception as e:
        logger.error(f"Database query error: {e}")
        return jsonify({"error": "Failed to retrieve data"}), 500
    finally:
        conn.close()

if __name__ == '__main__':

    # Run the app
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
