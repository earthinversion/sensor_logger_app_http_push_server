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

def extract_dominant_frequency(Sxx, f, power_threshold=-30):
    """Extract the single dominant frequency from the spectrogram if its power is above a threshold."""
    # Sum power over all time slices to get total power per frequency
    total_power = np.sum(Sxx, axis=1)
    total_power_db = 10 * np.log10(total_power)
    # print(total_power_db)
    # Define a power threshold
    # Find the index of the frequency with the maximum total power
    dominant_frequency_index = np.argmax(total_power_db)
    # Check if the maximum power is above the threshold
    if total_power_db[dominant_frequency_index] > power_threshold:
        # Return the frequency corresponding to the maximum power
        return f[dominant_frequency_index]
    else:
        # Return None if no dominant frequency meets the threshold
        return 0.0

def extract_h_over_v_dominant_frequency(Sxx_f_dict, power_threshold=-30):
    """
    Compute the dominant frequency using the H/V (Horizontal-to-Vertical) spectral ratio.

    Parameters:
        Sxx_f_dict: dict
            A dictionary containing spectrogram data and frequencies for each component ('X', 'Y', 'Z').
            Example: {'X': (Sxx_x, f_x), 'Y': (Sxx_y, f_y), 'Z': (Sxx_z, f_z)}
        power_threshold: float
            Minimum power in dB to consider a frequency as dominant.

    Returns:
        float: Dominant frequency based on the H/V ratio.
    """
    try:
        # Extract the spectrogram data and frequency arrays for X, Y, and Z
        Sxx_x, f_x = Sxx_f_dict['X']
        Sxx_y, f_y = Sxx_f_dict['Y']
        Sxx_z, f_z = Sxx_f_dict['Z']

        # Add epsilon directly to replace zeros or negative values in spectrogram data
        epsilon = 1e-10
        Sxx_x = np.maximum(Sxx_x, epsilon)
        Sxx_y = np.maximum(Sxx_y, epsilon)
        Sxx_z = np.maximum(Sxx_z, epsilon)

        # Compute the power spectra in dB
        Sxx_x_db = 10 * np.log10(np.sum(Sxx_x, axis=1))
        Sxx_y_db = 10 * np.log10(np.sum(Sxx_y, axis=1))
        Sxx_z_db = 10 * np.log10(np.sum(Sxx_z, axis=1))


        ## check for all three components for the threshold
        for ss in [Sxx_x_db, Sxx_y_db, Sxx_z_db]:
            if np.max(ss) < power_threshold:
                return 0.0

        # Calculate average horizontal spectrum in dB (X and Y components)
        Sxx_h_db = (Sxx_x_db + Sxx_y_db) / 2

        # Ensure frequencies match across components
        if not np.array_equal(f_x, f_y) or not np.array_equal(f_x, f_z):
            raise ValueError("Frequency arrays for X, Y, and Z components must match.")

        # Compute the H/V ratio in dB
        hv_ratio_db = Sxx_h_db - Sxx_z_db
        # print(f"Sxx_z_db: {Sxx_z_db}")

        # Find the index of the frequency with the maximum H/V ratio above the power threshold
        valid_indices = np.where(hv_ratio_db > power_threshold)[0]
        # if len(valid_indices) == 0:
        #     # print("No valid indices")
        #     return 0.0  # Return 0 if no frequency meets the threshold

        dominant_index = valid_indices[np.argmax(hv_ratio_db[valid_indices])]
        return f_x[dominant_index]  # Return the dominant frequency
    except Exception as e:
        logger.error(f"Error in extract_h_over_v_dominant_frequency: {e}")
        return 0.0


