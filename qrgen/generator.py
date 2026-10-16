"""Generación de imágenes QR a partir de un texto.

El código se dibuja directamente desde la matriz de módulos con Pillow
(una imagen en paleta escalada con vecino más cercano), lo que es mucho más
rápido que el renderizado módulo a módulo de ``qrcode`` y deja bordes nítidos.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import qrcode
from PIL import Image
from qrcode.exceptions import DataOverflowError

ERROR_LEVELS = {
    "L (7%)": qrcode.constants.ERROR_CORRECT_L,
    "M (15%)": qrcode.constants.ERROR_CORRECT_M,
    "Q (25%)": qrcode.constants.ERROR_CORRECT_Q,
    "H (30%)": qrcode.constants.ERROR_CORRECT_H,
}

# Fracción máxima del lado del código que puede ocupar el logo con su margen.
LOGO_RATIO = 0.22


@dataclass
class QROptions:
    fill_color: str = "#000000"
    back_color: str = "#ffffff"
    box_size: int = 10
    border: int = 4
    error_level: str = "M (15%)"
    logo_path: str | None = None


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


@lru_cache(maxsize=256)
def _matrix(data: str, level: int, border: int) -> tuple[tuple[bool, ...], ...]:
    """Matriz de módulos (con borde). Se cachea: la vista previa la pide a menudo."""
    qr = qrcode.QRCode(error_correction=level, border=border)
    qr.add_data(data)
    try:
        qr.make(fit=True)
    except (DataOverflowError, ValueError):
        raise ValueError(
            "Los datos son demasiado largos para un código QR. "
            "Reduce el contenido o usa un enlace."
        ) from None
    return tuple(tuple(row) for row in qr.get_matrix())


def _level(opts: QROptions) -> int:
    if opts.logo_path:
        # El logo tapa parte del código: se necesita la máxima corrección.
        return qrcode.constants.ERROR_CORRECT_H
    return ERROR_LEVELS.get(opts.error_level, qrcode.constants.ERROR_CORRECT_M)


def get_matrix(data: str, opts: QROptions | None = None) -> tuple[tuple[bool, ...], ...]:
    opts = opts or QROptions()
    if not data:
        raise ValueError("No hay contenido para generar el QR.")
    return _matrix(data, _level(opts), opts.border)


@lru_cache(maxsize=8)
def _load_logo(path: str, mtime: float) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGBA")


def _logo_tile(opts: QROptions, code_side: int, box_size: int) -> Image.Image:
    """Logo centrado sobre un recuadro del color de fondo, ya escalado."""
    assert opts.logo_path
    path = str(opts.logo_path)
    logo = _load_logo(path, Path(path).stat().st_mtime).copy()
    pad = max(2, box_size // 2)
    max_side = max(1, int(code_side * LOGO_RATIO) - pad * 2)
    logo.thumbnail((max_side, max_side), Image.LANCZOS)
    tile = Image.new("RGB", (logo.size[0] + pad * 2, logo.size[1] + pad * 2), opts.back_color)
    tile.paste(logo, (pad, pad), logo)
    return tile


def make_image(data: str, opts: QROptions | None = None) -> Image.Image:
    """Devuelve el QR como imagen PIL en RGB."""
    opts = opts or QROptions()
    matrix = get_matrix(data, opts)
    n = len(matrix)
    raw = bytes(1 if cell else 0 for row in matrix for cell in row)
    img = Image.frombytes("P", (n, n), raw)
    img.putpalette([*_hex_to_rgb(opts.back_color), *_hex_to_rgb(opts.fill_color)])
    side = n * opts.box_size
    img = img.resize((side, side), Image.NEAREST).convert("RGB")

    if opts.logo_path:
        code_side = (n - 2 * opts.border) * opts.box_size
        tile = _logo_tile(opts, code_side, opts.box_size)
        img.paste(tile, ((side - tile.size[0]) // 2, (side - tile.size[1]) // 2))
    return img


def make_svg(data: str, opts: QROptions | None = None) -> str:
    """SVG vectorial; las filas se agrupan en tramos para reducir el tamaño."""
    opts = opts or QROptions()
    matrix = get_matrix(data, opts)
    n = len(matrix)
    parts: list[str] = []
    for y, row in enumerate(matrix):
        x = 0
        while x < n:
            if row[x]:
                start = x
                while x < n and row[x]:
                    x += 1
                parts.append(f"M{start} {y}h{x - start}v1h-{x - start}z")
            else:
                x += 1

    size = n * opts.box_size
    body = [
        f'<rect width="{n}" height="{n}" fill="{opts.back_color}"/>',
        f'<path d="{"".join(parts)}" fill="{opts.fill_color}" shape-rendering="crispEdges"/>',
    ]
    if opts.logo_path:
        # El logo se incrusta como PNG; se calcula en píxeles y se expresa en módulos.
        px = 16
        code_side = (n - 2 * opts.border) * px
        tile = _logo_tile(opts, code_side, px)
        buf = io.BytesIO()
        tile.save(buf, "PNG")
        w, h = tile.size[0] / px, tile.size[1] / px
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        body.append(
            f'<image x="{(n - w) / 2:g}" y="{(n - h) / 2:g}" width="{w:g}" height="{h:g}" '
            f'href="data:image/png;base64,{b64}"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {n} {n}">' + "".join(body) + "</svg>\n"
    )


def save(data: str, path: str | Path, opts: QROptions | None = None) -> Path:
    """Guarda el QR en PNG, JPG, BMP o SVG según la extensión del archivo."""
    opts = opts or QROptions()
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".svg":
        path.write_text(make_svg(data, opts), encoding="utf-8")
    elif ext in (".png", ".jpg", ".jpeg", ".bmp"):
        img = make_image(data, opts)
        if ext == ".png":
            img.save(path, optimize=True)
        elif ext in (".jpg", ".jpeg"):
            img.save(path, quality=95, subsampling=0)
        else:
            img.save(path)
    else:
        raise ValueError("Formato no soportado. Usa .png, .jpg, .bmp o .svg.")
    return path
