# Operations Guide

I use this guide to run the stack consistently in local and EC2 environments.

## 1. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Start PostgreSQL
```bash
docker compose up -d postgres
```

## 3. Run Ingestion and Dashboard
```bash
python apps/postgresql/datacollection_server.py
```

In another shell:
```bash
streamlit run apps/postgresql/dashboard_streamlit.py --server.port 5000
```

## 4. Use SQLite-Only Mode
```bash
python apps/sqlite/datacollection_server.py
streamlit run apps/sqlite/dashboard_streamlit.py --server.port 5000
```

## 5. Export Data
```bash
python tools/export/export_postgres_to_sqlite.py
python tools/export/export_postgres_to_hdf5.py
```

## 6. Generate Event Plots
```bash
python tools/analysis/plot_sqlite_acceleration_data.py
```

## 7. EC2 Bootstrap Script
```bash
bash scripts/setup/install_environment_ec2.sh
```
