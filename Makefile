COMPOSE = docker compose --env-file .env -f docker/docker-compose.yml
.PHONY: env setup sample demo dashboard test lint up init app produce down logs

env:        ## create .env with random secrets
	python scripts/make_env.py
setup:      ## install everything for development
	pip install -r requirements-dev.txt
sample:     ## generate a 200k-row PaySim-format sample
	python scripts/generate_sample_data.py --rows 200000
demo: sample ## run the whole scoring logic in-process (no Docker) and open the dashboard
	PYTHONPATH=. python scripts/run_local_demo.py && PYTHONPATH=. streamlit run dashboard/app.py
dashboard:
	PYTHONPATH=. streamlit run dashboard/app.py
test:
	python -m pytest -q
lint:
	ruff check .
up:         ## start Kafka + ClickHouse, create topics, tables, views, roles
	$(COMPOSE) up -d --build zookeeper kafka clickhouse topics-init db-init
app:        ## also start consumer + dashboard containers
	$(COMPOSE) --profile app up -d --build
produce:    ## stream the sample file into Kafka
	$(COMPOSE) run --rm producer
down:
	$(COMPOSE) --profile app --profile producer down
logs:
	$(COMPOSE) logs -f consumer
