import psycopg2
from psycopg2.extras import execute_values
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging
import uvicorn


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sensor_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
DB_CONFIG = {
    "dbname": "sensor_data",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": 5432
}

sensor_data_list_to_store = ['gravity', 'accelerometer']

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_database(sensor_data_to_store='gravity'):
    """Initialize PostgreSQL database with required tables"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {sensor_data_to_store}_data (
            timestamp TIMESTAMP PRIMARY KEY,
            client_ip TEXT,
            x REAL,
            y REAL,
            z REAL
        )
    ''')
    cursor.execute(f'''
        CREATE INDEX IF NOT EXISTS idx_timestamp 
        ON {sensor_data_to_store}_data (timestamp)
    ''')
    conn.commit()
    conn.close()
    logger.info(f"Table for {sensor_data_to_store} initialized successfully")

def store_data_in_db(sensor_name, timestamp, client_ip, x, y, z):
    """Store sensor data in PostgreSQL database"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"INSERT INTO {sensor_name}_data (timestamp, client_ip, x, y, z) VALUES (%s, %s, %s, %s, %s)",
            (timestamp, client_ip, x, y, z)
        )
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()  # Ignore duplicate timestamps
    except Exception as e:
        logger.error(f"Error storing data: {e}")
        raise
    finally:
        conn.close()

@app.post("/data")
async def upload_sensor_data(request: Request):
    try:
        data = await request.json()
        payload = data.get("payload", [])
        
        if not isinstance(payload, list):
            logger.warning("Invalid payload format received")
            return {"status": "error", "message": "Invalid payload format"}
        
        client_ip = request.client.host
        processed_count = 0
        for d in payload:
            if d.get("name") in sensor_data_list_to_store:
                ts = datetime.fromtimestamp(d["time"] / 1_000_000_000)
                x, y, z = d["values"]["x"], d["values"]["y"], d["values"]["z"]
                store_data_in_db(d["name"], ts, client_ip, x, y, z)
                processed_count += 1

        return {"status": "success", "processed_count": processed_count}

    except Exception as e:
        logger.error(f"Error processing data: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "message": "Data collection server is running!",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    for sensor_data_to_store in sensor_data_list_to_store:
        init_database(sensor_data_to_store)

    logger.info("Starting sensor data server...")
    uvicorn.run(app, host="0.0.0.0", port=56204)
