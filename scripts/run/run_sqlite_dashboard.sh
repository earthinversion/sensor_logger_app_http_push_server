#!/bin/bash

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

source /home/ec2-user/venv/bin/activate
streamlit run "${ROOT_DIR}/apps/sqlite/dashboard_streamlit.py" --server.port 5000
