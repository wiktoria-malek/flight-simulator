.PHONY: help install check BBA_GUI ComputeResponseMatrix_GUI SysID_GUI

help:
	@echo "Flight-simulator (Poetry) - commands:"
	@echo ""
	@echo "  make install                     Install dependencies"
	@echo ""
	@echo "Run tools:"
	@echo "  make BBA                     Run BBA_GUI.py"
	@echo "  make CRM   Run ComputeResponseMatrix_GUI.py"
	@echo "  make SysID                   Run SysID_GUI.py"
	@echo ""

install:
	poetry install --no-root

check: install
	poetry run python -c "import numpy, matplotlib; import PyQt6;"

BBA: install
	poetry run python BBA_GUI.py

CRM: install
	poetry run python ComputeResponseMatrix_GUI.py

SysID: install
	poetry run python SysID_GUI.py