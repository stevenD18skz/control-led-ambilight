"""Control BLE de luces MohuanLED (BJ_LED_M): protocolo, reconexión automática y efectos."""
import asyncio
import colorsys
import json
import logging
import math
from concurrent.futures import ThreadPoolExecutor

from bleak import BleakClient, BleakScanner

from .constants import CONFIG_PATH
from .sampler import ScreenSampler

log = logging.getLogger("led")

WRITE_UUID = "0000ee02-0000-1000-8000-00805f9b34fb"
DEVICE_NAME = "bj_led_m"

FRAME_INTERVAL = 0.04   # ~25 comandos de color por segundo como máximo
SCAN_TIMEOUT = 10
CONNECT_TIMEOUT = 15
FAILS_BEFORE_SCAN = 3   # tras N fallos con la MAC guardada, vuelve a escanear
SCREEN_INTERVAL = 0.1   # pausa entre capturas de pantalla (~10 por segundo)

# Efectos que reemplazan el color manual fijo
COLOR_OVERRIDING_EFFECTS = ("desvanecido", "arcoiris", "pantalla")

FADE_PALETTE = [(255, 0, 0), (255, 140, 0), (255, 255, 0), (0, 255, 0),
                (0, 255, 255), (0, 0, 255), (160, 0, 255), (255, 0, 120)]


def cmd_power(on):
    return bytes.fromhex("69 96 02 01") + bytes([1 if on else 0])


def cmd_color(r, g, b):
    return bytes.fromhex("69 96 05 02") + bytes([r, g, b])


def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def scale(rgb, factor):
    return tuple(max(0, min(255, round(c * factor))) for c in rgb)


def hue_to_rgb(hue):
    return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(hue, 1, 1))


