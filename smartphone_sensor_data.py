import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import create_engine
from datetime import datetime
from pytz import timezone
import logging
import time
from scipy.signal import spectrogram
import numpy as np

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

# Specify the local time zone
LOCAL_TIMEZONE = timezone("America/Los_Angeles")  

def get_location_data(client_ip):
    """Fetch the most recent location data for a given client_ip."""
    try:
        query = f"""
            SELECT latitude, longitude, altitude
            FROM location_data
            WHERE client_ip = '{client_ip}'
            ORDER BY timestamp DESC
            LIMIT 1
        """
        df = pd.read_sql_query(query, engine)
        if not df.empty:
            return df.iloc[0].to_dict()
        return {}
    except Exception as e:
        logger.error(f"Error fetching location data for client_ip {client_ip}: {e}")
        return {}

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
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert(LOCAL_TIMEZONE)  # Convert to local time
        return df
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return pd.DataFrame()

def plot_spectrogram(data, fs=50):
    """Generate a spectrogram plot from the accelerometer data."""
    f, t, Sxx = spectrogram(data, fs=fs, nperseg=256, noverlap=128, scaling='density')
    spectrogram_fig = go.Figure(data=go.Heatmap(
        x=t,
        y=f,
        z=10 * np.log10(Sxx),  # Convert power to dB
        colorscale='Jet'
    ))
    spectrogram_fig.update_layout(
        title="Spectrogram (X-axis Data)",
        xaxis_title="Time (s)",
        yaxis_title="Frequency (Hz)",
        height=400
    )
    return spectrogram_fig

# Function to visualize the data
def update_visualization(client_ip, location_placeholder, waveform_placeholder, spectrogram_placeholder, duration):
    # Fetch the location data
    location_data = get_location_data(client_ip)
    if location_data:
        location_placeholder.markdown(
            f"""
            **Location Information:**
            - **Latitude:** {location_data.get('latitude', 'N/A')}
            - **Longitude:** {location_data.get('longitude', 'N/A')}
            - **Altitude:** {location_data.get('altitude', 'N/A')} meters
            """
        )
    else:
        location_placeholder.warning("No location data available for this client.")


    # Fetch sensor data and create plots
    df = get_last_samples(client_ip, duration)
    
    if df.empty:
        waveform_placeholder.warning("No data available.")
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

    # Store the waveform in session state to prevent reloading
    st.session_state['waveform_fig'] = fig

    with waveform_placeholder.container():
        st.plotly_chart(fig, use_container_width=True)

    # Plot spectrogram for "x" component
    spectrogram_fig = plot_spectrogram(df["x"].values)
    st.session_state['spectrogram_fig'] = spectrogram_fig
    with spectrogram_placeholder.container():
        st.plotly_chart(spectrogram_fig, use_container_width=True)

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
    location_placeholder = st.empty()
    waveform_placeholder = st.empty()
    spectrogram_placeholder = st.empty()

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

    # Initialize session state for plots
    if 'waveform_fig' not in st.session_state:
        st.session_state['waveform_fig'] = None
    if 'spectrogram_fig' not in st.session_state:
        st.session_state['spectrogram_fig'] = None

    try:
        while auto_refresh:
            update_visualization(client_ip, location_placeholder, waveform_placeholder, spectrogram_placeholder, duration)
            time.sleep(refresh_rate)
    except Exception as e:
        logger.error(f"Error in visualization loop: {e}")
        st.error(f"An error occurred: {str(e)}")

    if not auto_refresh:
        if st.sidebar.button("Refresh Now"):
            update_visualization(client_ip, location_placeholder, waveform_placeholder, spectrogram_placeholder, duration)

if __name__ == "__main__":
    main()
