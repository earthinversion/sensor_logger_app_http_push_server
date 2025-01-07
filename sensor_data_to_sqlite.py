import pandas as pd
import logging
from sqlalchemy import create_engine, text
from datetime import datetime

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
PG_DB_CONFIG = {
    "dbname": "sensor_data",
    "user": "postgres",
    "password": "password",
    "host": "localhost",
    "port": 5432
}

# SQLite Database Path
current_date_time = datetime.now().strftime('%Y%m%d%H%M%S')
SQLITE_FILE = f'sensor_data_{current_date_time}.sqlite'

# List of sensor tables
sensor_tables = ['accelerometer_data']  


def get_unique_client_ips(pg_engine):
    """Get the list of unique client_ip values from PostgreSQL."""
    client_ips = set()
    try:
        with pg_engine.connect() as conn:
            for table in sensor_tables:
                query = text(f"SELECT DISTINCT client_ip FROM {table} WHERE client_ip IS NOT NULL")
                result = conn.execute(query)
                ips = [row[0] for row in result]  # Access by index
                client_ips.update(ips)
        logger.info(f"Found {len(client_ips)} unique client_ip(s).")
    except Exception as e:
        logger.error(f"Error fetching client_ip values: {e}")
    return list(client_ips)


def export_to_sqlite(pg_engine, sqlite_engine, client_ip):
    """Export data for a specific client_ip to SQLite."""
    try:
        with pg_engine.connect() as pg_conn, sqlite_engine.connect() as sqlite_conn:
            for table in sensor_tables:
                query = f"""
                    SELECT *
                    FROM {table}
                    WHERE client_ip = %s
                    ORDER BY timestamp
                """
                df = pd.read_sql_query(query, pg_conn, params=(client_ip,))
                if not df.empty:
                    # Write to SQLite
                    df.to_sql(name=table, con=sqlite_conn, if_exists='append', index=False)
                    logger.info(f"Exported {len(df)} rows from {table} for client_ip {client_ip}.")
                else:
                    logger.info(f"No data found in {table} for client_ip {client_ip}.")
    except Exception as e:
        logger.error(f"Error exporting data for client_ip {client_ip}: {e}")


def main():
    """Main function to export data from PostgreSQL to SQLite."""
    # Create PostgreSQL and SQLite engines
    pg_engine = create_engine(
        f"postgresql://{PG_DB_CONFIG['user']}:{PG_DB_CONFIG['password']}@{PG_DB_CONFIG['host']}:{PG_DB_CONFIG['port']}/{PG_DB_CONFIG['dbname']}"
    )
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_FILE}")

    # Get the list of unique client_ips
    client_ips = get_unique_client_ips(pg_engine)

    # Export data for each client_ip to SQLite
    for client_ip in client_ips:
        logger.info(f"Processing data for client_ip {client_ip}...")
        export_to_sqlite(pg_engine, sqlite_engine, client_ip)

    logger.info(f"Data export completed. Data written to {SQLITE_FILE}.")


if __name__ == "__main__":
    main()
