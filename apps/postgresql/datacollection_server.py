from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import asyncio
import asyncpg
import logging
import uvicorn
import argparse


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

# sensor_data_list_to_store = ['gravity', 'accelerometer', 'barometer', 'magnetometer', 'compass', 'totalacceleration', 'battery', 'location']
sensor_data_list_to_store = ['gravity', 'accelerometer','accelerometeruncalibrated', 'gyroscope', 'totalacceleration']


# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run the sensor data server.")
parser.add_argument("--use-port", action="store_true", default=False, help="Include the client port in the IP address.")
args = parser.parse_args()

# Global variable for whether to use the port
use_port = args.use_port

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def create_database_if_not_exists():
    """Create the database if it doesn't exist"""
    try:
        # Connect to the default 'postgres' database
        conn = await asyncpg.connect(
            database="postgres",
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"]
        )
        # Check if the database exists
        query = f"SELECT 1 FROM pg_database WHERE datname = '{DB_CONFIG['dbname']}'"
        result = await conn.fetch(query)
        if not result:
            # Database does not exist; create it
            await conn.execute(f"CREATE DATABASE {DB_CONFIG['dbname']}")
            logger.info(f"Database '{DB_CONFIG['dbname']}' created successfully.")
        else:
            logger.info(f"Database '{DB_CONFIG['dbname']}' already exists.")
    except Exception as e:
        logger.error(f"Error creating database: {e}")
    finally:
        await conn.close()


async def cleanup_old_data():
    """Delete data older than 24 hours from the database."""
    while True:
        try:
            async with app.state.db_pool.acquire() as conn:
                for sensor_data_to_store in sensor_data_list_to_store:
                    query = f"""
                        DELETE FROM {sensor_data_to_store}_data 
                        WHERE timestamp < NOW() - INTERVAL '24 HOURS';
                    """
                    await conn.execute(query)
                    logger.info(f"Old data deleted from {sensor_data_to_store}_data table.")

                location_cleanup_query = """
                    DELETE FROM location_data 
                    WHERE timestamp < NOW() - INTERVAL '24 HOURS';
                """
                await conn.execute(location_cleanup_query)
                logger.info("Old data deleted from location_data table.")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        # Sleep for an hour before the next cleanup
        await asyncio.sleep(3600)

# Create database pool
@app.on_event("startup")
async def startup():
    await create_database_if_not_exists()
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

    await init_location_table() # Initialize the location table

    # Start the cleanup task
    asyncio.create_task(cleanup_old_data())

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

async def init_location_table():
    """Initialize the location table"""
    query = '''
        CREATE TABLE IF NOT EXISTS location_data (
            timestamp TIMESTAMP PRIMARY KEY,
            client_ip TEXT,
            latitude REAL,
            longitude REAL,
            altitude REAL,
            horizontal_accuracy REAL,
            vertical_accuracy REAL
        );
        CREATE INDEX IF NOT EXISTS idx_location_timestamp 
        ON location_data (timestamp);
    '''
    async with app.state.db_pool.acquire() as conn:
        await conn.execute(query)
    logger.info("Location table initialized successfully")

async def store_data_in_db(sensor_name, data):
    """Store sensor data in PostgreSQL database asynchronously"""
    query = f"""
        INSERT INTO {sensor_name}_data (timestamp, client_ip, x, y, z) 
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (timestamp) DO NOTHING
    """
    async with app.state.db_pool.acquire() as conn:
        await conn.executemany(query, data)

async def store_location_data(location_data):
    """Store location data in the database asynchronously"""
    query = """
        INSERT INTO location_data (timestamp, client_ip, latitude, longitude, altitude, horizontal_accuracy, vertical_accuracy) 
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (timestamp) DO NOTHING
    """
    async with app.state.db_pool.acquire() as conn:
        await conn.executemany(query, location_data)

@app.post("/data")
async def upload_sensor_data(request: Request):
    try:
        data = await request.json()
        payload = data.get("payload", [])
        
        if not isinstance(payload, list):
            logger.warning("Invalid payload format received")
            return {"status": "error", "message": "Invalid payload format"}
        
        # client_ip = request.client.host

        client_host = request.client.host

        if use_port:
            client_port = request.client.port
            client_ip = f"{client_host}:{client_port}"  # Combine host and port
        else:
            client_ip = client_host


        data_batches = {"gravity": [], "accelerometer": [], "accelerometeruncalibrated": [], "gyroscope": [], "totalacceleration": []}
        location_data = []
        processed_count = 0
        
        for d in payload:
            if d.get("name") in sensor_data_list_to_store:
                ts = datetime.fromtimestamp(d["time"] / 1_000_000_000)
                x, y, z = d["values"]["x"], d["values"]["y"], d["values"]["z"]
                data_batches[d["name"]].append((ts, client_ip, x, y, z))
                processed_count += 1
            elif d.get("name") == "location":
                ts = datetime.fromtimestamp(d["time"] / 1_000_000_000)
                location = d["values"]
                latitude = location.get("latitude")
                longitude = location.get("longitude")
                altitude = location.get("altitude")
                horizontal_accuracy = location.get("horizontalAccuracy")
                vertical_accuracy = location.get("verticalAccuracy")
                location_data.append((ts, client_ip, latitude, longitude, altitude, horizontal_accuracy, vertical_accuracy))

            # ## print if d.get("name") is not in sensor_data_list_to_store
            # else:
            #     # logger.warning(f"Invalid sensor data type: {d.get('name')} {d.get('values')}")
            #     if d.get('name') == 'location':
            #         logger.warning(f"Invalid sensor data type: {d.get('name')} {d.get('values')}")
            #         # location {'bearingAccuracy': 0, 'speedAccuracy': 1.5, 'verticalAccuracy': 1.5512449741363525, 'horizontalAccuracy': 32.0989990234375, 'speed': 0.008591005578637123, 'bearing': 0, 'altitude': 68.80000305175781, 'longitude': -122.2597648, 'latitude': 37.8743682}
        # Perform batch writes for each sensor type
        for sensor_name, sensor_data in data_batches.items():
            if sensor_data:
                await store_data_in_db(sensor_name, sensor_data)

        # Store location data
        if location_data:
            await store_location_data(location_data)

        return {"status": "success", "processed_count": processed_count}

    except Exception as e:
        logger.exception(f"Error processing data: {e}")
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
