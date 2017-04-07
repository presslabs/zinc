.DEFAULT_GOAL := build

test:
	py.test -v -n auto --capture=no --no-migrations -k 'not with_aws' --flake8
full-test:
	py.test -v         --capture=no --color=yes
lint:
	py.test -v -n auto --capture=no --color=yes --flake8 -m 'flake8'
run:
	@echo "#################################################################"
	@echo "#                                                               #"
	@echo "# Run 'make run-celery' in order to start the background worker #"
	@echo "#                                                               #"
	@echo "#################################################################"
	python ./manage.py runserver
run-celery:
	celery worker -A django_project -B
build:
	@echo "There is nothing to build for this project"
seed:
	python ./manage.py migrate --no-input
	python ./manage.py seed
.PHONY: test full-test run build lint seed
