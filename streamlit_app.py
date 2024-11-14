# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import sqlite3
from datetime import datetime, timedelta, timezone
import requests
import logging
from pytz import timezone
import pytz 

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

# Configuration
FASTAPI_URL = "http://localhost:56204"  # Update this if your server is on a different host

def check_server_health():
    """Check if the FastAPI server is running"""
    try:
        response = requests.get(f"{FASTAPI_URL}/")
        return response.status_code == 200
    except requests.RequestException:
        return False

def get_server_stats():
    """Get statistics from the server"""
    try:
        response = requests.get(f"{FASTAPI_URL}/stats")
        if response.status_code == 200:
            return response.json()
        return None
    except requests.RequestException:
        return None

def get_data_from_db(time_range_minutes):
    """Fetch data from SQLite database for the specified time range"""
    # Calculate start_time in UTC
    start_time = datetime.utcnow() - timedelta(minutes=time_range_minutes)
    conn = sqlite3.connect("sensor_data.db")
    try:
        query = """
            SELECT timestamp, x, y, z 
            FROM accelerometer_data 
            WHERE timestamp > ? 
            ORDER BY timestamp ASC
        """
        # Pass start_time in UTC ISO format
        df = pd.read_sql_query(query, conn, params=(start_time.strftime("%Y-%m-%dT%H:%M:%S"),))
        
        # Define the local timezone
        local_tz = timezone('America/Los_Angeles')  # Replace with your local timezone
        
        # Convert timestamps from UTC to local time for visualization
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize('UTC').dt.tz_convert(local_tz)
        return df
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def update_visualization(placeholder, time_range):
    """Update the visualization with current data"""
    df = get_data_from_db(time_range)
    
    if df.empty:
        placeholder.warning(f"No data found in the last {time_range} minutes.")
        return

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=("X Component", "Y Component", "Z Component")
    )

    fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["x"], mode="lines", line=dict(color="red")),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["y"], mode="lines", line=dict(color="green")),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["z"], mode="lines", line=dict(color="blue")),
        row=3, col=1
    )

    fig.update_layout(
        xaxis_title="Time",
        height=600,
        margin=dict(l=40, r=40, t=40, b=40),
        showlegend=False
    )
    fig.update_yaxes(title_text="X", row=1, col=1)
    fig.update_yaxes(title_text="Y", row=2, col=1)
    fig.update_yaxes(title_text="Z", row=3, col=1)

    with placeholder.container():
        st.plotly_chart(fig, use_container_width=True)
        
        # Display data statistics
        stats = get_server_stats()
        if stats:
            st.sidebar.markdown("### Data Statistics")
            st.sidebar.write(f"Total Records: {stats['total_records']}")
            st.sidebar.write(f"Oldest Record: {stats['oldest_record']}")
            st.sidebar.write(f"Newest Record: {stats['newest_record']}")

def main():
    st.title("Real-Time Accelerometer Visualization")
    
    # Check server status
    if not check_server_health():
        st.error("⚠️ Cannot connect to the sensor data server. Please ensure it's running.")
        st.stop()
    else:
        st.sidebar.success("✅ Connected to sensor data server")
    
    # Add time range selector in sidebar
    time_range = st.sidebar.slider(
        "Historical Data (minutes)",
        min_value=1,
        max_value=60,
        value=1,
        key="time_range"
    )
    
    # Create a placeholder for the plot
    placeholder = st.empty()
    
    # Add visualization controls
    with st.sidebar:
        st.markdown("### Visualization Controls")
        auto_refresh = st.checkbox("Auto-refresh", value=True)
        
        if auto_refresh:
            refresh_rate = st.slider(
                "Refresh Rate (seconds)",
                min_value=0.1,
                max_value=5.0,
                value=0.5,
                step=0.1
            )
            st.info(f"Updating every {refresh_rate} seconds")
        else:
            refresh_button = st.button("Refresh Now")
            if refresh_button:
                update_visualization(placeholder, time_range)
            st.info("Manual refresh mode")
            return

    try:
        while auto_refresh:
            update_visualization(placeholder, time_range)
            time.sleep(refresh_rate)
    except Exception as e:
        logger.error(f"Error in visualization loop: {e}")
        st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
