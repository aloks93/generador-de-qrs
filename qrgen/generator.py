"""Generación de imágenes QR a partir de un texto."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import qrcode
import qrcode.image.svg
from qrcode.exceptions import DataOverflowError
from PIL import Image

ERROR_LEVELS = {
    "L (7%)": qrcode.constants.ERROR_CORRECT_L,
    "M (15%)": qrcode.constants.ERROR_CORRECT_M,
    "Q (25%)": qrcode.constants.ERROR_CORRECT_Q,
    "H (30%)": qrcode.constants.ERROR_CORRECT_H,
}


@dataclass
class QROptions:
    fill_color: str = "#000000"
    back_color: str = "#ffffff"
    box_size: int = 10
    border: int = 4
    error_level: str = "M (15%)"
    logo_path: str | None = None


def _build(data: str, opts: QROptions) -> qrcode.QRCode:
    level = ERROR_LEVELS.get(opts.error_level, qrcode.constants.ERROR_CORRECT_M)
    if opts.logo_path:
        # El logo tapa parte del código: se necesita la máxima corrección.
        level = qrcode.constants.ERROR_CORRECT_H
    qr = qrcode.QRCode(error_correction=level, box_size=opts.box_size, border=opts.border)
    qr.add_data(data)
    try:
        qr.make(fit=True)
    except (DataOverflowError, ValueError):
        raise ValueError(
            "Los datos son demasiado largos para un código QR. "
            "Reduce el contenido o usa un enlace."
        ) from None
    return qr


def make_image(data: str, opts: QROptions | None = None) -> Image.Image:
    """Devuelve el QR como imagen PIL en RGB."""
    opts = opts or QROptions()
    if not data:
        raise ValueError("No hay contenido para generar el QR.")
    qr = _build(data, opts)
    img = qr.make_image(fill_color=opts.fill_color, back_color=opts.back_color).convert("RGB")

    if opts.logo_path:
        logo = Image.open(opts.logo_path).convert("RGBA")
        # Limita el logo (con su margen) a ~22% del lado del código para no
        # superar la capacidad de corrección.
        code_side = qr.modules_count * opts.box_size
        pad = max(2, opts.box_size // 2)
        max_side = max(1, int(code_side * 0.22) - pad * 2)
        logo.thumbnail((max_side, max_side), Image.LANCZOS)
        bg = Image.new("RGB", (logo.size[0] + pad * 2, logo.size[1] + pad * 2), opts.back_color)
        bg.paste(logo, (pad, pad), logo)
        pos = ((img.size[0] - bg.size[0]) // 2, (img.size[1] - bg.size[1]) // 2)
        img.paste(bg, pos)
    return img


def save(data: str, path: str | Path, opts: QROptions | None = None) -> Path:
    """Guarda el QR en PNG, JPG o SVG según la extensión del archivo."""
    opts = opts or QROptions()
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".svg":
        qr = _build(data, opts)
        svg = qr.make_image(image_factory=qrcode.image.svg.SvgPathFillImage)
        svg.save(str(path))
        # Aplica los colores elegidos (el SVG por defecto es negro sobre blanco).
        content = path.read_text(encoding="utf-8")
        content = content.replace('fill="#000000"', f'fill="{opts.fill_color}"', 1)
        content = content.replace('fill="white"', f'fill="{opts.back_color}"', 1)
        path.write_text(content, encoding="utf-8")
    elif ext in (".png", ".jpg", ".jpeg", ".bmp"):
        make_image(data, opts).save(path)
    else:
        raise ValueError("Formato no soportado. Usa .png, .jpg, .bmp o .svg.")
    return path
