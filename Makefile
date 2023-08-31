deploy-dev:
	railway environment dev
	railway service conduction-tines
	railway up -d

deploy-prod:
	railway environment production
	railway service conduction-tines
	railway up -d

run-local: .env
	poetry run honcho start

test: .env
	poetry run honcho run python -m pytest

.env:
	@echo "Please create a .env file with all variables as per polarity.cfg"
	@echo "and .env-example to be able to run this locally. Note that all"
	@echo "variables are required and the example values are not valid but"
	@echo "are there to show the approximate format of values."
	@exit 1
