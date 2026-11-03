# Optional shortcuts. Everything also works with plain `python run_project.py --mode ...`.
.PHONY: test smoke development full
test:
	python -m pytest -q tests
smoke:
	python run_project.py --mode smoke
development:
	python run_project.py --mode development
full:
	python run_project.py --mode full
