# Project Structure

I reorganized this repository so each folder has a single, clear responsibility.

## Top-Level Layout
- `apps/`: I keep runnable application entrypoints here.
- `tools/`: I keep export and analysis utilities here.
- `scripts/`: I keep repeatable setup/run shell scripts here.
- `assets/`: I keep generated figures and presentation artifacts here.
- `docs/`: I keep operational and maintenance documentation here.

## App Modules
- `apps/postgresql/datacollection_server.py`: I ingest realtime smartphone payloads into PostgreSQL.
- `apps/postgresql/dashboard_streamlit.py`: I serve the realtime PostgreSQL dashboard.
- `apps/sqlite/datacollection_server.py`: I ingest payloads into SQLite for lightweight workflows.
- `apps/sqlite/dashboard_streamlit.py`: I visualize SQLite-based sensor streams.
- `apps/experimental/sensor_basic_server.py`: I keep minimal prototype ingestion logic.

## Tooling Modules
- `tools/export/export_postgres_to_sqlite.py`: I export selected PostgreSQL records into SQLite snapshots.
- `tools/export/export_postgres_to_hdf5.py`: I export PostgreSQL records into HDF5 for scientific workflows.
- `tools/analysis/plot_sqlite_acceleration_data.py`: I generate event-oriented accelerometer plots.
- `tools/analysis/get_hostname.py`: I keep a small utility for host identification.

## Runtime Helpers
- `scripts/setup/install_environment_ec2.sh`: I bootstrap an EC2 machine for this project.
- `scripts/run/run_postgresql_ingestion.sh`: I start the PostgreSQL ingestion app.
- `scripts/run/run_postgresql_dashboard.sh`: I start the PostgreSQL Streamlit dashboard.
- `scripts/run/run_sqlite_ingestion.sh`: I start the SQLite ingestion app.
- `scripts/run/run_sqlite_dashboard.sh`: I start the SQLite Streamlit dashboard.
