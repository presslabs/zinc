test:
	py.test -v --no-migrations -k 'not with_aws'
full-test:
	py.test -v
run:
	@echo "##########################################################################"
	@echo "#                                                                        #"
	@echo "# Run 'celery worker -A zinc -B' in order to start the background worker #"
	@echo "#                                                                        #"
	@echo "##########################################################################"
	python ./manage.py runserver
build:
	@echo "There is nothing to build for this project"
lint:
	py.test -v --flake8 -m 'flake8'
seed:
	@echo "This project has no seeding yet"

.PHONY: test full-test run build lint seed
