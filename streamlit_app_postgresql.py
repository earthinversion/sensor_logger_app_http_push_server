import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import create_engine
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('streamlit_app.log'),
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

# Create SQLAlchemy engine
DB_URI = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
engine = create_engine(DB_URI)

sensor_data_to_store = 'accelerometer'  # 'gravity' or 'accelerometer'

# Function to fetch the last 'duration' seconds of samples from the database
def get_last_samples(client_ip=None, duration=10):
    if client_ip is None:
        return pd.DataFrame()

    try:
        query = f"""
            SELECT timestamp, x, y, z 
            FROM {sensor_data_to_store}_data 
            WHERE client_ip = '{client_ip}'
            AND timestamp >= NOW() - INTERVAL '{duration} seconds'
            ORDER BY timestamp ASC
        """
        df = pd.read_sql_query(query, engine)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return pd.DataFrame()

# Function to visualize the data
def update_visualization(client_ip, placeholder, duration):
    df = get_last_samples(client_ip, duration)
    
    if df.empty:
        placeholder.warning("No data available.")
        return

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
    )

    fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["x"], mode="lines"),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["y"], mode="lines"),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["z"], mode="lines"),
        row=3, col=1
    )

    fig.update_layout(
        height=600,
        margin=dict(l=40, r=40, t=40, b=40),
        showlegend=False
    )
    fig.update_yaxes(title_text="X", row=1, col=1)
    fig.update_yaxes(title_text="Y", row=2, col=1)
    fig.update_yaxes(title_text="Z", row=3, col=1)

    placeholder.plotly_chart(fig, use_container_width=True)

# Function to get all client_ip in the database
def get_all_client_ip():
    try:
        query = f"""
            SELECT DISTINCT client_ip
            FROM {sensor_data_to_store}_data
        """
        df = pd.read_sql_query(query, engine)
        return df['client_ip'].tolist()
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return []

# Main function
def main():
    st.title(f"{sensor_data_to_store.capitalize()} Data Visualization")
    
    # Create a placeholder for the plot
    placeholder = st.empty()

    # Add a dropdown for selecting client_ip
    client_ip = st.sidebar.selectbox(
        "Select Client IP",
        options=get_all_client_ip()
    )

    # Add a slider for waveform duration
    duration = st.sidebar.slider(
        "Select Duration (seconds)",
        min_value=10,
        max_value=300,
        value=60,
        step=10
    )

    # Add auto-refresh option
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
    refresh_rate = st.sidebar.slider(
        "Refresh Rate (seconds)",
        min_value=0.1,
        max_value=5.0,
        value=0.5,
        step=0.1
    ) if auto_refresh else None

    while True:
        update_visualization(client_ip, placeholder, duration)
        if auto_refresh:
            time.sleep(refresh_rate)
        else:
            break

    if not auto_refresh:
        if st.sidebar.button("Refresh Now"):
            update_visualization(client_ip, placeholder, duration)

if __name__ == "__main__":
    main()
