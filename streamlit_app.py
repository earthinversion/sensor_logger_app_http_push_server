from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
from datetime import datetime, timedelta
import threading
import streamlit as st
import pandas as pd
import time as time_lib
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
import json

# Database configuration
DB_NAME = "sensor_data.db"

def init_database():
    """Initialize SQLite database with required table"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accelerometer_data (
            timestamp DATETIME PRIMARY KEY,
            x REAL,
            y REAL,
            z REAL
        )
    ''')
    conn.commit()
    conn.close()

# Shared data storage (deque with max length)
data_length_to_display = 60  # seconds
sampling_rate = 50  # Hz
total_data_points = data_length_to_display * sampling_rate

# Global variables for data storage
class DataStore:
    def __init__(self):
        self.time_queue = deque(maxlen=total_data_points)
        self.accel_x_queue = deque(maxlen=total_data_points)
        self.accel_y_queue = deque(maxlen=total_data_points)
        self.accel_z_queue = deque(maxlen=total_data_points)
        self.data_lock = threading.Lock()
        self.last_fetch_time = None
        self.selected_time_range = 1  # Default 1 minute

data_store = DataStore()

# FastAPI app
app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def store_data_in_db(timestamp, x, y, z):
    """Store sensor data in SQLite database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO accelerometer_data (timestamp, x, y, z) VALUES (?, ?, ?, ?)",
            (timestamp, x, y, z)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Ignore duplicate timestamps
    finally:
        conn.close()

def get_historical_data(start_time):
    """Fetch historical data from SQLite database"""
    conn = sqlite3.connect(DB_NAME)
    try:
        df = pd.read_sql_query("""
            SELECT timestamp, x, y, z 
            FROM accelerometer_data 
            WHERE timestamp > ? 
            ORDER BY timestamp ASC
        """, conn, params=(start_time.isoformat(),))
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    finally:
        conn.close()

@app.post("/data")
async def upload_sensor_data(request: Request):
    try:
        data = await request.json()
        payload = data.get("payload", [])
        
        if not isinstance(payload, list):
            return {"status": "error", "message": "Invalid payload format"}

        with data_store.data_lock:
            for d in payload:
                if d.get("name") in ["accelerometer"]:
                    ts = datetime.fromtimestamp(d["time"] / 1_000_000_000)
                    x, y, z = d["values"]["x"], d["values"]["y"], d["values"]["z"]
                    
                    # Store in database
                    store_data_in_db(ts, x, y, z)
                    
                    # Update deque if it's recent data
                    if len(data_store.time_queue) == 0 or ts > data_store.time_queue[-1]:
                        data_store.time_queue.append(ts)
                        data_store.accel_x_queue.append(x)
                        data_store.accel_y_queue.append(y)
                        data_store.accel_z_queue.append(z)

        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def health_check():
    return {"message": "Data collection server is running!"}

def run_fastapi():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=56204)

def update_visualization(placeholder, time_range):
    """Update the visualization with current data and historical data if needed"""
    current_time = datetime.now()
    
    # Get current data from deque
    with data_store.data_lock:
        current_data = pd.DataFrame({
            "Time": list(data_store.time_queue),
            "X": list(data_store.accel_x_queue),
            "Y": list(data_store.accel_y_queue),
            "Z": list(data_store.accel_z_queue),
        })

    # If historical data is requested, fetch from database
    if time_range * 60 > data_length_to_display:
        start_time = current_time - timedelta(minutes=time_range)
        
        # Only fetch new historical data if needed
        if (data_store.last_fetch_time is None or 
            data_store.last_fetch_time < start_time or 
            data_store.selected_time_range != time_range):
            
            historical_data = get_historical_data(start_time)
            data_store.last_fetch_time = current_time
            data_store.selected_time_range = time_range
            
            # Combine historical data with current data
            if not current_data.empty:
                # Remove overlapping data points
                historical_data = historical_data[
                    historical_data['timestamp'] < current_data['Time'].iloc[0]
                ]
                data = pd.concat([
                    historical_data.rename(columns={
                        'timestamp': 'Time',
                        'x': 'X',
                        'y': 'Y',
                        'z': 'Z'
                    }),
                    current_data
                ])
            else:
                data = historical_data.rename(columns={
                    'timestamp': 'Time',
                    'x': 'X',
                    'y': 'Y',
                    'z': 'Z'
                })
        else:
            data = current_data
    else:
        data = current_data

    if not data.empty:
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            subplot_titles=("X Component", "Y Component", "Z Component")
        )

        fig.add_trace(
            go.Scatter(x=data["Time"], y=data["X"], mode="lines", line=dict(color="red")),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=data["Time"], y=data["Y"], mode="lines", line=dict(color="green")),
            row=2, col=1
        )
        fig.add_trace(
            go.Scatter(x=data["Time"], y=data["Z"], mode="lines", line=dict(color="blue")),
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
            st.plotly_chart(fig, use_container_width=True, key=f"plot-{time_lib.time()}")

def run_streamlit():
    st.title("Real-Time Accelerometer Visualization")
    
    # Create a placeholder for the plot
    placeholder = st.empty()
    
    # Add time range selector in sidebar
    time_range = st.sidebar.slider(
        "Historical Data (minutes)",
        min_value=1,
        max_value=60,
        value=1,
        key="time_range"
    )
    
    refresh_rate = 0.5  # Refresh rate in seconds

    while True:
        update_visualization(placeholder, time_range)
        time_lib.sleep(refresh_rate)

if __name__ == "__main__":
    # Initialize database
    init_database()
    
    # Start FastAPI in a separate thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    # Run Streamlit visualization
    run_streamlit()