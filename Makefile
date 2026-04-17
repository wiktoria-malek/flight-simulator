.PHONY: help install check fix-qt-macos BBA_GUI ComputeResponseMatrix_GUI SysID_GUI Emittance

help:
	@echo "Flight-simulator (Poetry) - commands:"
	@echo ""
	@echo "  make install                     Install dependencies"
	@echo "  make fix-qt-macos                Clear macOS hidden flags that break Qt plugins"
	@echo ""
	@echo "Run tools:"
	@echo "  make BBA                     Run BBA_GUI.py"
	@echo "  make CRM   Run ComputeResponseMatrix_GUI.py"
	@echo "  make SysID                   Run SysID_GUI.py"
	@echo "  make Emittance               Run Emittance_Measurement_GUI.py"
	@echo ""

install:
	poetry install --no-root

fix-qt-macos:
	@if [ "$$(uname)" = "Darwin" ] && [ -d .venv ]; then chflags -R nohidden .venv; fi

check: install fix-qt-macos
	poetry run python -c "import numpy, matplotlib; import PyQt6;"

BBA: install fix-qt-macos
	poetry run python BBA_GUI.py

CRM: install fix-qt-macos
	poetry run python ComputeResponseMatrix_GUI.py

SysID: install fix-qt-macos
	poetry run python SysID_GUI.py

Emittance: install fix-qt-macos
	poetry run python Emittance_Measurement_GUI.py