class LedController:
    def __init__(self, loop, on_status):
        self._loop = loop
        self._on_status = on_status  # on_status(estado, detalle)
        self.config = load_config()
        self.power = self.config.get("power", True)
        self.color = tuple(self.config.get("color", (255, 255, 255)))
        self.brightness = self.config.get("brightness", 1.0)
        self.speed = self.config.get("speed", 1.0)
        self.screen_monitor = self.config.get("screen_monitor", 1)
        self.screen_zone = self.config.get("screen_zone", "all")
        self.effect = self.config.get("effect", "pantalla")  # Por defecto siempre Modo Pantalla activado

        self._client = None
        self._fails = 0
        self._closing = False
        self._resend = True
        self._frame = self._static_frame()
        self._dirty = asyncio.Event()         # hay un nuevo frame para mandar
        self._disconnected = asyncio.Event()  # se perdió la conexión BLE
        self._tasks = []
        self._effect_task = None

    # ---------- API pública ----------

    def call(self, fn, *args):
        """Ejecuta fn(*args) dentro del bucle asyncio (seguro desde cualquier hilo)."""
        self._loop.call_soon_threadsafe(fn, *args)

    def set_power(self, on):
        self.power = on
        self._dirty.set()

    def set_color(self, rgb):
        self.color = tuple(rgb)
        if self.effect in COLOR_OVERRIDING_EFFECTS:
            self.set_effect(None)
        self._refresh()

    def set_brightness(self, value):
        self.brightness = value
        self._refresh()

    def set_speed(self, value):
        self.speed = value

    def set_screen_monitor(self, monitor):
        self.screen_monitor = int(monitor)
        if self.effect == "pantalla":
            self.set_effect("pantalla")
        self.save_settings()

    def set_screen_zone(self, zone):
        self.screen_zone = zone
        if self.effect == "pantalla":
            self.set_effect("pantalla")
        self.save_settings()

    def set_effect(self, name):
        if self._effect_task:
            self._effect_task.cancel()
            self._effect_task = None
        if self.effect == "pantalla" and name != "pantalla" and self._on_status:
            self._on_status("screen_color", None)
        self.effect = name
        if name == "pantalla":
            self._effect_task = asyncio.create_task(self._run_screen())
        elif name:
            self._effect_task = asyncio.create_task(self._run_effect(name))
        self._refresh()

    def forget_device(self):
        """Olvida la MAC guardada y vuelve a escanear."""
        self.config.pop("mac", None)
        save_config(self.config)
        self._fails = 0
        if self._client and self._client.is_connected:
            asyncio.create_task(self._client.disconnect())

    def save_settings(self):
        self.config.update(
            power=self.power,
            color=list(self.color),
            brightness=self.brightness,
            speed=self.speed,
            screen_monitor=self.screen_monitor,
            screen_zone=self.screen_zone,
            effect=self.effect,
        )
        save_config(self.config)

    async def start(self):
        self._tasks = [asyncio.create_task(self._connection_loop()),
                       asyncio.create_task(self._writer_loop())]
        if self.effect:
            self.set_effect(self.effect)

    async def shutdown(self):
        self._closing = True
        self.set_effect(None)
        for task in self._tasks:
            task.cancel()
        self.save_settings()
        if self._client and self._client.is_connected:
            await self._client.disconnect()

    # ---------- Conexión ----------

    def _status(self, state, detail=""):
        log.info("%s: %s", state, detail)
        self._on_status(state, detail)

    async def _connection_loop(self):
        delay = 2
        while not self._closing:
            try:
                await self._connect()
                delay = 2
                await self._disconnected.wait()
                self._status("reconectando", "Se perdió la conexión, reconectando…")
            except Exception as e:
                reason = str(e) or type(e).__name__
                log.warning("Fallo de conexión: %s", reason)
                self._status("error", f"{reason} · reintento en {delay} s")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def _connect(self):
        mac = self.config.get("mac")
        if not mac or self._fails >= FAILS_BEFORE_SCAN:
            self._status("buscando", "Buscando luces BJ_LED_M…")
            device = await BleakScanner.find_device_by_filter(
                lambda d, adv: DEVICE_NAME in (adv.local_name or d.name or "").lower(),
                timeout=SCAN_TIMEOUT,
            )
            if device is None:
                raise RuntimeError("No encontré ninguna luz BJ_LED_M")
            target, mac = device, device.address
        else:
            target = mac

        self._status("conectando", f"Conectando a {mac}…")
        self._disconnected.clear()
        client = BleakClient(target, disconnected_callback=self._handle_disconnect,
                             timeout=CONNECT_TIMEOUT)
        try:
            await client.connect()
        except Exception:
            self._fails += 1
            raise

        self._client = client
        self._fails = 0
        if self.config.get("mac") != mac:
            self.config["mac"] = mac
            save_config(self.config)
        self._status("conectado", mac)
        self._resend = True
        self._dirty.set()

    def _handle_disconnect(self, client):
        if client is self._client:
            self._client = None
            self._disconnected.set()

    # ---------- Envío de comandos ----------

    def _static_frame(self):
        return scale(self.color, self.brightness)

    def _refresh(self):
        if not self.effect:
            self._frame = self._static_frame()
        self._dirty.set()

    async def _writer_loop(self):
        """Manda solo el estado más reciente, sin saturar la luz."""
        sent_power = sent_frame = None
        while True:
            await self._dirty.wait()
            self._dirty.clear()
            client = self._client
            if client is None or not client.is_connected:
                continue
            if self._resend:
                sent_power = sent_frame = None
                self._resend = False
            try:
                if self.power != sent_power:
                    await client.write_gatt_char(WRITE_UUID, cmd_power(self.power), response=True)
                    sent_power = self.power
                    sent_frame = None
                if self.power and self._frame != sent_frame:
                    frame = self._frame
                    await client.write_gatt_char(WRITE_UUID, cmd_color(*frame), response=False)
                    sent_frame = frame
            except Exception as e:
                log.warning("Error escribiendo: %s", e)
                self._resend = True
                self._dirty.set()
                await asyncio.sleep(0.5)
            await asyncio.sleep(FRAME_INTERVAL)

    # ---------- Efectos de luz ----------

    async def _run_effect(self, name):
        phase = 0.0
        while True:
            phase += FRAME_INTERVAL * self.speed
            if name == "arcoiris":
                rgb = hue_to_rgb((phase / 8) % 1)
            elif name == "respiracion":
                level = 0.05 + 0.95 * (1 + math.cos(2 * math.pi * phase / 4)) / 2
                rgb = scale(self.color, level)
            else:  # desvanecido
                pos = (phase / 2.5) % len(FADE_PALETTE)
                i, t = int(pos), pos - int(pos)
                a, b = FADE_PALETTE[i], FADE_PALETTE[(i + 1) % len(FADE_PALETTE)]
                rgb = tuple(round(x + (y - x) * t) for x, y in zip(a, b))
            self._frame = scale(rgb, self.brightness)
            self._dirty.set()
            await asyncio.sleep(FRAME_INTERVAL)

    async def _run_screen(self):
        """Modo pantalla (Ambilight): captura el fotograma y sincroniza el LED."""
        sampler = ScreenSampler(monitor=self.screen_monitor, zone=self.screen_zone)
        pool = ThreadPoolExecutor(max_workers=1)
        current = None
        try:
            while True:
                target = await asyncio.get_running_loop().run_in_executor(pool, sampler.sample)
                alpha = min(0.9, 0.3 * self.speed)
                current = target if current is None else tuple(
                    c + (t - c) * alpha for c, t in zip(current, target))
                scaled = scale(current, self.brightness)
                self._frame = scaled
                self._dirty.set()
                if self._on_status:
                    self._on_status("screen_color", scaled)
                await asyncio.sleep(SCREEN_INTERVAL)
        finally:
            if self._on_status:
                self._on_status("screen_color", None)
            pool.submit(sampler.close)
            pool.shutdown(wait=False)
