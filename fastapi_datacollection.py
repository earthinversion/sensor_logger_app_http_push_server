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

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_database():
    """Initialize SQLite database with required table"""
    conn = sqlite3.connect("sensor_data.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accelerometer_data (
            timestamp DATETIME PRIMARY KEY,
            x REAL,
            y REAL,
            z REAL
        )
    ''')
    # Create index on timestamp for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_timestamp 
        ON accelerometer_data(timestamp)
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

def store_data_in_db(timestamp, x, y, z):
    """Store sensor data in SQLite database"""
    conn = sqlite3.connect("sensor_data.db")
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

@app.post("/data")
async def upload_sensor_data(request: Request):
    try:
        data = await request.json()
        payload = data.get("payload", [])
        
        if not isinstance(payload, list):
            logger.warning("Invalid payload format received")
            return {"status": "error", "message": "Invalid payload format"}
        
        ## print all the keys in the payload
        print(payload)
        processed_count = 0
        for d in payload:
            if d.get("name") in ["accelerometer"]:
                ts = datetime.fromtimestamp(d["time"] / 1_000_000_000)
                x, y, z = d["values"]["x"], d["values"]["y"], d["values"]["z"]
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

@app.get("/stats")
async def get_stats():
    """Get basic statistics about the stored data"""
    conn = sqlite3.connect("sensor_data.db")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                MIN(timestamp) as oldest_record,
                MAX(timestamp) as newest_record
            FROM accelerometer_data
        """)
        total, oldest, newest = cursor.fetchone()
        return {
            "total_records": total,
            "oldest_record": oldest,
            "newest_record": newest
        }
    finally:
        conn.close()

if __name__ == "__main__":
    init_database()
    logger.info("Starting sensor data server...")
    uvicorn.run(app, host="0.0.0.0", port=56204)