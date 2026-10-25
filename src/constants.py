"""Constantes globales, rutas y temas visuales para la aplicación."""
from pathlib import Path

# Rutas del proyecto
SRC_DIR = Path(__file__).resolve().parent
BASE_DIR = SRC_DIR.parent
ASSETS_DIR = BASE_DIR / "assets"
CONFIG_PATH = BASE_DIR / "config.json"
LOG_PATH = BASE_DIR / "led_control.log"

ICON_ICO_PATH = ASSETS_DIR / "icon.ico"
ICON_PNG_PATH = ASSETS_DIR / "icon.png"
ICON_TRAY_PATH = ASSETS_DIR / "icon_tray.png"

# Colores de la interfaz (Tema oscuro premium)
BG = "#13151b"
PANEL = "#1d212c"
PANEL_HOVER = "#272c3b"
PANEL_ACTIVE = "#32384a"
CARD_BG = "#191c25"
CARD_BORDER = "#252a36"
FG = "#eef0f5"
MUTED = "#868c9b"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"
SUCCESS = "#10b981"
SUCCESS_HOVER = "#059669"

# Fuentes
FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI Semibold", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI Semibold", 13)

# Diccionario de estados BLE
STATUS = {
    "conectado": ("#10b981", "Conectado"),
    "conectando": ("#f0b429", "Conectando"),
    "buscando": ("#f0b429", "Buscando"),
    "reconectando": ("#f0b429", "Reconectando"),
    "error": ("#ef5350", "Sin conexión"),
}

# Paleta de colores preestablecidos (Presets)
PRESETS = [
    "#ff0000", "#ff8c00", "#ffff00", "#00ff00", "#00ffff",
    "#0000ff", "#a000ff", "#ff0078", "#ffffff"
]

# Efectos decorativos
OTHER_EFFECTS = [
    ("desvanecido", "Desvanecido"),
    ("respiracion", "Respiración"),
    ("arcoiris", "Arcoíris")
]
