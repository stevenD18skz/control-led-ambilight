"""Punto de entrada principal para Control LED Ambilight."""
import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
SRC_DIR = Path(__file__).resolve().parent
BASE_DIR = SRC_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.app import main

if __name__ == "__main__":
    main()
