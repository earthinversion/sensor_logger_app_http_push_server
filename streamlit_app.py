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

time_queue = deque(maxlen=total_data_points)
accel_x_queue = deque(maxlen=total_data_points)
accel_y_queue = deque(maxlen=total_data_points)
accel_z_queue = deque(maxlen=total_data_points)

# Lock for thread-safe operations
data_lock = threading.Lock()

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
    cursor.execute(
        "INSERT INTO accelerometer_data (timestamp, x, y, z) VALUES (?, ?, ?, ?)",
        (timestamp, x, y, z)
    )
    conn.commit()
    conn.close()

def load_initial_data():
    """Load the most recent data from SQLite into deque"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Calculate the timestamp threshold for loading data
    threshold_time = datetime.now() - timedelta(seconds=data_length_to_display)
    
    cursor.execute("""
        SELECT timestamp, x, y, z 
        FROM accelerometer_data 
        WHERE timestamp > ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    """, (threshold_time, total_data_points))
    
    rows = cursor.fetchall()
    conn.close()
    
    with data_lock:
        for row in reversed(rows):  # Reverse to maintain chronological order
            timestamp = datetime.fromisoformat(row[0])
            time_queue.append(timestamp)
            accel_x_queue.append(row[1])
            accel_y_queue.append(row[2])
            accel_z_queue.append(row[3])

@app.post("/data")
async def upload_sensor_data(request: Request):
    try:
        data = await request.json()
        payload = data.get("payload", [])
        
        if not isinstance(payload, list):
            return {"status": "error", "message": "Invalid payload format"}

        with data_lock:
            for d in payload:
                if d.get("name") in ["accelerometer"]:
                    ts = datetime.fromtimestamp(d["time"] / 1_000_000_000)
                    x, y, z = d["values"]["x"], d["values"]["y"], d["values"]["z"]
                    
                    # Store in database
                    store_data_in_db(ts, x, y, z)
                    
                    # Update deque if it's recent data
                    if len(time_queue) == 0 or ts > time_queue[-1]:
                        time_queue.append(ts)
                        accel_x_queue.append(x)
                        accel_y_queue.append(y)
                        accel_z_queue.append(z)

        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
def health_check():
    return {"message": "Data collection server is running!"}

def run_fastapi():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=56204)

def get_historical_data(start_time):
    """Fetch historical data from SQLite database"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("""
        SELECT timestamp, x, y, z 
        FROM accelerometer_data 
        WHERE timestamp > ? 
        ORDER BY timestamp ASC
    """, conn, params=(start_time,))
    conn.close()
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

def run_streamlit():
    st.title("Real-Time Accelerometer Visualization")
    refresh_rate = 0.5  # Refresh rate in seconds

    # Add time range selector
    time_range = st.sidebar.slider(
        "Historical Data (minutes)",
        min_value=1,
        max_value=60,
        value=data_length_to_display // 60
    )

    placeholder = st.empty()

    while True:
        # Get current data from deque
        with data_lock:
            current_data = pd.DataFrame({
                "Time": list(time_queue),
                "X": list(accel_x_queue),
                "Y": list(accel_y_queue),
                "Z": list(accel_z_queue),
            })

        # If historical data is requested, fetch from database
        if time_range * 60 > data_length_to_display:
            start_time = datetime.now() - timedelta(minutes=time_range)
            historical_data = get_historical_data(start_time)
            
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

        time_lib.sleep(refresh_rate)

if __name__ == "__main__":
    # Initialize database
    init_database()
    
    # Load initial data from database into deque
    load_initial_data()
    
    # Start FastAPI in a separate thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    # Run Streamlit visualization
    run_streamlit()