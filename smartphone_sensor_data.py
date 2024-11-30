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

def get_last_samples(client_ip=None, duration=10):
    """Fetch the last 'duration' seconds of accelerometer data."""
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

def update_visualization(client_ip, duration):
    """Update waveform and spectrogram visualizations."""
    # Fetch the location data
    location_data = get_location_data(client_ip)
    location_info = f"""
    **Location Information:**
    - **Latitude:** {location_data.get('latitude', 'N/A')}
    - **Longitude:** {location_data.get('longitude', 'N/A')}
    - **Altitude:** {location_data.get('altitude', 'N/A')} meters
    """ if location_data else "No location data available for this client."

    # Fetch sensor data and create plots
    df = get_last_samples(client_ip, duration)
    if df.empty:
        return location_info, None, None

    # Plot waveforms
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
    )

    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["x"], mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["y"], mode="lines"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["z"], mode="lines"), row=3, col=1)

    fig.update_layout(
        height=600,
        margin=dict(l=40, r=40, t=40, b=40),
        showlegend=False
    )
    fig.update_yaxes(title_text="X", row=1, col=1)
    fig.update_yaxes(title_text="Y", row=2, col=1)
    fig.update_yaxes(title_text="Z", row=3, col=1)

    # Plot spectrogram for "x" component
    spectrogram_fig = plot_spectrogram(df["x"].values)

    return location_info, fig, spectrogram_fig

def get_all_client_ip():
    """Fetch all unique client_ip values from the database."""
    try:
        query = f"""
            SELECT DISTINCT client_ip
            FROM {sensor_data_to_store}_data
        """
        df = pd.read_sql_query(query, engine)
        return df['client_ip'].tolist()
    except Exception as e:
        logger.error(f"Error fetching client_ip values: {e}")
        return []

def main():
    st.title(f"{sensor_data_to_store.capitalize()} Data Visualization")
    
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

    # Create placeholders
    location_placeholder = st.empty()
    waveform_placeholder = st.empty()
    spectrogram_placeholder = st.empty()

    try:
        while auto_refresh:
            location_info, waveform_fig, spectrogram_fig = update_visualization(client_ip, duration)

            # Update placeholders
            with location_placeholder.container():
                st.markdown("### Location Data")
                st.markdown(location_info)

            with waveform_placeholder.container():
                if waveform_fig:
                    st.markdown("### Waveform")
                    st.plotly_chart(waveform_fig, use_container_width=True)

            with spectrogram_placeholder.container():
                if spectrogram_fig:
                    st.markdown("### Spectrogram")
                    st.plotly_chart(spectrogram_fig, use_container_width=True)

            time.sleep(refresh_rate)

    except Exception as e:
        logger.error(f"Error: {e}")
        st.error("An error occurred.")

if __name__ == "__main__":
    main()
