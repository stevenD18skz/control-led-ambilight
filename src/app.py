"""Interfaz gráfica de usuario (Tkinter + Tray) para Control LED Ambilight."""
import asyncio
import colorsys
import ctypes
import logging
import math
import queue
import threading
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk
import pystray

from .constants import (
    BG, PANEL, PANEL_HOVER, CARD_BG, CARD_BORDER, FG, MUTED,
    ACCENT, ACCENT_HOVER, SUCCESS, SUCCESS_HOVER,
    FONT, FONT_BOLD, FONT_SMALL, FONT_TITLE,
    STATUS, PRESETS, OTHER_EFFECTS,
    ICON_ICO_PATH, ICON_PNG_PATH, ICON_TRAY_PATH, LOG_PATH
)
from .controller import COLOR_OVERRIDING_EFFECTS, LedController
from .sampler import get_monitors_info


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def hex_to_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def flat_button(parent, text, command, **kw):
    options = dict(relief="flat", bd=0, bg=PANEL, fg=FG, activebackground=PANEL_HOVER,
                   activeforeground=FG, font=FONT, cursor="hand2", padx=12, pady=7)
    options.update(kw)
    return tk.Button(parent, text=text, command=command, **options)


def section_label(parent, text):
    tk.Label(parent, text=text.upper(), bg=BG, fg=MUTED, font=FONT_SMALL, anchor="w").pack(
        fill="x", pady=(14, 6))


def dark_scale(parent, from_, to, command, length):
    return tk.Scale(parent, from_=from_, to=to, orient="horizontal", command=command,
                    length=length, showvalue=False, bg=BG, troughcolor=PANEL,
                    activebackground=ACCENT, highlightthickness=0, bd=0, sliderrelief="flat",
                    sliderlength=18, width=12)


