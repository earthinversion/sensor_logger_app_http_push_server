from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
from datetime import datetime
import threading
import streamlit as st
import pandas as pd
import time as time_lib
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Define the total number of data points for visualization
data_length_to_display = 60  # seconds
sampling_rate = 50  # Hz
total_data_points = data_length_to_display * sampling_rate

# Initialize Streamlit state to persist data across script executions
if "time_queue" not in st.session_state:
    st.session_state.time_queue = deque(maxlen=total_data_points)
    st.session_state.accel_x_queue = deque(maxlen=total_data_points)
    st.session_state.accel_y_queue = deque(maxlen=total_data_points)
    st.session_state.accel_z_queue = deque(maxlen=total_data_points)

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
                    if len(st.session_state.time_queue) == 0 or ts > st.session_state.time_queue[-1]:
                        st.session_state.time_queue.append(ts)
                        st.session_state.accel_x_queue.append(d["values"]["x"])
                        st.session_state.accel_y_queue.append(d["values"]["y"])
                        st.session_state.accel_z_queue.append(d["values"]["z"])

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
    refresh_rate = 0.5  # Refresh rate in seconds

    # Create a placeholder for the plot
    placeholder = st.empty()

    while True:
        # Convert deque to DataFrame
        with data_lock:
            data = pd.DataFrame({
                "Time": list(st.session_state.time_queue),
                "X": list(st.session_state.accel_x_queue),
                "Y": list(st.session_state.accel_y_queue),
                "Z": list(st.session_state.accel_z_queue),
            })

        # Render only if there is data
        if not data.empty:
            # Ensure Time is in datetime format for Plotly
            data["Time"] = pd.to_datetime(data["Time"])

            # Create a Plotly figure with subplots
            fig = make_subplots(
                rows=3, cols=1, shared_xaxes=True,
                vertical_spacing=0.02,
                subplot_titles=("X Component", "Y Component", "Z Component")
            )

            # Add X component
            fig.add_trace(
                go.Scatter(x=data["Time"], y=data["X"], mode="lines", line=dict(color="red")),
                row=1, col=1
            )

            # Add Y component
            fig.add_trace(
                go.Scatter(x=data["Time"], y=data["Y"], mode="lines", line=dict(color="green")),
                row=2, col=1
            )

            # Add Z component
            fig.add_trace(
                go.Scatter(x=data["Time"], y=data["Z"], mode="lines", line=dict(color="blue")),
                row=3, col=1
            )

            # Update layout
            fig.update_layout(
                xaxis_title="Time",
                height=600,
                margin=dict(l=40, r=40, t=40, b=40),
                showlegend=False
            )
            fig.update_yaxes(title_text="X", row=1, col=1)
            fig.update_yaxes(title_text="Y", row=2, col=1)
            fig.update_yaxes(title_text="Z", row=3, col=1)

            # Update the plot in the placeholder
            with placeholder.container():
                st.plotly_chart(fig, use_container_width=True)

        # Sleep for the refresh rate
        time_lib.sleep(refresh_rate)


# Run both FastAPI and Streamlit
if __name__ == "__main__":
    # Start FastAPI in a separate thread
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    # Run Streamlit visualization
    run_streamlit()