def plot_spectrogram(data, component, fs=50, threshold=-30, freq_range=(0.05, 4)):
    """Generate a spectrogram plot for a single component."""
    f, t, Sxx_rough = spectrogram(data, fs=fs, nperseg=256, noverlap=128, scaling='density')
    Sxx = gaussian_filter(Sxx_rough, sigma=1)

    # Filter frequencies within the desired range
    freq_min, freq_max = freq_range
    freq_mask = (f >= freq_min) & (f <= freq_max)
    f = f[freq_mask]
    Sxx = Sxx[freq_mask, :]

    # Extract dominant frequencies
    dominant_frequency = extract_dominant_frequency(Sxx, f, power_threshold=threshold)

    Sxx_db = 10 * np.log10(Sxx)  # Convert power to dB
    fig = go.Figure(data=go.Heatmap(
        x=t,
        y=f,
        z=Sxx_db,  # Convert power to dB
        colorscale='Jet',
        zmin=-80,  # Minimum dB value
        zmax=10,  # Maximum dB value
    ))
    fig.update_layout(
        title=f"Spectrogram ({component}-axis)",
        xaxis_title="Time (s)",
        yaxis_title="Frequency (Hz)",
    )
    return fig, dominant_frequency, Sxx, f



def update_visualization(client_ip, duration, power_threshold=-10):
    """Update waveform and spectrogram visualizations."""
    # Fetch the location data
    location_data = get_location_data(client_ip)
    location_info = f"""
    {location_data.get('latitude', 'N/A'):.3f}, {location_data.get('longitude', 'N/A'):.3f}, {location_data.get('altitude', 'N/A')} m
    """ if location_data else "No location data available for this client."

    dominant_frequencies = {
        'X': 0.0,
        'Y': 0.0,
        'Z': 0.0
    }
    # Fetch sensor data
    df = get_last_samples(client_ip, duration)
    if df.empty:
        return location_info, None, None, dominant_frequencies, 0.0

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
        height=300,
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
    
    spectrogram_fig, dominant_frequencies['X'], Sxx_x, f_x = plot_spectrogram(df["x"].values, "X", threshold=power_threshold)
    spectrogram_figs.add_trace(spectrogram_fig.data[0], row=1, col=1)
    spectrogram_fig, dominant_frequencies['Y'], Sxx_y, f_y = plot_spectrogram(df["y"].values, "Y", threshold=power_threshold)
    spectrogram_figs.add_trace(spectrogram_fig.data[0], row=2, col=1)
    spectrogram_fig, dominant_frequencies['Z'], Sxx_z, f_z = plot_spectrogram(df["z"].values, "Z", threshold=power_threshold)
    spectrogram_figs.add_trace(spectrogram_fig.data[0], row=3, col=1)

    Sxx_f_dict = {
        'X': (Sxx_x, f_x),
        'Y': (Sxx_y, f_y),
        'Z': (Sxx_z, f_z)
    }

    hv_dominant_frequency = extract_h_over_v_dominant_frequency(Sxx_f_dict, power_threshold)

    # print(f"hv_dominant_frequency: {hv_dominant_frequency}")

    spectrogram_figs.update_layout(
        height=300,
        margin=dict(l=40, r=40, t=40, b=40),
        showlegend=False,
    )

    ## add title to the spectrogram
    spectrogram_figs.update_yaxes(title_text="Freq X", row=1, col=1)
    spectrogram_figs.update_yaxes(title_text="Freq Y", row=2, col=1)
    spectrogram_figs.update_yaxes(title_text="Freq Z", row=3, col=1)


    return location_info, waveform_fig, spectrogram_figs, dominant_frequencies, hv_dominant_frequency


# def get_all_client_ip():
#     """Fetch all unique client_ip values from the database."""
#     try:
#         query = f"""
#             SELECT DISTINCT client_ip
#             FROM {sensor_data_to_store}_data
#         """
#         df = pd.read_sql_query(query, engine)
#         client_ips = df['client_ip'].tolist()

#         # Load existing tags from SQLite
#         tags = get_tags()

#         # Combine client IPs with tags for display
#         tagged_ips = [f"{ip} ({tags.get(ip, 'No Tag')})" for ip in client_ips]
#         return tagged_ips, client_ips, tags
    
#     except Exception as e:
#         logger.error(f"Error fetching client_ip values: {e}")
#         return []

