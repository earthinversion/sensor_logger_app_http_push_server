#!/bin/bash

set -e

# I keep this script focused on a clean EC2 bootstrap for this repository.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

sudo yum update -y

sudo yum install -y git tmux docker

sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user

if [ ! -d "$HOME/venv" ]; then
    python3 -m venv ~/venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi
source ~/venv/bin/activate

pip install --upgrade pip
pip install -r "${ROOT_DIR}/requirements.txt"

echo "Environment setup is complete."
