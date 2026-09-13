.PHONY: load validate orphans review test analytics kpi report dashboard valuation screener peer verify3 verify4 smoke4 nlp proscons cfi capalloc tearsheet sector portfolio verify5 api cluster profile lint format testhtml loadtest perf e2e verify6 clean

load:
	python -m src.etl.load_all

validate:
	python scripts/run_validation.py

orphans:
	python scripts/filter_orphans.py

review:
	python scripts/review_data_quality.py

analytics:
	python -m src.analytics.engine

kpi:
	python -m pytest tests/kpi -v

test:
	python -m pytest tests -v

screener:
	python -m src.screener.engine

peer:
	python -m src.analytics.peer

verify3:
	python scripts/verify_sprint3.py

report:
	python -m src.report

dashboard:
	python -m streamlit run src/dashboard/app.py

valuation:
	python -m src.analytics.valuation

verify4:
	python scripts/verify_sprint4.py

smoke4:
	python -m scripts.dev_smoke_dashboard

nlp:
	python -m src.nlp.parser && python -m src.nlp.pros_cons_generator

proscons:
	python -m src.nlp.pros_cons_generator

cfi:
	python -m src.analytics.cashflow_kpis

capalloc:
	python -m src.analytics.capital_allocation_report

tearsheet:
	python -m src.reports.tearsheet --all

sector:
	python -m src.reports.sector_report

portfolio:
	python -m src.reports.portfolio_report

verify5:
	python scripts/verify_sprint5.py

cluster:
	python -m src.analytics.clustering && python -m src.analytics.descriptive

profile:
	python scripts/build_analyst_guide.py

api:
	python -m uvicorn src.api.main:app --reload --port 8000

testapi:
	python -m pytest tests/api -v

testhtml:
	python -m pytest tests --html=reports/pytest_report.html --self-contained-html

lint:
	python -m black src tests scripts --check
	python -m ruff check .

loadtest:
	python scripts/load_test_api.py

perf:
	python scripts/perf_dashboard.py

e2e:
	python scripts/e2e_endpoints.py

verify6:
	python scripts/verify_sprint6.py

clean:
	python -c "import shutil; shutil.rmtree('__pycache__', ignore_errors=True); shutil.rmtree('.pytest_cache', ignore_errors=True)"
