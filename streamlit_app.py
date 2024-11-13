from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
from datetime import datetime
import threading
import streamlit as st
import pandas as pd
import time as time_lib

# Shared data storage (deque with max length)
time_queue = deque(maxlen=1000)
accel_x_queue = deque(maxlen=1000)
accel_y_queue = deque(maxlen=1000)
accel_z_queue = deque(maxlen=1000)

# Lock for thread-safe operations
data_lock = threading.Lock()

# FastAPI app for data collection
app = FastAPI()

# Enable CORS for Streamlit to fetch data
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route for receiving sensor data
@app.post("/data")
async def upload_sensor_data(request: Request):
    global time_queue, accel_x_queue, accel_y_queue, accel_z_queue

    try:
        # Parse the incoming JSON data
        data = await request.json()

        # Extract the 'payload' field
        payload = data.get("payload", [])
        if not isinstance(payload, list):
            return {"status": "error", "message": "Invalid payload format"}

        # Process each JSON object in the payload
        with data_lock:  # Use threading.Lock for synchronous access
            for d in payload:
                if d.get("name") in ["accelerometer"]:
                    ts = datetime.fromtimestamp(d["time"] / 1_000_000_000)
                    if len(time_queue) == 0 or ts > time_queue[-1]:
                        time_queue.append(ts)
                        accel_x_queue.append(d["values"]["x"])
                        accel_y_queue.append(d["values"]["y"])
                        accel_z_queue.append(d["values"]["z"])

        return {"status": "success"}

    except Exception as e:
        # Log the error and return a failure response
        return {"status": "error", "message": str(e)}


# Health check
@app.get("/")
def health_check():
    return {"message": "Data collection server is running!"}

# Run FastAPI in a separate thread
def run_fastapi():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=56204)

# Streamlit visualization
def run_streamlit():
    st.title("Real-Time Accelerometer Visualization")
    placeholder = st.empty()

    # Real-time plotting loop
    while True:
        # Convert deque to DataFrame
        with data_lock:
            data = pd.DataFrame({
                "Time": list(time_queue),
                "X": list(accel_x_queue),
                "Y": list(accel_y_queue),
                "Z": list(accel_z_queue),
            })

        # Update the visualization
        with placeholder.container():
            st.line_chart(data.set_index("Time"))

        time_lib.sleep(1)  # Adjust refresh rate

# Run both FastAPI and Streamlit
if __name__ == "__main__":
    # Start FastAPI in a separate thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    # Run Streamlit visualization on port 5000
    run_streamlit()
