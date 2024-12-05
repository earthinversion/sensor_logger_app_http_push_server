import pandas as pd
import psycopg2
import logging
from sqlalchemy import create_engine
from sqlalchemy.sql import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('export_sensor_data.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# PostgreSQL Database Configuration
DB_CONFIG = {
    "dbname": "sensor_data",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": 5432
}

# List of sensor tables
sensor_tables = ['accelerometer_data', 'gravity_data', 'gyroscope_data', 'totalacceleration_data']

# HDF5 File Path
HDF5_FILE = 'sensor_data.h5'


def get_unique_client_ips(engine):
    client_ips = set()
    try:
        with engine.connect() as conn:
            for table in sensor_tables:
                try:
                    # Use sqlalchemy.text to handle raw SQL
                    query = text(f"SELECT DISTINCT client_ip FROM {table} WHERE client_ip IS NOT NULL")
                    result = conn.execute(query)
                    ips = [row['client_ip'] for row in result]
                    client_ips.update(ips)
                except Exception as table_error:
                    logger.error(f"Error querying {table}: {table_error}")
        logger.info(f"Found {len(client_ips)} unique client_ip(s).")
    except Exception as e:
        logger.error(f"Error fetching client_ip values: {e}")
    return list(client_ips)



def extract_sensor_data(engine, client_ip):
    """Extract sensor data for a given client_ip from all sensor tables."""
    data = {}
    try:
        with engine.connect() as conn:
            for table in sensor_tables:
                query = f"""
                    SELECT *
                    FROM {table}
                    WHERE client_ip = %s
                    ORDER BY timestamp
                """
                df = pd.read_sql_query(query, conn, params=(client_ip,))
                if not df.empty:
                    data[table] = df
                    logger.info(f"Extracted {len(df)} rows from {table} for client_ip {client_ip}.")
                else:
                    logger.info(f"No data found in {table} for client_ip {client_ip}.")
    except Exception as e:
        logger.error(f"Error extracting data for client_ip {client_ip}: {e}")
    return data

def write_to_hdf5(client_ip, data, hdf5_file):
    """Write the extracted data for a client_ip to an HDF5 file."""
    try:
        with pd.HDFStore(hdf5_file, mode='a') as store:
            for table, df in data.items():
                group_key = f"/{client_ip}/{table}"
                store.put(group_key, df, format='table', data_columns=True)
                logger.info(f"Written {len(df)} rows to {group_key} in HDF5.")
    except Exception as e:
        logger.error(f"Error writing data to HDF5 for client_ip {client_ip}: {e}")

def main():
    """Main function to extract and write sensor data to HDF5."""
    # Create SQLAlchemy engine
    engine = create_engine(
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )

    # Get the list of unique client_ips
    client_ips = get_unique_client_ips(engine)

    # Extract and write data for each client_ip
    for client_ip in client_ips:
        logger.info(f"Processing data for client_ip {client_ip}...")
        data = extract_sensor_data(engine, client_ip)
        if data:
            write_to_hdf5(client_ip, data, HDF5_FILE)

    logger.info(f"Data export completed. Sensor data written to {HDF5_FILE}.")

if __name__ == "__main__":
    main()
