.PHONY: build-web-visualizer, build-pypi, build, run-local, test, pytest, pytest-docker

VERSION ?= local

build-web-visualizer:
	cd web-visualizer && \
		npm install && \
		npm run build

build-pypi: build-web-visualizer
	@hatch build

build: test build-pypi
	@docker build --platform=linux/amd64 \
		-t solace/solace-agent-mesh:${VERSION} .

run-local:
	@docker-compose -f docker-compose-local.yaml run \
		--rm solace-agent-mesh

test:
	@python3 run_tests.py

pytest:
	@pytest

pytest-docker:
	@docker run --rm --entrypoint pytest solace/solace-agent-mesh:${VERSION}