#!/bin/bash

set -e


source /home/ec2-user/venv/bin/activate
python fastapi_datacollection.py

# Run the visualization script

