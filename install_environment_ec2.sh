#!/bin/bash

# Update package repository
sudo yum update -y

# Install git and tmux
sudo yum install -y git
sudo yum install -y tmux

# Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required Python packages
pip install fastapi uvicorn
pip install plotly
pip install streamlit

# Clone the repository
git clone https://github.com/earthinversion/sensor_logger_app_http_push_server.git

# Print a success message
echo "Instance setup is complete!"