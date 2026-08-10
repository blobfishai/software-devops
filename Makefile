.PHONY: build test serve docker-build docker-run

build:
	python3 build/build_world.py

test:
	python3 -m pytest tests/ -q

serve:
	python3 serve.py --world world --port 8080

docker-build:
	docker build -t software-devops-world .

docker-run: docker-build
	docker run --rm -p 8080:8080 software-devops-world
