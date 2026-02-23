from fastapi import FastAPI, HTTPException, Request
import os
import json

app = FastAPI()

# Base directory to store incoming data
DATA_DIR = "sensor_data"
os.makedirs(DATA_DIR, exist_ok=True)

@app.post("/data")
async def upload_sensor_data(request: Request):
    try:
        # Get JSON data from the POST request
        sensor_data = await request.json()

        if not sensor_data:
            raise HTTPException(status_code=400, detail="No JSON data received")

        # Extract the client's IP address
        client_ip = request.client.host

        # Create a directory for the client IP
        client_dir = os.path.join(DATA_DIR, client_ip)
        os.makedirs(client_dir, exist_ok=True)

        # Save data to a file in the client's directory
        filename = os.path.join(client_dir, f"sensor_{sensor_data.get('device_id', 'unknown')}.json")
        with open(filename, 'a') as file:
            file.write(json.dumps(sensor_data) + '\n')

        return {"message": "Data received successfully"}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def health_check():
    return {"message": "Server is running!"}

if __name__ == "__main__":
    import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=5000)
    uvicorn.run(app, host="0.0.0.0", port=56204)
