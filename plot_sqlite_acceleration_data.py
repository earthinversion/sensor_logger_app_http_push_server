import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# SQLite Database Path
SQLITE_FILE = 'sensor_data.sqlite'

def get_client_ips(sqlite_conn):
    """Retrieve the unique client_ip values from the accelerometer_data table."""
    query = "SELECT DISTINCT client_ip FROM accelerometer_data"
    client_ips = pd.read_sql_query(query, sqlite_conn)['client_ip'].tolist()
    return client_ips

def get_accelerometer_data(sqlite_conn, client_ip, hours):
    """Retrieve accelerometer data for a specific client_ip from the last `n` hours."""
    # Calculate the cutoff timestamp
    cutoff_time = datetime.now() - timedelta(hours=hours)
    cutoff_time_str = cutoff_time.strftime('%Y-%m-%d %H:%M:%S')
    
    query = f"""
        SELECT timestamp, x, y, z
        FROM accelerometer_data
        WHERE client_ip = ? AND timestamp >= ?
        ORDER BY timestamp
    """
    df = pd.read_sql_query(query, sqlite_conn, params=(client_ip, cutoff_time_str))
    return df

def plot_accelerometer_data(client_ip, data, fig_name):
    """Plot the accelerometer data (x, y, z) for a specific client_ip."""
    fig, axs = plt.subplots(3, 1, figsize=(10, 12), sharex=True)
    
    axs[0].plot(data['timestamp'], data['x'], label='X', color='r', alpha=0.7)
    axs[0].set_ylabel('X')
    axs[0].legend()
    axs[0].grid()

    axs[1].plot(data['timestamp'], data['y'], label='Y', color='g', alpha=0.7)
    axs[1].set_ylabel('Y')
    axs[1].legend()
    axs[1].grid()

    axs[2].plot(data['timestamp'], data['z'], label='Z', color='b', alpha=0.7)
    axs[2].set_ylabel('Z')
    axs[2].set_xlabel('Timestamp')
    axs[2].legend()
    axs[2].grid()

    plt.suptitle(f"Client {client_ip}")
    plt.xticks(rotation=45)
    
    # Set x-axis ticks to 5
    axs[2].xaxis.set_major_locator(plt.MaxNLocator(5))
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(fig_name, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved plot to {fig_name}")

def main():
    """Main function to read SQLite DB and plot accelerometer data."""
    # Number of hours to filter
    n_hours = 1
    
    # Connect to the SQLite database
    sqlite_conn = sqlite3.connect(SQLITE_FILE)
    
    # Get unique client_ip values
    client_ips = get_client_ips(sqlite_conn)
    print(f"Found {len(client_ips)} client(s): {client_ips}")
    
    # Plot accelerometer data for each client_ip
    for client_ip in client_ips:
        print(f"Plotting data for client_ip: {client_ip}")
        data = get_accelerometer_data(sqlite_conn, client_ip, n_hours)
        if not data.empty:
            client_ip_str = client_ip.replace('.', '_')
            fig_name = f"accelerometer_data_{client_ip_str}.png"
            plot_accelerometer_data(client_ip, data, fig_name)
        else:
            print(f"No accelerometer data found for client_ip: {client_ip} in the last {n_hours} hours.")
    
    # Close the SQLite connection
    sqlite_conn.close()

if __name__ == "__main__":
    main()
