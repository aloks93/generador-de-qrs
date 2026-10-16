# Generador de QRs

Aplicación de escritorio en Python para crear códigos QR de todo tipo, con vista previa en vivo, colores personalizados, logo central y exportación a PNG, JPG, BMP o SVG.

## Tipos de QR soportados

| Tipo | Qué hace al escanearlo |
|---|---|
| 🔗 Enlace / URL | Abre la página web |
| 📄 PDF / Archivo | Abre un PDF, imagen, video o cualquier archivo alojado en internet |
| 📝 Texto | Muestra el texto |
| 📶 WiFi | Conecta a la red (WPA, WEP o abierta, incluso redes ocultas) |
| 👤 Contacto (vCard) | Guarda el contacto en la agenda |
| ✉️ Email | Abre un correo con destinatario, asunto y mensaje |
| 📞 Teléfono | Inicia una llamada |
| 💬 SMS | Prepara un SMS |
| 🟢 WhatsApp | Abre un chat de WhatsApp con mensaje opcional |
| 📍 Ubicación | Abre las coordenadas en el mapa |
| 📅 Evento | Añade un evento al calendario |
| ₿ Cripto | Solicitud de pago (Bitcoin, Ethereum, Litecoin…) |

### Sobre los PDFs y archivos

Un código QR solo puede guardar unos 3 KB, así que **un archivo no cabe dentro del QR**. Para compartir un PDF:

1. Súbelo a Google Drive, Dropbox, OneDrive o similar.
2. Compártelo como «cualquiera con el enlace puede ver».
3. Pega ese enlace en la sección **📄 PDF / Archivo**.

## Instalación

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/aloks93/generador-de-qrs.git
cd generador-de-qrs
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

1. Elige el tipo de QR en el menú de la izquierda.
2. Rellena los campos; la vista previa se actualiza automáticamente.
3. Personalízalo (opcional): color del código y del fondo, tamaño, nivel de corrección de errores y logo.
4. Pulsa **💾 Guardar** (PNG, SVG, JPG o BMP) o **📋 Copiar** para pegarlo directamente en otra aplicación (Windows).

> Al añadir un logo se usa automáticamente la corrección de errores H (30%) para que el QR siga leyéndose. El formato SVG no incluye el logo.

### Uso como librería

```python
from qrgen import payloads
from qrgen.generator import QROptions, save

datos = payloads.wifi("MiCasa", "clave-secreta")
save(datos, "wifi.png", QROptions(fill_color="#1a3d8f"))
```

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest
```

## Estructura

```
main.py              # punto de entrada
qrgen/payloads.py    # formato del contenido de cada tipo de QR
qrgen/generator.py   # generación y exportación de imágenes
qrgen/clipboard.py   # copiar imagen al portapapeles (Windows)
qrgen/gui.py         # interfaz gráfica (CustomTkinter)
tests/               # pruebas con pytest
```

## Licencia

MIT
