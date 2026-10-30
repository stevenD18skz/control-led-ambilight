# 🖥️ Control LED · Ambilight

Aplicación de control virtual y sincronización Ambilight en tiempo real para tiras de luz LED Bluetooth **MohuanLED (BJ_LED_M)** en Windows.

---

## 📁 Estructura del Proyecto

```text
Control Led/
├── assets/                  # Recursos gráficos (iconos pixel art)
│   ├── icon.ico            # Icono multi-resolución de Windows
│   ├── icon.png            # Icono HD
│   └── icon_tray.png       # Icono optimizado para la bandeja del sistema
├── src/                    # Todo el código fuente de la aplicación
│   ├── main.py             # Punto de entrada de la aplicación
│   ├── __main__.py         # Soporte para ejecución modular (python -m src)
│   ├── __init__.py         # Exportaciones del paquete
│   ├── app.py              # Interfaz gráfica Tkinter y bandeja del sistema
│   ├── controller.py       # Lógica Bluetooth BLE, reconexión y efectos
│   ├── sampler.py          # Captura de pantalla y algoritmo de color Ambilight
│   └── constants.py        # Rutas globales, paletas de colores y fuentes
├── tools/                  # Utilidades y diagnósticos
│   ├── scan.py             # Escaneo de dispositivos BLE cercanos
│   ├── explore.py          # Inspección de servicios y características BLE
│   ├── test_basic.py       # Prueba de comandos directos BLE
│   └── update_shortcuts.py # Generador de accesos directos de Windows
├── Instalar y ejecutar.bat # Prepara el entorno e instala las dependencias
├── config.json             # Ajustes guardados del usuario (brillo, estado, monitor, etc.)
├── Control LED.bat         # Lanzador sin consola para Windows
├── Control LED.lnk         # Acceso directo con icono personalizado
└── requirements.txt        # Dependencias de Python
```

---

## 🚀 Cómo Iniciar la Aplicación

1. **Primera ejecución**: Instala [Python 3.10 o superior](https://www.python.org/downloads/) si aún no está instalado. Luego haz doble clic en `Instalar y ejecutar.bat`. El archivo crea `.venv`, instala las dependencias de `requirements.txt` e inicia la aplicación. Se necesita conexión a Internet para instalar las dependencias.
2. **Ejecuciones posteriores**: Haz doble clic en `Control LED.bat` o en `Control LED.lnk`.
3. **Desde la terminal, después de instalar**:
   ```bash
   .venv\Scripts\python.exe src\main.py
   # o también:
   .venv\Scripts\python.exe -m src
   ```

---

## 🎨 Características

* **Modo Pantalla (Ambilight)**:
  * Ponderación inteligente de color: filtra negros y grises para reflejar el color más vivo de la escena.
  * Visualizador en vivo en la interfaz con código HEX y muestra en tiempo real.
  * Selección de monitor para configuraciones de múltiples pantallas.
  * 3 Zonas de captura:
    * **Completa**: Promedio ponderado de toda la pantalla.
    * **Bordes**: Perímetro del 20% (ideal para tiras montadas detrás del monitor).
    * **Inferior (Mesa)**: Franja inferior del 35% con filtro anti-barras negras (ideal para luces bajo el escritorio / desk underglow).
  * Control de reactividad ajustable desde *Cine (suave)* hasta *Juegos (rápido)*.
* **Control Manual y Efectos**:
  * Rueda de color interactiva + 9 presets de color rápido.
  * Efectos decorativos (Desvanecido, Respiración, Arcoíris).
* **Bandeja del Sistema (System Tray)**:
  * Icono de monitor pixel art junto al reloj de Windows.
  * Menú rápido con clic derecho para activar/pausar Ambilight o apagar las luces sin abrir la ventana.
