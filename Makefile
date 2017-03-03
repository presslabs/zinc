test:
	py.test -v -n auto --capture=no --no-migrations -k 'not with_aws' --flake8
full-test:
	py.test -v         --capture=no --color=yes
lint:
	py.test -v -n auto --capture=no --color=yes --flake8 -m 'flake8'
run:
	@echo "##########################################################################"
	@echo "#                                                                        #"
	@echo "# Run 'celery worker -A zinc -B' in order to start the background worker #"
	@echo "#                                                                        #"
	@echo "##########################################################################"
	python ./manage.py runserver
build:
	@echo "There is nothing to build for this project"
seed:
	@echo "This project has no seeding yet"

.PHONY: test full-test run build lint seed
