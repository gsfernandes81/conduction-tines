deploy-dev:
	railway environment dev
	railway service conduction-tines
	railway up -d

deploy-prod:
	railway environment production
	railway service conduction-tines
	railway up -d

run-local:
	poetry run honcho start

test:
	poetry run honcho run python -m pytest