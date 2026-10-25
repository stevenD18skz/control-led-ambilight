"""Módulo de captura y cálculo del color de la pantalla (Ambilight)."""
import colorsys
import mss
import numpy as np

SAMPLE_STEP = 20        # toma 1 de cada 20 píxeles en cada eje
BLACK_CUTOFF = 0.08     # ignora píxeles casi negros (bordes de películas, fondos oscuros)
SATURATION_BOOST = 1.3  # refuerzo de viveza del color
MIN_LEVEL = 0.15        # brillo mínimo para no apagar el ambiente del todo


def get_monitors_info():
    """Devuelve la lista de monitores físicos disponibles [(index, width, height), ...]."""
    try:
        with mss.MSS() as sct:
            info = []
            for i, m in enumerate(sct.monitors):
                if i == 0:
                    continue  # El monitor 0 es la combinación de todas las pantallas
                info.append((i, m.get("width", 0), m.get("height", 0)))
            return info if info else [(1, 1920, 1080)]
    except Exception:
        return [(1, 1920, 1080)]


class ScreenSampler:
    """Muestreador de pantalla. Usar siempre desde el mismo hilo (mss guarda recursos por hilo)."""

    def __init__(self, monitor=1, zone="all"):
        self._monitor = monitor
        self._zone = zone
        self._sct = None

    def sample(self):
        if self._sct is None:
            self._sct = mss.MSS()
        mon_idx = self._monitor if self._monitor < len(self._sct.monitors) else 1
        shot = self._sct.grab(self._sct.monitors[mon_idx])

        # BGRA -> RGB, submuestreado, normalizado en 0..1
        pixels = np.frombuffer(shot.bgra, np.uint8).reshape(shot.height, shot.width, 4)
        img = pixels[::SAMPLE_STEP, ::SAMPLE_STEP, 2::-1].astype(np.float32) / 255

        if self._zone == "borders":
            # Extraer bordes exteriores (20% del perímetro)
            h, w = img.shape[:2]
            pad_y, pad_x = max(1, int(h * 0.2)), max(1, int(w * 0.2))
            mask = np.ones((h, w), dtype=bool)
            mask[pad_y:h - pad_y, pad_x:w - pad_x] = False
            img_pixels = img[mask]
            value = img_pixels.max(axis=1)
            saturation = (value - img_pixels.min(axis=1)) / (value + 1e-6)
            weight = (saturation ** 2 * value + 0.02) * (value > BLACK_CUTOFF)
            if weight.sum() < 1e-6:
                return (0, 0, 0)
            r, g, b = (img_pixels * weight[..., None]).sum(axis=0) / weight.sum()
        elif self._zone == "bottom":
            # Extraer la franja inferior (35% inferior, ideal para luces bajo el escritorio)
            h = img.shape[0]
            start_y = int(h * 0.65)
            img_slice = img[start_y:, :]
            value = img_slice.max(axis=2)
            saturation = (value - img_slice.min(axis=2)) / (value + 1e-6)
            # Ignora automáticamente barras negras de películas (value > BLACK_CUTOFF)
            weight = (saturation ** 2 * value + 0.02) * (value > BLACK_CUTOFF)
            if weight.sum() < 1e-6:
                # Si la franja del 35% está en negro absoluto (ej. barra negra ancha de película),
                # amplía la captura a la mitad inferior de la pantalla para mantener luz
                img_slice = img[int(h * 0.5):, :]
                value = img_slice.max(axis=2)
                saturation = (value - img_slice.min(axis=2)) / (value + 1e-6)
                weight = (saturation ** 2 * value + 0.02) * (value > BLACK_CUTOFF)
                if weight.sum() < 1e-6:
                    return (0, 0, 0)
            r, g, b = (img_slice * weight[..., None]).sum(axis=(0, 1)) / weight.sum()
        else:
            value = img.max(axis=2)
            saturation = (value - img.min(axis=2)) / (value + 1e-6)
            # Los píxeles vivos y brillantes pesan mucho más que los grises
            weight = (saturation ** 2 * value + 0.02) * (value > BLACK_CUTOFF)
            if weight.sum() < 1e-6:
                return (0, 0, 0)
            r, g, b = (img * weight[..., None]).sum(axis=(0, 1)) / weight.sum()

        h, s, _ = colorsys.rgb_to_hsv(r, g, b)
        level = max(MIN_LEVEL, min(1.0, float(value.mean()) * 2))
        rgb = colorsys.hsv_to_rgb(h, min(1.0, s * SATURATION_BOOST), level)
        return tuple(round(c * 255) for c in rgb)

    def close(self):
        if self._sct is not None:
            self._sct.close()
            self._sct = None
