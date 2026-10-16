# QR//GEN — Generador de QRs

Generador de códigos QR para **Windows** (app de escritorio en Python) y **Android** (app nativa en Kotlin). Vista previa en vivo, modo claro y oscuro, colores personalizados, logo central y exportación a PNG, JPG, BMP o SVG.

![Interfaz en modo oscuro](docs/captura-oscuro.png)

## ⬇ Descargas

| Plataforma | Archivo | Enlace |
|---|---|---|
| **Windows** — ejecutable portable | `GeneradorQR.exe` | [Descargar .exe](https://github.com/aloks93/generador-de-qrs/releases/latest/download/GeneradorQR.exe) |
| **Windows** — comprimido (exe + licencia) | `GeneradorQR-windows.zip` | [Descargar .zip](https://github.com/aloks93/generador-de-qrs/releases/latest/download/GeneradorQR-windows.zip) |
| **Android** 7.0 o superior | `GeneradorQR-android.apk` | [Descargar .apk](https://github.com/aloks93/generador-de-qrs/releases/latest/download/GeneradorQR-android.apk) |
| **Código fuente** | `GeneradorQR-source.zip` | [Descargar .zip](https://github.com/aloks93/generador-de-qrs/releases/latest/download/GeneradorQR-source.zip) |

Todas las versiones están en [Releases](https://github.com/aloks93/generador-de-qrs/releases).

- **Windows:** el `.exe` no necesita instalación ni Python. Como no está firmado digitalmente, SmartScreen puede avisar la primera vez: pulsa *Más información → Ejecutar de todas formas*.
- **Android:** abre el `.apk` en el móvil y permite «instalar apps de origen desconocido» cuando lo pida.

## Tipos de QR soportados

| Código | Tipo | Qué hace al escanearlo |
|---|---|---|
| `URL` | Enlace / URL | Abre la página web |
| `FILE` | PDF / Archivo | Abre un PDF, imagen, video o cualquier archivo alojado en internet |
| `TXT` | Texto | Muestra el texto |
| `WIFI` | Red WiFi | Conecta a la red (WPA, WEP o abierta, incluso redes ocultas) |
| `VCF` | Contacto (vCard) | Guarda el contacto en la agenda |
| `MAIL` | Email | Abre un correo con destinatario, asunto y mensaje |
| `TEL` | Teléfono | Inicia una llamada |
| `SMS` | SMS | Prepara un SMS |
| `WA` | WhatsApp | Abre un chat de WhatsApp con mensaje opcional |
| `GEO` | Ubicación | Abre las coordenadas en el mapa |
| `CAL` | Evento | Añade un evento al calendario |
| `BTC` | Cripto | Solicitud de pago (Bitcoin, Ethereum, Litecoin…) |

### Sobre los PDFs y archivos

Un código QR solo puede guardar unos 3 KB, así que **un archivo no cabe dentro del QR**. Para compartir un PDF:

1. Súbelo a Google Drive, Dropbox, OneDrive o similar.
2. Compártelo como «cualquiera con el enlace puede ver».
3. Pega ese enlace en la sección **PDF / Archivo**.

## App de escritorio

![Interfaz en modo claro](docs/captura-claro.png)

1. Elige el tipo de QR en la columna izquierda.
2. Rellena los campos; la vista previa se actualiza sola. Los datos de cada tipo se conservan al cambiar de uno a otro.
3. Ajusta color del código y del fondo (`⇄` los intercambia), corrección de errores, tamaño de módulo y logo.
4. **GUARDAR** (PNG, SVG, JPG o BMP) o **COPIAR** para pegarlo en otra aplicación.

| Atajo | Acción |
|---|---|
| `Ctrl+S` | Guardar |
| `Ctrl+Shift+C` | Copiar imagen |
| `Ctrl+T` | Cambiar entre modo claro y oscuro |

> Con logo se fuerza la corrección H (30 %) para que el QR siga leyéndose. El SVG también incluye el logo.

### Ejecutar desde el código

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/aloks93/generador-de-qrs.git
cd generador-de-qrs
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
python main.py
```

### Uso como librería

```python
from qrgen import payloads
from qrgen.generator import QROptions, save

datos = payloads.wifi("MiCasa", "clave-secreta")
save(datos, "wifi.png", QROptions(fill_color="#1a3d8f"))
```

### Crear el .exe

```bash
pip install pyinstaller
python scripts/build_windows.py   # → dist/GeneradorQR.exe y dist/GeneradorQR-windows.zip
```

## App Android

Código en [`android/`](android/): Kotlin + Jetpack Compose, generación con ZXing, sin permisos especiales. Incluye los mismos 12 tipos de QR, modo claro/oscuro, colores, corrección de errores, logo, guardado en PNG/SVG y compartir.

```bash
cd android
./gradlew assembleRelease         # → app/build/outputs/apk/release/app-release.apk
```

También se puede abrir la carpeta `android/` con Android Studio.

## Publicar una versión

Las descargas se generan automáticamente con GitHub Actions (`.github/workflows/release.yml`). Al subir una etiqueta se compilan el `.exe`, el `.zip` y el `.apk` y se adjuntan a una nueva release:

```bash
git tag v1.0.1
git push origin v1.0.1
```

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest                             # Python
cd android && ./gradlew test       # Kotlin (mismos casos que en Python)
```

## Estructura

```
main.py                 # punto de entrada (escritorio)
qrgen/payloads.py       # contenido de cada tipo de QR
qrgen/generator.py      # generación y exportación de imágenes (con caché)
qrgen/theme.py          # tema visual industrial claro/oscuro
qrgen/gui.py            # interfaz gráfica (CustomTkinter)
qrgen/clipboard.py      # copiar imagen al portapapeles (Windows)
scripts/build_windows.py
android/                # app Android (Kotlin + Compose)
tests/                  # pruebas con pytest
```

## Licencia

[MIT](LICENSE) © 2026 Lucas Espinola
