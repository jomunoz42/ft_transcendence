NAME := ft_transcendence
COMPOSE_FILE := docker-compose.yml
# docker compose v2 (plugin) if present, docker-compose v1 (standalone) otherwise
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

all: help

help:
	@printf "%s\n" "$(NAME) setup"
	@printf "%s\n" "  make up      Build and start the app once docker-compose.yml exists"
	@printf "%s\n" "  make down    Stop the app containers"
	@printf "%s\n" "  make logs    Follow app container logs"
	@printf "%s\n" "  make status  Show app container status"
	@printf "%s\n" "  make db-check Verify Postgres connects and persists across a restart"
	@printf "%s\n" "  make test    Run the backend test suite"
	@printf "%s\n" "  make migrate Apply outstanding database migrations"
	@printf "%s\n" "  make db-reset DESTRUCTIVE: wipe the database volume and start empty"
	@printf "%s\n" "  make clean   Remove local object/dependency files"

check-compose:
	@test -f "$(COMPOSE_FILE)" || (printf "%s\n" "Missing $(COMPOSE_FILE). Choose the stack before using this target."; exit 1)

up: check-compose
	$(COMPOSE) -f "$(COMPOSE_FILE)" up --build

down: check-compose
	$(COMPOSE) -f "$(COMPOSE_FILE)" down

logs: check-compose
	$(COMPOSE) -f "$(COMPOSE_FILE)" logs -f

status: check-compose
	$(COMPOSE) -f "$(COMPOSE_FILE)" ps

# Wipes the database on purpose: drops the postgres_data volume, then brings
# Postgres back up empty. Run `make migrate` afterwards to recreate the schema.
db-reset: check-compose
	$(COMPOSE) -f "$(COMPOSE_FILE)" down -v
	$(COMPOSE) -f "$(COMPOSE_FILE)" up -d postgres

migrate: check-compose
	$(COMPOSE) -f "$(COMPOSE_FILE)" run --rm backend alembic upgrade head

test: check-compose
	$(COMPOSE) -f "$(COMPOSE_FILE)" run --rm backend pytest

db-check: check-compose
	./database/db-check.sh

clean:
	find . -name '*.o' -delete
	find . -name '*.d' -delete

fclean: clean

re: fclean all

.PHONY: all help up down logs status test migrate db-reset db-check clean fclean re check-compose
