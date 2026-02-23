#!/bin/bash

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

source /home/ec2-user/venv/bin/activate
python "${ROOT_DIR}/apps/postgresql/datacollection_server.py"
