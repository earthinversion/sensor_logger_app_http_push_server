.PHONY: help install run run-postgres run-sqlite postgres-up postgres-down postgres-ingest postgres-dashboard sqlite-ingest sqlite-dashboard export-sqlite export-hdf5

help:
	@echo "Available targets:"
	@echo "  make install            # install Python dependencies"
	@echo "  make run                # run PostgreSQL stack (ingestion + dashboard)"
	@echo "  make run-postgres       # same as run"
	@echo "  make run-sqlite         # run SQLite stack (ingestion + dashboard)"
	@echo "  make postgres-up        # start PostgreSQL container"
	@echo "  make postgres-down      # stop containers"
	@echo "  make export-sqlite      # export PostgreSQL to SQLite"
	@echo "  make export-hdf5        # export PostgreSQL to HDF5"

install:
	pip install -r requirements.txt

run: run-postgres

run-postgres:
	docker compose up -d postgres
	( python apps/postgresql/datacollection_server.py & ) && streamlit run apps/postgresql/dashboard_streamlit.py --server.port 5000

run-sqlite:
	( python apps/sqlite/datacollection_server.py & ) && streamlit run apps/sqlite/dashboard_streamlit.py --server.port 5000

postgres-up:
	docker compose up -d postgres

postgres-down:
	docker compose down

postgres-ingest:
	python apps/postgresql/datacollection_server.py

postgres-dashboard:
	streamlit run apps/postgresql/dashboard_streamlit.py --server.port 5000

sqlite-ingest:
	python apps/sqlite/datacollection_server.py

sqlite-dashboard:
	streamlit run apps/sqlite/dashboard_streamlit.py --server.port 5000

export-sqlite:
	python tools/export/export_postgres_to_sqlite.py

export-hdf5:
	python tools/export/export_postgres_to_hdf5.py
