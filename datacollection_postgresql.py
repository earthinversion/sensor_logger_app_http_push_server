from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import asyncio
import asyncpg
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

# Create database pool
@app.on_event("startup")
async def startup():
    app.state.db_pool = await asyncpg.create_pool(
        database=DB_CONFIG["dbname"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        min_size=1,
        max_size=30  # Adjust based on the expected load
    )
    for sensor_data_to_store in sensor_data_list_to_store:
        await init_database(sensor_data_to_store)

@app.on_event("shutdown")
async def shutdown():
    await app.state.db_pool.close()

async def init_database(sensor_data_to_store='gravity'):
    """Initialize PostgreSQL database with required tables"""
    query = f'''
        CREATE TABLE IF NOT EXISTS {sensor_data_to_store}_data (
            timestamp TIMESTAMP PRIMARY KEY,
            client_ip TEXT,
            x REAL,
            y REAL,
            z REAL
        );
        CREATE INDEX IF NOT EXISTS idx_timestamp 
        ON {sensor_data_to_store}_data (timestamp);
    '''
    async with app.state.db_pool.acquire() as conn:
        await conn.execute(query)
    logger.info(f"Table for {sensor_data_to_store} initialized successfully")

async def store_data_in_db(sensor_name, data):
    """Store sensor data in PostgreSQL database asynchronously"""
    query = f"""
        INSERT INTO {sensor_name}_data (timestamp, client_ip, x, y, z) 
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (timestamp) DO NOTHING
    """
    async with app.state.db_pool.acquire() as conn:
        await conn.executemany(query, data)

@app.post("/data")
async def upload_sensor_data(request: Request):
    try:
        data = await request.json()
        payload = data.get("payload", [])
        
        if not isinstance(payload, list):
            logger.warning("Invalid payload format received")
            return {"status": "error", "message": "Invalid payload format"}
        
        client_ip = request.client.host
        data_batches = {"gravity": [], "accelerometer": []}
        processed_count = 0
        
        for d in payload:
            if d.get("name") in sensor_data_list_to_store:
                ts = datetime.fromtimestamp(d["time"] / 1_000_000_000)
                x, y, z = d["values"]["x"], d["values"]["y"], d["values"]["z"]
                data_batches[d["name"]].append((ts, client_ip, x, y, z))
                processed_count += 1
        
        # Perform batch writes for each sensor type
        for sensor_name, sensor_data in data_batches.items():
            if sensor_data:
                await store_data_in_db(sensor_name, sensor_data)

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
    logger.info("Starting sensor data server...")
    uvicorn.run(app, host="0.0.0.0", port=56204)