def get_all_client_ip():
    """Fetch all unique client_ip values from the database with data in the last nn seconds."""
    try:
        # Get the current time and subtract nn seconds to filter recent data
        query = f"""
            SELECT DISTINCT client_ip
            FROM {sensor_data_to_store}_data
            WHERE timestamp >= NOW() - INTERVAL '60 seconds'
        """
        df = pd.read_sql_query(query, engine)
        
        if df.empty:
            return [], [], {}  # Return empty lists if no data is found

        client_ips = df['client_ip'].tolist()

        # Load existing tags from SQLite
        tags = get_tags()

        # Combine client IPs with tags for display
        tagged_ips = [f"{ip} ({tags.get(ip, 'No Tag')})" for ip in client_ips]
        return tagged_ips, client_ips, tags

    except Exception as e:
        logger.error(f"Error fetching client_ip values: {e}")
        return []


def format_dominant_frequency(dominant_frequency):
    """Format the dominant frequency string."""
    if dominant_frequency == 0.0:
        return "N/A"
    return f"{dominant_frequency:.2f} Hz"

def main():

    # Initialize the SQLite database
    init_tag_db()

    # Get client IPs and tags
    tagged_ips, client_ips, tags = get_all_client_ip()
    
    # Add a dropdown for selecting client_ip
    client_ip_with_tag = st.sidebar.selectbox(
        "Select Client IP",
        options=tagged_ips
    )

    if client_ip_with_tag is None:
        st.error("No client IPs found in the database.")
        return

    # Extract the raw client_ip from the selection
    client_ip = client_ip_with_tag.split(" ")[0]


    # Display current tag and allow modification
    current_tag = tags.get(client_ip, "")

    # st.title(f"{sensor_data_to_store.capitalize()} Data Visualization")
    st.subheader(f"MyShake Experiment ({current_tag}[{client_ip}]: {sensor_data_to_store.capitalize()})")


    new_tag = st.sidebar.text_input("Tag", value=current_tag)

    if st.sidebar.button("Save Tag"):
        add_or_update_tag(client_ip, new_tag)
        st.sidebar.success(f"Tag for {client_ip} updated to '{new_tag}'.")


    # Add a slider for waveform duration
    duration = st.sidebar.slider(
        "Select Duration (seconds)",
        min_value=10,
        max_value=300,
        value=120,
        step=10
    )

    # Add auto-refresh option
    refresh_rate = st.sidebar.slider(
        "Refresh Rate (seconds)",
        min_value=0.5,
        max_value=10.0,
        value=1.0,
        step=0.5
    )

    # A slider for the dominant frequency threshold
    dominant_frequency_threshold = st.sidebar.slider(
        "Frequency Thresh (dB)",
        min_value=-70,
        max_value=0,
        value=-30,
        step=5
    )


    # Create placeholders
    colx, col_hv, coly = st.columns(3)
    with colx:
        location_placeholder = st.empty()
    with col_hv:
        hv_dominant_frequencies_placeholder = st.empty()
    with coly:
        dominant_frequencies_placeholder = st.empty()

    col1, col2 = st.columns(2)
    with col1:
        waveform_placeholder = st.empty()
    with col2:
        spectrogram_placeholder = st.empty()


    try:
        while True:
            # Generate a unique key suffix using the current timestamp
            timestamp_key = int(time.time() * 1000)

            location_info, waveform_fig, spectrogram_figs, dominant_frequencies, hv_dominant_frequency = update_visualization(client_ip, duration, dominant_frequency_threshold)

            dominant_frequencies_str = (
                f"**Freqs (Hz):** X: {format_dominant_frequency(dominant_frequencies['X'])} | "
                f"Y: {format_dominant_frequency(dominant_frequencies['Y'])} | "
                f"Z: {format_dominant_frequency(dominant_frequencies['Z'])}"
            )

            # Update location information
            location_placeholder.markdown(location_info)

            # Update H/V dominant frequency
            hv_dominant_frequencies_placeholder.markdown(f"**H/V Frequency (Hz):** {format_dominant_frequency(hv_dominant_frequency)}")

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
        # print(e)
        st.error("Something went wrong! Please check the logs for more information.")


if __name__ == "__main__":
    main()
