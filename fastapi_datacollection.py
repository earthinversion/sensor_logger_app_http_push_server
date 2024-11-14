# sensor_server.py
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import sqlite3
import logging

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
    """Initialize SQLite database with required table"""
    conn = sqlite3.connect(f"sensor_data_{sensor_data_to_store}.db")
    cursor = conn.cursor()
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {sensor_data_to_store}_data (
            timestamp DATETIME PRIMARY KEY,
            x REAL,
            y REAL,
            z REAL
        )
    ''')
    # Create index on timestamp for faster queries
    cursor.execute(f'''
        CREATE INDEX IF NOT EXISTS idx_timestamp 
        ON {sensor_data_to_store}_data(timestamp)
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

def store_data_in_db(timestamp, x, y, z):
    """Store sensor data in SQLite database"""
    conn = sqlite3.connect("sensor_data_accelerometer.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO accelerometer_data (timestamp, x, y, z) VALUES (?, ?, ?, ?)",
            (timestamp, x, y, z)
        )
        conn.commit()
        # print(f"Stored data at {timestamp}")
    except sqlite3.IntegrityError:
        pass  # Ignore duplicate timestamps
    except Exception as e:
        logger.error(f"Error storing data: {e}")
        raise
    finally:
        conn.close()

def store_gravity_data_in_db(timestamp, x, y, z):
    """Store sensor data in SQLite database"""
    conn = sqlite3.connect("sensor_data_gravity.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO gravity_data (timestamp, x, y, z) VALUES (?, ?, ?, ?)",
            (timestamp, x, y, z)
        )
        conn.commit()
        # print(f"Stored data at {timestamp}")
    except sqlite3.IntegrityError:
        pass  # Ignore duplicate timestamps
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
        
        ## print all the keys in the payload
        # print("-----------------")
        # print(payload)
        # print("-----------------")
        processed_count = 0
        for d in payload:
            if d.get("name") in sensor_data_list_to_store:
                ts = datetime.fromtimestamp(d["time"] / 1_000_000_000)
                x, y, z = d["values"]["x"], d["values"]["y"], d["values"]["z"]
                if d.get("name") == 'gravity':
                    store_gravity_data_in_db(ts, x, y, z)
                elif d.get("name") == 'accelerometer':
                    store_data_in_db(ts, x, y, z)
                processed_count += 1

            
        logger.info(f"Processed {processed_count} data points successfully")
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