class App:
    def __init__(self, root):
        self.root = root
        self.ui_scale = root.winfo_fpixels("1i") / 96
        self.status_queue = queue.Queue()

        # Bucle asyncio en un hilo aparte para el stack de Bluetooth
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.led = LedController(self.loop, lambda s, d: self.status_queue.put((s, d)))
        asyncio.run_coroutine_threadsafe(self.led.start(), self.loop)

        self.power = self.led.power
        self.color = self.led.color
        self.effect = self.led.effect
        self.screen_zone = getattr(self.led, "screen_zone", "all")
        self.screen_monitor = getattr(self.led, "screen_monitor", 1)
        self.current_screen_color = None

        # Monitores físicos disponibles
        self.monitors_info = get_monitors_info()

        self._build_ui()
        self._update_power_button()
        self._show_color(self.color)
        self._update_screen_controls()
        self._update_effect_buttons()

        # Pestaña activa inicial: por defecto Modo Pantalla
        initial_tab = self.led.config.get("last_tab", "screen")
        self.switch_tab(initial_tab)

        root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        root.bind("<Unmap>", self._on_unmap)
        self._init_tray()
        self._poll_status()

    # ---------- Construcción de la interfaz ----------

    def _build_ui(self):
        root = self.root
        root.title("Control LED · Ambilight")
        root.configure(bg=BG)
        root.resizable(False, False)

        # Carga del icono pixel art nítido para la ventana y la barra de tareas
        self._header_icon_img = None
        if ICON_PNG_PATH.exists():
            try:
                raw_icon = Image.open(ICON_PNG_PATH)
                self._header_icon_img = ImageTk.PhotoImage(raw_icon.resize((28, 28), Image.Resampling.BOX))
                self._icon_photos = [
                    ImageTk.PhotoImage(raw_icon.resize((s, s), Image.Resampling.BOX))
                    for s in (32, 48, 64, 128, 256, 16)
                ]
                root.iconphoto(True, *self._icon_photos)
            except Exception:
                pass
        if ICON_ICO_PATH.exists():
            try:
                root.iconbitmap(str(ICON_ICO_PATH))
            except Exception:
                pass

        body = tk.Frame(root, bg=BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)
        self.wheel_size = int(220 * self.ui_scale)
        width = int(280 * self.ui_scale)

        # 1. Encabezado: icono, nombre y botones de acción
        header = tk.Frame(body, bg=BG)
        header.pack(fill="x")
        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side="left")
        if self._header_icon_img:
            tk.Label(title_box, image=self._header_icon_img, bg=BG).pack(side="left", padx=(0, 8))
        tk.Label(title_box, text="Control Ambilight", bg=BG, fg=FG, font=FONT_TITLE).pack(side="left")

        actions = tk.Frame(header, bg=BG)
        actions.pack(side="right")
        flat_button(actions, "Ocultar", self.hide_to_tray, font=FONT_SMALL, padx=8, pady=3).pack(side="left", padx=(0, 6))
        flat_button(actions, "Buscar", self.rescan, font=FONT_SMALL, padx=8, pady=3).pack(side="left")

        status_row = tk.Frame(body, bg=BG)
        status_row.pack(fill="x", pady=(4, 0))
        dot = int(9 * self.ui_scale)
        self.status_dot = tk.Canvas(status_row, width=dot, height=dot, bg=BG, highlightthickness=0)
        self.status_dot.create_oval(1, 1, dot - 1, dot - 1, fill=MUTED, outline="", tags="dot")
        self.status_dot.pack(side="left", padx=(0, 6))
        self.status_label = tk.Label(status_row, text="Iniciando…", bg=BG, fg=MUTED, font=FONT_SMALL,
                                     anchor="w", wraplength=width, justify="left")
        self.status_label.pack(side="left", fill="x")

        # 2. Botón Maestro de Encendido
        self.power_btn = tk.Button(body, command=self.toggle_power, relief="flat", bd=0,
                                   font=("Segoe UI Semibold", 11), cursor="hand2", pady=8)
        self.power_btn.pack(fill="x", pady=(12, 12))

        # 3. Selector de Pestañas
        tabs_frame = tk.Frame(body, bg=PANEL, padx=3, pady=3)
        tabs_frame.pack(fill="x", pady=(0, 12))

        self.btn_tab_screen = tk.Button(
            tabs_frame, text="🖥️ Modo Pantalla (Ambilight)", relief="flat", bd=0,
            cursor="hand2", font=FONT_BOLD, pady=6,
            command=lambda: self.switch_tab("screen")
        )
        self.btn_tab_screen.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.btn_tab_manual = tk.Button(
            tabs_frame, text="🎨 Manual / Efectos", relief="flat", bd=0,
            cursor="hand2", font=FONT, pady=6,
            command=lambda: self.switch_tab("manual")
        )
        self.btn_tab_manual.pack(side="right", fill="x", expand=True)

        # Pestaña 1: Modo Pantalla
        self.screen_frame = tk.Frame(body, bg=BG)
        self._build_screen_tab(self.screen_frame, width)

        # Pestaña 2: Manual y Efectos
        self.manual_frame = tk.Frame(body, bg=BG)
        self._build_manual_tab(self.manual_frame, width)

        # Pie informativo
        tk.Label(body, text="Cierra o minimiza para ocultar en la barra de tareas.\nClic derecho en el icono de la bandeja para accesos rápidos.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), wraplength=width + 20, justify="center").pack(
            fill="x", pady=(14, 0))

    def _build_screen_tab(self, parent, width):
        """Construye la vista protagonista del Modo Pantalla."""
        hero_card = tk.Frame(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                             highlightthickness=1, padx=12, pady=12)
        hero_card.pack(fill="x", pady=(0, 10))

        # Botón Hero de Modo Pantalla
        self.screen_hero_btn = tk.Button(
            hero_card, text="▶  ACTIVAR MODO PANTALLA", relief="flat", bd=0,
            font=("Segoe UI Semibold", 12), cursor="hand2", pady=10,
            command=lambda: self.toggle_effect("pantalla")
        )
        self.screen_hero_btn.pack(fill="x")

        # Visualizador en tiempo real
        preview_container = tk.Frame(hero_card, bg=CARD_BG)
        preview_container.pack(fill="x", pady=(10, 0))

        tk.Label(preview_container, text="COLOR DE PANTALLA EN VIVO", bg=CARD_BG,
                 fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")

        live_row = tk.Frame(preview_container, bg=CARD_BG)
        live_row.pack(fill="x", pady=(4, 0))

        self.screen_live_color = tk.Canvas(live_row, width=44, height=36, bg="#2a2e3b",
                                           highlightbackground=PANEL_HOVER, highlightthickness=1)
        self.screen_live_color.pack(side="left")

        live_info = tk.Frame(live_row, bg=CARD_BG, padx=10)
        live_info.pack(side="left", fill="both", expand=True)

        self.screen_color_lbl = tk.Label(live_info, text="En pausa", bg=CARD_BG, fg=FG,
                                         font=("Consolas", 11, "bold"), anchor="w")
        self.screen_color_lbl.pack(fill="x")

        self.screen_status_desc = tk.Label(live_info, text="Haz clic arriba para iniciar sincronización",
                                           bg=CARD_BG, fg=MUTED, font=FONT_SMALL, anchor="w")
        self.screen_status_desc.pack(fill="x")

        # Tarjeta de Ajustes
        section_label(parent, "Ajustes de Pantalla")

        settings_card = tk.Frame(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                                 highlightthickness=1, padx=12, pady=10)
        settings_card.pack(fill="x")

        # 1. Zona de captura
        tk.Label(settings_card, text="Zona de captura:", bg=CARD_BG, fg=MUTED, font=FONT_SMALL).pack(anchor="w")
        zone_row = tk.Frame(settings_card, bg=CARD_BG)
        zone_row.pack(fill="x", pady=(4, 8))

        self.btn_zone_all = tk.Button(
            zone_row, text="Completa", relief="flat", bd=0, cursor="hand2",
            font=FONT_SMALL, pady=5, command=lambda: self._set_zone("all")
        )
        self.btn_zone_all.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_zone_borders = tk.Button(
            zone_row, text="Bordes", relief="flat", bd=0, cursor="hand2",
            font=FONT_SMALL, pady=5, command=lambda: self._set_zone("borders")
        )
        self.btn_zone_borders.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_zone_bottom = tk.Button(
            zone_row, text="Inferior (Mesa)", relief="flat", bd=0, cursor="hand2",
            font=FONT_SMALL, pady=5, command=lambda: self._set_zone("bottom")
        )
        self.btn_zone_bottom.pack(side="left", fill="x", expand=True)

        # 2. Selector de monitor
        if len(self.monitors_info) > 1:
            tk.Label(settings_card, text="Monitor a sincronizar:", bg=CARD_BG, fg=MUTED, font=FONT_SMALL).pack(anchor="w", pady=(4, 0))
            mon_row = tk.Frame(settings_card, bg=CARD_BG)
            mon_row.pack(fill="x", pady=(4, 8))
            self.monitor_buttons = {}
            for idx, w, h in self.monitors_info:
                btn = tk.Button(
                    mon_row, text=f"Monitor {idx} ({w}x{h})", relief="flat", bd=0,
                    cursor="hand2", font=FONT_SMALL, pady=4,
                    command=lambda i=idx: self._set_monitor(i)
                )
                btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
                self.monitor_buttons[idx] = btn
        else:
            mon_info = self.monitors_info[0] if self.monitors_info else (1, 1920, 1080)
            tk.Label(settings_card, text=f"Pantalla: Monitor {mon_info[0]} ({mon_info[1]}x{mon_info[2]})",
                     bg=CARD_BG, fg=MUTED, font=FONT_SMALL).pack(anchor="w", pady=(2, 6))

        # 3. Reactividad / Suavizado
        speed_header = tk.Frame(settings_card, bg=CARD_BG)
        speed_header.pack(fill="x", pady=(4, 0))
        tk.Label(speed_header, text="Reactividad (Suavizado):", bg=CARD_BG, fg=MUTED, font=FONT_SMALL).pack(side="left")
        self.screen_speed_lbl = tk.Label(speed_header, text="Equilibrado", bg=CARD_BG, fg=FG, font=FONT_SMALL)
        self.screen_speed_lbl.pack(side="right")

        self.screen_speed_scale = dark_scale(settings_card, 1, 10, self._on_speed, width - 40)
        self.screen_speed_scale.set(round(self.led.speed * 4))
        self.screen_speed_scale.pack(fill="x", pady=(2, 8))

        # 4. Brillo
        bright_header = tk.Frame(settings_card, bg=CARD_BG)
        bright_header.pack(fill="x", pady=(4, 0))
        tk.Label(bright_header, text="Brillo de la luz:", bg=CARD_BG, fg=MUTED, font=FONT_SMALL).pack(side="left")
        self.screen_bright_lbl = tk.Label(bright_header, text=f"{round(self.led.brightness * 100)}%",
                                          bg=CARD_BG, fg=FG, font=FONT_SMALL)
        self.screen_bright_lbl.pack(side="right")

        self.screen_bright_scale = dark_scale(settings_card, 1, 100, self._on_brightness, width - 40)
        self.screen_bright_scale.set(round(self.led.brightness * 100))
        self.screen_bright_scale.pack(fill="x", pady=(2, 4))

    def _build_manual_tab(self, parent, width):
        """Construye la vista con rueda de color manual y efectos decorativos."""
        section_label(parent, "Color Manual")
        self.wheel = tk.Canvas(parent, width=self.wheel_size, height=self.wheel_size, bg=BG,
                               highlightthickness=0, cursor="crosshair")
        self.wheel.pack()
        self.wheel_img = self._make_wheel_image(self.wheel_size)
        self.wheel.create_image(0, 0, image=self.wheel_img, anchor="nw")
        m = int(8 * self.ui_scale)
        self.wheel.create_oval(0, 0, m * 2, m * 2, outline="#000000", width=4, tags="marker")
        self.wheel.create_oval(0, 0, m * 2, m * 2, outline="#ffffff", width=2, tags="marker")
        self.wheel.bind("<Button-1>", self._on_wheel)
        self.wheel.bind("<B1-Motion>", self._on_wheel)

        preview_row = tk.Frame(parent, bg=BG)
        preview_row.pack(fill="x", pady=(8, 0))
        sw = int(24 * self.ui_scale)
        self.preview = tk.Canvas(preview_row, width=sw, height=sw, bg=BG, highlightthickness=0)
        self.preview.create_rectangle(0, 0, sw, sw, outline="", tags="fill")
        self.preview.pack(side="left")
        self.hex_label = tk.Label(preview_row, bg=BG, fg=FG, font=("Consolas", 10))
        self.hex_label.pack(side="left", padx=8)

        presets = tk.Frame(parent, bg=BG)
        presets.pack(fill="x", pady=(8, 0))
        ps = int(22 * self.ui_scale)
        for value in PRESETS:
            c = tk.Canvas(presets, width=ps, height=ps, bg=BG, highlightthickness=0, cursor="hand2")
            c.create_oval(1, 1, ps - 1, ps - 1, fill=value, outline=PANEL_HOVER)
            c.bind("<Button-1>", lambda e, v=value: self.pick_color(hex_to_rgb(v)))
            c.pack(side="left", padx=(0, 5))

        # Brillo
        section_label(parent, "Brillo")
        bright_row = tk.Frame(parent, bg=BG)
        bright_row.pack(fill="x")
        self.manual_bright_lbl = tk.Label(bright_row, bg=BG, fg=FG, font=FONT, width=5, anchor="e")
        self.manual_bright_lbl.pack(side="right")
        self.manual_bright_scale = dark_scale(bright_row, 1, 100, self._on_brightness, width - 40)
        self.manual_bright_scale.set(round(self.led.brightness * 100))
        self.manual_bright_scale.pack(side="left")
        self.manual_bright_lbl.config(text=f"{round(self.led.brightness * 100)}%")

        # Efectos decorativos
        section_label(parent, "Efectos Decorativos")
        fx_row = tk.Frame(parent, bg=BG)
        fx_row.pack(fill="x")
        self.effect_buttons = {}
        for i, (key, label) in enumerate(OTHER_EFFECTS):
            btn = flat_button(fx_row, label, lambda k=key: self.toggle_effect(k))
            btn.pack(side="left", fill="x", expand=True, padx=(0 if i == 0 else 4, 0))
            self.effect_buttons[key] = btn

    def _make_wheel_image(self, size):
        img = tk.PhotoImage(width=size, height=size)
        r = size / 2
        rows = []
        for y in range(size):
            row = []
            for x in range(size):
                dx, dy = x + 0.5 - r, r - y - 0.5
                d = math.hypot(dx, dy)
                if d <= r:
                    h = (math.atan2(dy, dx) / (2 * math.pi)) % 1
                    row.append(rgb_to_hex(tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, d / r, 1))))
                else:
                    row.append(BG)
            rows.append("{" + " ".join(row) + "}")
        img.put(" ".join(rows))
        return img

    # ---------- Navegación de Pestañas ----------

    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        self.led.config["last_tab"] = tab_name
        self.led.call(self.led.save_settings)

        if tab_name == "screen":
            self.btn_tab_screen.config(bg=ACCENT, fg="#ffffff", activebackground=ACCENT_HOVER)
            self.btn_tab_manual.config(bg=PANEL, fg=MUTED, activebackground=PANEL_HOVER)
            self.manual_frame.pack_forget()
            self.screen_frame.pack(fill="both", expand=True)
        else:
            self.btn_tab_manual.config(bg=ACCENT, fg="#ffffff", activebackground=ACCENT_HOVER)
            self.btn_tab_screen.config(bg=PANEL, fg=MUTED, activebackground=PANEL_HOVER)
            self.screen_frame.pack_forget()
            self.manual_frame.pack(fill="both", expand=True)

    # ---------- Acciones ----------

    def toggle_power(self):
        self.power = not self.power
        self.led.call(self.led.set_power, self.power)
        self._update_power_button()

    def pick_color(self, rgb):
        self.color = rgb
        self._show_color(rgb)
        if not self.power:
            self.toggle_power()
        if self.effect in COLOR_OVERRIDING_EFFECTS:
            self.effect = None
            self._update_effect_buttons()
            self._update_screen_controls()
        self.led.call(self.led.set_color, rgb)

    def toggle_effect(self, key):
        self.effect = None if self.effect == key else key
        if self.effect and not self.power:
            self.toggle_power()
        self.led.call(self.led.set_effect, self.effect)
        self._update_effect_buttons()
        self._update_screen_controls()

    def rescan(self):
        self.led.call(self.led.forget_device)
        self._show_status("buscando", "Buscando luces BJ_LED_M…")

    def _set_zone(self, zone):
        self.screen_zone = zone
        self.led.call(self.led.set_screen_zone, zone)
        self._update_screen_controls()

    def _set_monitor(self, monitor_idx):
        self.screen_monitor = monitor_idx
        self.led.call(self.led.set_screen_monitor, monitor_idx)
        self._update_screen_controls()

    def _on_wheel(self, event):
        r = self.wheel_size / 2
        dx, dy = event.x - r, r - event.y
        h = (math.atan2(dy, dx) / (2 * math.pi)) % 1
        s = min(math.hypot(dx, dy) / r, 1)
        self.pick_color(tuple(round(c * 255) for c in colorsys.hsv_to_rgb(h, s, 1)))

    def _on_brightness(self, value):
        val = int(value)
        self.screen_bright_lbl.config(text=f"{val}%")
        self.manual_bright_lbl.config(text=f"{val}%")
        self.screen_bright_scale.set(val)
        self.manual_bright_scale.set(val)
        self.led.call(self.led.set_brightness, val / 100)

    def _on_speed(self, value):
        val = int(value)
        self.screen_speed_scale.set(val)
        if val <= 3:
            desc = "Suave (Cine)"
        elif val <= 7:
            desc = "Equilibrado"
        else:
            desc = "Rápido (Juegos)"
        self.screen_speed_lbl.config(text=desc)
        self.led.call(self.led.set_speed, val / 4)

    # ---------- Actualizaciones Visuales ----------

    def _update_power_button(self):
        if self.power:
            self.power_btn.config(text="💡  Luz Encendida", bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8")
        else:
            self.power_btn.config(text="⚫  Luz Apagada", bg=PANEL, fg=MUTED, activebackground=PANEL_HOVER)
        self._update_tray_icon()

    def _update_screen_controls(self):
        is_screen = (self.effect == "pantalla")
        if is_screen:
            self.screen_hero_btn.config(
                text="⏹  PAUSAR MODO PANTALLA",
                bg=SUCCESS, fg="#ffffff",
                activebackground=SUCCESS_HOVER
            )
            self.screen_status_desc.config(
                text="● Sincronizando en tiempo real con el monitor",
                fg=SUCCESS
            )
        else:
            self.screen_hero_btn.config(
                text="▶  ACTIVAR MODO PANTALLA",
                bg=PANEL, fg=FG,
                activebackground=PANEL_HOVER
            )
            self.screen_status_desc.config(
                text="Haz clic arriba para iniciar sincronización",
                fg=MUTED
            )
            self.screen_color_lbl.config(text="En pausa", fg=MUTED)
            self.screen_live_color.configure(bg="#20242f")

        # Botones de zona
        for z, btn in [("all", self.btn_zone_all), ("borders", self.btn_zone_borders), ("bottom", self.btn_zone_bottom)]:
            if self.screen_zone == z:
                btn.config(bg=ACCENT, fg="#ffffff")
            else:
                btn.config(bg=PANEL, fg=MUTED)

        # Botones de monitor
        if hasattr(self, "monitor_buttons"):
            for idx, btn in self.monitor_buttons.items():
                if idx == self.screen_monitor:
                    btn.config(bg=ACCENT, fg="#ffffff")
                else:
                    btn.config(bg=PANEL, fg=MUTED)

    def _on_screen_color_update(self, rgb):
        """Llamado cuando el hilo de captura entrega un nuevo color."""
        if rgb is None:
            if self.effect != "pantalla":
                self.screen_color_lbl.config(text="En pausa", fg=MUTED)
                self.screen_live_color.configure(bg="#20242f")
            return

        self.current_screen_color = rgb
        hex_val = rgb_to_hex(rgb)
        self.screen_live_color.configure(bg=hex_val)
        self.screen_color_lbl.config(text=hex_val.upper(), fg=FG)
        if self.effect == "pantalla":
            self._update_tray_icon()

    def _update_effect_buttons(self):
        for key, btn in self.effect_buttons.items():
            active = (key == self.effect)
            btn.config(bg=ACCENT if active else PANEL, fg="#ffffff" if active else FG,
                       activebackground=ACCENT_HOVER if active else PANEL_HOVER)

    def _show_color(self, rgb):
        value = rgb_to_hex(rgb)
        self.preview.itemconfig("fill", fill=value)
        self.hex_label.config(text=value.upper())
        h, s, _ = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
        r = self.wheel_size / 2
        x = r + math.cos(h * 2 * math.pi) * s * (r - 1)
        y = r - math.sin(h * 2 * math.pi) * s * (r - 1)
        m = int(8 * self.ui_scale)
        for item in self.wheel.find_withtag("marker"):
            self.wheel.coords(item, x - m, y - m, x + m, y + m)
        self._update_tray_icon()

    def _show_status(self, state, detail):
        color, title = STATUS.get(state, (MUTED, state))
        self.status_dot.itemconfig("dot", fill=color)
        self.status_label.config(text=f"{title} · {detail}" if detail else title)

    def _poll_status(self):
        try:
            while True:
                msg = self.status_queue.get_nowait()
                if msg[0] == "screen_color":
                    self._on_screen_color_update(msg[1])
                else:
                    self._show_status(*msg)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_status)

    # ---------- Bandeja del sistema (System Tray) ----------

    def _make_tray_image(self):
        size = 64
        if not hasattr(self, "_base_tray_img") or self._base_tray_img is None:
            if ICON_TRAY_PATH.exists():
                self._base_tray_img = Image.open(ICON_TRAY_PATH).convert("RGBA").resize((size, size), Image.Resampling.BOX)
            else:
                self._base_tray_img = None

        if self._base_tray_img is not None:
            if self.power:
                img = self._base_tray_img.copy()
                draw = ImageDraw.Draw(img)
                if self.effect == "pantalla" and self.current_screen_color:
                    color = tuple(self.current_screen_color)
                else:
                    color = tuple(self.color)
                # Pequeño led indicador circular en la esquina inferior derecha
                draw.ellipse((44, 44, 58, 58), fill=color, outline=(255, 255, 255), width=2)
                return img
            else:
                # Si está apagada la luz, muestra el monitor en modo reposo atenuado
                from PIL import ImageEnhance
                gray = self._base_tray_img.convert("L").convert("RGBA")
                return ImageEnhance.Brightness(gray).enhance(0.45)

        # Fallback si no existe la imagen
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((6, 6, size - 7, size - 7), fill=tuple(self.color) if self.power else (45, 49, 58))
        return img

    def _init_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar Control", self.show_from_tray, default=True),
            pystray.MenuItem(lambda item: "Pausar Modo Pantalla" if self.effect == "pantalla" else "Activar Modo Pantalla",
                             self.toggle_screen_from_tray),
            pystray.MenuItem(lambda item: "Apagar Luz" if self.power else "Encender Luz", self.toggle_power_from_tray),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir por completo", self.exit_app)
        )
        self.tray_icon = pystray.Icon("ControlLED", self._make_tray_image(), "Control LED · Ambilight", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _update_tray_icon(self):
        if hasattr(self, "tray_icon") and self.tray_icon:
            try:
                self.tray_icon.icon = self._make_tray_image()
            except Exception:
                pass

    def toggle_screen_from_tray(self, icon=None, item=None):
        self.root.after(0, lambda: self.toggle_effect("pantalla"))

    def hide_to_tray(self):
        self.root.withdraw()

    def _on_unmap(self, event):
        if event.widget == self.root and self.root.state() == "iconic":
            self.root.withdraw()

    def show_from_tray(self, icon=None, item=None):
        self.root.after(0, self._restore_window)

    def _restore_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()

    def toggle_power_from_tray(self, icon=None, item=None):
        self.root.after(0, self.toggle_power)

    def exit_app(self, icon=None, item=None):
        if hasattr(self, "tray_icon") and self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.after(0, self.close)

    def close(self):
        if hasattr(self, "tray_icon") and self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        future = asyncio.run_coroutine_threadsafe(self.led.shutdown(), self.loop)
        try:
            future.result(timeout=5)
        except Exception:
            logging.exception("Error al cerrar")
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.root.destroy()


def main():
    logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # texto nítido en pantallas escaladas
    except (AttributeError, OSError):
        pass
    try:
        # Registra el AppUserModelID para que Windows muestre el icono en la barra de tareas
        app_id = "brayan.controlled.ambilight.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        pass
    try:
        root = tk.Tk()
        App(root)
        root.mainloop()
    except Exception as e:
        logging.exception("Error al iniciar la aplicación: %s", e)
        try:
            import tkinter.messagebox as mb
            mb.showerror("Error Control LED", f"Ocurrió un error al iniciar:\n{e}\n\nRevisa led_control.log para más detalles.")
        except Exception:
            pass
