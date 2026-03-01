SERVER_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))/../Code/Server
IP := $$(hostname -I | awk '{print $$1}')

.PHONY: server server-stop server-restart kill example calibrate test lint check

server:
	cd $(SERVER_DIR) && sudo python3 main.py -t -n

server-stop:
	sudo pkill -f "python3 main.py" || true

server-restart: server-stop
	@sleep 2
	$(MAKE) server

kill:
	sudo pkill -f "python3 main.py" || true
	sudo pkill -f "example.py\|calibrate.py" || true
	@echo "Server and clients stopped."

example:
	uv run python example.py $(IP)

calibrate:
	uv run python calibrate.py $(IP)

test: kill
	@sleep 2
	cd $(SERVER_DIR) && sudo python3 main.py -t -n &
	@sleep 5
	uv run python example.py $(IP)
	sudo pkill -f "python3 main.py" || true
	@echo "Test complete."

lint:
	uv run ruff check src/
	uv run mypy src/

check: lint
	uv run pytest
