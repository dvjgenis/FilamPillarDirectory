.PHONY: dev dev-sheets dev-sample sync-secrets pregeocode install test

dev: install
	streamlit run app.py

# Google Sheets — uses .streamlit/secrets.toml (run make sync-secrets after key changes)
dev-sheets: install sync-secrets
	CHURCH_DATA_SOURCE=sheets $(if $(SHEET_ID),CHURCH_SHEET_ID=$(SHEET_ID),) streamlit run app.py

dev-sample: install
	CHURCH_CSV_PATH=data/sample_directory.csv streamlit run app.py

sync-secrets:
	python scripts/sync_streamlit_secrets.py

pregeocode:
	python scripts/pregeocode.py

pregeocode-secrets:
	python scripts/pregeocode.py --print-secrets

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v
