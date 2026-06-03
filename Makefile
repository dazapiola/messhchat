.PHONY: install run clean help

PYTHON := python3
VENV := .venv
PIP := $(VENV)/bin/pip
BIN := $(VENV)/bin/python

help:
	@echo ""
	@echo "  MeshChat 🧉 - Comandos disponibles:"
	@echo ""
	@echo "  make install   Crear entorno virtual e instalar dependencias"
	@echo "  make run       Iniciar MeshChat"
	@echo "  make clean     Eliminar entorno virtual"
	@echo ""

install:
	@echo "Creando entorno virtual..."
	$(PYTHON) -m venv $(VENV)
	@echo "Instalando dependencias..."
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements.txt -q
	@echo ""
	@echo "✓ Listo. Ejecutá: make run"

run:
	$(BIN) meshchat_tui.py

clean:
	rm -rf $(VENV)
	@echo "✓ Entorno virtual eliminado."
