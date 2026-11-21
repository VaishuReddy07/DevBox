.PHONY: up down logs seed reset clean

up:
	bash scripts/devbox up

down:
	bash scripts/devbox down

logs:
	bash scripts/devbox logs

seed:
	bash scripts/devbox seed

reset:
	bash scripts/devbox reset

clean:
	bash scripts/devbox clean
