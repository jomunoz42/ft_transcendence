NAME := ft_transcendence
COMPOSE_FILE := docker-compose.yml

all: help

help:
	@printf "%s\n" "$(NAME) setup"
	@printf "%s\n" "  make up      Build and start the app once docker-compose.yml exists"
	@printf "%s\n" "  make down    Stop the app containers"
	@printf "%s\n" "  make logs    Follow app container logs"
	@printf "%s\n" "  make status  Show app container status"
	@printf "%s\n" "  make clean   Remove local object/dependency files"

check-compose:
	@test -f "$(COMPOSE_FILE)" || (printf "%s\n" "Missing $(COMPOSE_FILE). Choose the stack before using this target."; exit 1)

up: check-compose
	docker compose -f "$(COMPOSE_FILE)" up --build

down: check-compose
	docker compose -f "$(COMPOSE_FILE)" down

logs: check-compose
	docker compose -f "$(COMPOSE_FILE)" logs -f

status: check-compose
	docker compose -f "$(COMPOSE_FILE)" ps

clean:
	find . -name '*.o' -delete
	find . -name '*.d' -delete

fclean: clean

re: fclean all

.PHONY: all help up down logs status clean fclean re check-compose
