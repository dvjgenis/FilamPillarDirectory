.PHONY: dev install test

dev: install
	streamlit run app.py

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v
