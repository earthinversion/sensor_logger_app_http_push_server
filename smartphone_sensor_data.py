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
from scipy.ndimage import gaussian_filter
from client_tags import get_tags, init_tag_db, add_or_update_tag

# Set page configuration
st.set_page_config(
    page_title="San Diego Shake Tests",
    layout="wide",  # Increase the app's width
    initial_sidebar_state="expanded"
)

# Configure logging to save to a file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('streamlit_app.log')
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

def extract_dominant_frequency(Sxx, f):
    """Extract the single dominant frequency from the spectrogram if its power is above a threshold."""
    # Sum power over all time slices to get total power per frequency
    total_power = np.sum(Sxx, axis=1)
    total_power_db = 10 * np.log10(total_power)
    # print(total_power_db)
    # Define a power threshold
    power_threshold = -30  # dB  
    # Find the index of the frequency with the maximum total power
    dominant_frequency_index = np.argmax(total_power_db)
    # Check if the maximum power is above the threshold
    if total_power_db[dominant_frequency_index] > power_threshold:
        # Return the frequency corresponding to the maximum power
        return f[dominant_frequency_index]
    else:
        # Return None if no dominant frequency meets the threshold
        return None


def plot_spectrogram(data, component, fs=50):
    """Generate a spectrogram plot for a single component."""
    f, t, Sxx_rough = spectrogram(data, fs=fs, nperseg=256, noverlap=128, scaling='density')
    Sxx = gaussian_filter(Sxx_rough, sigma=1)

    # Extract dominant frequencies
    dominant_frequency = extract_dominant_frequency(Sxx, f)

    fig = go.Figure(data=go.Heatmap(
        x=t,
        y=f,
        z=10 * np.log10(Sxx),  # Convert power to dB
        colorscale='Jet',
        zmin=-80,  # Minimum dB value
        zmax=10,  # Maximum dB value
    ))
    fig.update_layout(
        title=f"Spectrogram ({component}-axis)",
        xaxis_title="Time (s)",
        yaxis_title="Frequency (Hz)",
    )
    return fig, dominant_frequency



def update_visualization(client_ip, duration):
    """Update waveform and spectrogram visualizations."""
    # Fetch the location data
    location_data = get_location_data(client_ip)
    location_info = f"""
    **Location Information:** ({location_data.get('latitude', 'N/A')}, {location_data.get('longitude', 'N/A')}, {location_data.get('altitude', 'N/A')} meters)
    """ if location_data else "No location data available for this client."

    # Fetch sensor data
    df = get_last_samples(client_ip, duration)
    if df.empty:
        return location_info, None, None

    # Create waveform plot
    waveform_fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
    )
    waveform_fig.add_trace(go.Scatter(x=df["timestamp"], y=df["x"], mode="lines", name="X"), row=1, col=1)
    waveform_fig.add_trace(go.Scatter(x=df["timestamp"], y=df["y"], mode="lines", name="Y"), row=2, col=1)
    waveform_fig.add_trace(go.Scatter(x=df["timestamp"], y=df["z"], mode="lines", name="Z"), row=3, col=1)
    waveform_fig.update_layout(
        width=600,
        margin=dict(l=40, r=40, t=40, b=40),
        showlegend=False,
    )
    waveform_fig.update_yaxes(title_text="X", row=1, col=1)
    waveform_fig.update_yaxes(title_text="Y", row=2, col=1)
    waveform_fig.update_yaxes(title_text="Z", row=3, col=1)

    # Generate spectrograms for all components
    spectrogram_figs = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
    )
    dominant_frequencies = {}
    spectrogram_fig, dominant_frequencies['X'] = plot_spectrogram(df["x"].values, "X")
    spectrogram_figs.add_trace(spectrogram_fig.data[0], row=1, col=1)
    spectrogram_fig, dominant_frequencies['Y'] = plot_spectrogram(df["y"].values, "Y")
    spectrogram_figs.add_trace(spectrogram_fig.data[0], row=2, col=1)
    spectrogram_fig, dominant_frequencies['Z'] = plot_spectrogram(df["z"].values, "Z")
    spectrogram_figs.add_trace(spectrogram_fig.data[0], row=3, col=1)


    spectrogram_figs.update_layout(
        width=600,
        margin=dict(l=40, r=40, t=40, b=40),
        showlegend=False,
    )

    return location_info, waveform_fig, spectrogram_figs, dominant_frequencies


def get_all_client_ip():
    """Fetch all unique client_ip values from the database."""
    try:
        query = f"""
            SELECT DISTINCT client_ip
            FROM {sensor_data_to_store}_data
        """
        df = pd.read_sql_query(query, engine)
        client_ips = df['client_ip'].tolist()

        # Load existing tags from SQLite
        tags = get_tags()

        # Combine client IPs with tags for display
        tagged_ips = [f"{ip} ({tags.get(ip, 'No Tag')})" for ip in client_ips]
        return tagged_ips, client_ips, tags
    
    except Exception as e:
        logger.error(f"Error fetching client_ip values: {e}")
        return []


def main():
    st.title(f"{sensor_data_to_store.capitalize()} Data Visualization")

    # Initialize the SQLite database
    init_tag_db()

    # Get client IPs and tags
    tagged_ips, client_ips, tags = get_all_client_ip()
    
    # Add a dropdown for selecting client_ip
    client_ip_with_tag = st.sidebar.selectbox(
        "Select Client IP",
        options=tagged_ips
    )

    # Extract the raw client_ip from the selection
    client_ip = client_ip_with_tag.split(" ")[0]

    # Display current tag and allow modification
    current_tag = tags.get(client_ip, "")
    new_tag = st.sidebar.text_input("Tag", value=current_tag)

    if st.sidebar.button("Save Tag"):
        add_or_update_tag(client_ip, new_tag)
        st.sidebar.success(f"Tag for {client_ip} updated to '{new_tag}'.")


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
    colx, coly = st.columns(2)
    with colx:
        location_placeholder = st.empty()
    with coly:
        dominant_frequencies_placeholder = st.empty()

    col1, col2 = st.columns(2)
    with col1:
        waveform_placeholder = st.empty()
    with col2:
        spectrogram_placeholder = st.empty()


    try:
        while auto_refresh:
            # Generate a unique key suffix using the current timestamp
            timestamp_key = int(time.time() * 1000)

            location_info, waveform_fig, spectrogram_figs, dominant_frequencies = update_visualization(client_ip, duration)

            dominant_frequencies_str = (
                f"**Dominant Frequencies (Hz):** X-comp: {dominant_frequencies['X']:.2f} Hz | "
                f"Y-comp: {dominant_frequencies['Y']:.2f} Hz | "
                f"Z-comp: {dominant_frequencies['Z']:.2f} Hz"
            )

            # Update location information
            location_placeholder.markdown(location_info)

            # Update dominant frequencies
            dominant_frequencies_placeholder.markdown(dominant_frequencies_str)

            # Use st.columns() dynamically for waveform and spectrogram
            waveform_col, spectrogram_col = st.columns([1, 1])

            with waveform_col:
                waveform_placeholder.plotly_chart(waveform_fig, key=f"waveform_{client_ip}_{timestamp_key}")

            with spectrogram_col:
                spectrogram_placeholder.plotly_chart(spectrogram_figs, key=f"spectrogram_{client_ip}_{timestamp_key}")

            time.sleep(refresh_rate)

    except Exception as e:
        logger.exception(f"Error: {e}")
        st.error("Something went wrong! Please check the logs for more information.")


if __name__ == "__main__":
    main()
