import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import logging
import time  # Correct import for time.sleep()

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

sensor_data_to_store = 'accelerometer' #'accelerometer'

# Function to fetch the last 60*50 samples from the database
def get_last_samples(client_ip=None):
    if client_ip is None:
        return pd.DataFrame()
    
    conn = sqlite3.connect(f"sensor_data_{sensor_data_to_store}.db")
    try:
        query = f"""
            SELECT timestamp, x, y, z 
            FROM {sensor_data_to_store}_data 
            WHERE client_ip = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(client_ip, 60 * 50,))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df.sort_values(by="timestamp")  # Ensure data is sorted in ascending order
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# Function to visualize the data
def update_visualization(client_ip, placeholder, plot_key):
    df = get_last_samples(client_ip)
    
    if df.empty:
        placeholder.warning("No data available.")
        return

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        # subplot_titles=("X Component", "Y Component", "Z Component")
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
        # xaxis_title="Time",
        height=600,
        margin=dict(l=40, r=40, t=40, b=40),
        showlegend=False
    )
    fig.update_yaxes(title_text="X", row=1, col=1)
    fig.update_yaxes(title_text="Y", row=2, col=1)
    fig.update_yaxes(title_text="Z", row=3, col=1)

    with placeholder.container():
        st.plotly_chart(fig, use_container_width=True, key=plot_key)

## Get all client_ip in the database
def get_all_client_ip():
    conn = sqlite3.connect(f"sensor_data_{sensor_data_to_store}.db")
    try:
        query = f"""
            SELECT DISTINCT client_ip
            FROM {sensor_data_to_store}_data
        """
        df = pd.read_sql_query(query, conn)
        return df['client_ip'].tolist()
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return []
    finally:
        conn.close()

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

    # Add auto-refresh option
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
    refresh_rate = st.sidebar.slider(
        "Refresh Rate (seconds)",
        min_value=0.1,
        max_value=5.0,
        value=0.5,
        step=0.1
    ) if auto_refresh else None

    try:
        iteration = 0  # To generate unique keys for each plot
        while auto_refresh:
            plot_key = f"plot_{iteration}"  # Generate a unique key for each iteration
            update_visualization(client_ip, placeholder, plot_key)
            # st.sidebar.info(f"Refreshing every {refresh_rate} seconds")
            time.sleep(refresh_rate)
            iteration += 1
    except Exception as e:
        logger.error(f"Error in visualization loop: {e}")
        st.error(f"An error occurred: {str(e)}")

    if not auto_refresh:
        if st.sidebar.button("Refresh Now"):
            update_visualization(client_ip, placeholder, "manual_plot")

if __name__ == "__main__":
    main()
