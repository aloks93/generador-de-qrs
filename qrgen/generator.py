"""Renderizado de códigos (QR, 2D y de barras) a imagen PIL o SVG, con estilos avanzados.

Con el estilo por defecto (módulos cuadrados, sin degradado) se dibuja con una
imagen en paleta escalada por vecino más cercano: rápido y con bordes nítidos.
Con formas o degradados se dibuja a 4x y se reduce con antialias.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

from .symbology import ERROR_LEVELS, SYMBOLOGIES, Symbol, encode

__all__ = ["ERROR_LEVELS", "QROptions", "MODULE_SHAPES", "EYE_SHAPES", "GRADIENTS",
           "get_symbol", "get_matrix", "make_image", "make_svg", "save"]

MODULE_SHAPES = {"square": "Cuadrado", "rounded": "Redondeado", "dots": "Puntos", "diamond": "Rombo"}
EYE_SHAPES = {"square": "Cuadrado", "rounded": "Redondeado", "circle": "Círculo"}
GRADIENTS = {"none": "Sin degradado", "horizontal": "Horizontal", "vertical": "Vertical",
             "diagonal": "Diagonal", "radial": "Radial"}

SUPERSAMPLE = 4


@dataclass
class QROptions:
    # Básicas
    fill_color: str = "#000000"
    back_color: str = "#ffffff"
    box_size: int = 10
    border: int = 4
    error_level: str = "M (15%)"
    logo_path: str | None = None
    # Avanzadas
    symbology: str = "QR"
    version: int | None = None  # versión mínima del QR (1-40)
    mask: int | None = None  # patrón de máscara del QR (0-7)
    transparent: bool = False
    gradient: str = "none"
    gradient_color: str = "#1a3d8f"
    module_shape: str = "square"
    module_scale: float = 1.0  # 0.5-1.0: tamaño del módulo dentro de su celda
    eye_shape: str = "square"
    eye_color: str | None = None  # None = mismo que el código
    eye_inner_color: str | None = None
    logo_ratio: float = 0.22  # lado máximo del logo respecto al código
    logo_pad: bool = True  # recuadro del color de fondo detrás del logo
    caption: str = ""  # texto debajo del código
    caption_size: int = 0  # 0 = automático
    caption_color: str | None = None
    bar_height: int = 40  # altura de las barras lineales, en módulos
    show_text: bool = True  # texto legible bajo los códigos de barras


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _level(opts: QROptions) -> str:
    # El logo tapa parte del código: se necesita la máxima corrección.
    return "H (30%)" if opts.logo_path else opts.error_level


def get_symbol(data: str, opts: QROptions | None = None) -> Symbol:
    opts = opts or QROptions()
    return encode(data, opts.symbology, _level(opts), opts.version, opts.mask)


def get_matrix(data: str, opts: QROptions | None = None) -> tuple[tuple[bool, ...], ...]:
    """Matriz de un código 2D incluyendo la zona de silencio (borde)."""
    opts = opts or QROptions()
    sym = get_symbol(data, opts)
    b = opts.border
    blank = (False,) * (sym.width + 2 * b)
    return (blank,) * b + tuple((False,) * b + row + (False,) * b for row in sym.cells) + (blank,) * b


# ---------- Geometría común ----------

@dataclass
class _Layout:
    sym: Symbol
    cols: int  # celdas de ancho, con borde
    rows: int  # celdas de alto de la zona del código, con borde
    bx: int  # borde horizontal (celdas)
    by: int  # borde vertical (celdas)
    bar_rows: int  # filas que ocupa cada módulo (1 en 2D, bar_height en lineales)
    caption: str
    caption_cells: float  # alto de la banda de texto, en celdas
    caption_font: float  # tamaño de letra, en celdas


def _layout(data: str, opts: QROptions) -> _Layout:
    sym = get_symbol(data, opts)
    if sym.linear:
        bx, by, bar_rows = max(opts.border, 1) * 2, max(opts.border // 2, 1), max(opts.bar_height, 5)
        rows = bar_rows + 2 * by
    else:
        bx = by = opts.border
        bar_rows = 1
        rows = sym.height + 2 * by
    cols = sym.width + 2 * bx
    caption = opts.caption.strip()
    if sym.linear and opts.show_text:
        caption = sym.text  # en los lineales manda el texto legible (con dígito de control)
    font = opts.caption_size / opts.box_size if opts.caption_size else max(2.0, cols * (0.07 if not sym.linear else 0.09))
    if sym.linear and not opts.caption_size:
        font = min(font, bar_rows * 0.35)
    caption_cells = font * 1.5 if caption else 0.0
    return _Layout(sym, cols, rows, bx, by, bar_rows, caption, caption_cells, font)


def _is_eye(sym: Symbol, x: int, y: int) -> bool:
    return any(fx <= x < fx + 7 and fy <= y < fy + 7 for fx, fy in sym.finders)


def _styled(opts: QROptions) -> bool:
    """¿Hace falta dibujar módulo a módulo? (el degradado funciona también con el camino rápido)."""
    return (opts.module_shape != "square" or opts.module_scale < 1 or opts.eye_shape != "square"
            or bool(opts.eye_color) or bool(opts.eye_inner_color))


# ---------- Imagen ----------

@lru_cache(maxsize=8)
def _load_logo(path: str, mtime: float) -> Image.Image:
    with Image.open(path) as img:
        return img.convert("RGBA")


def _font(size: int, mono: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (["consolab.ttf", "consola.ttf", "DejaVuSansMono-Bold.ttf", "Menlo.ttc"] if mono
             else ["arialbd.ttf", "seguisb.ttf", "DejaVuSans-Bold.ttf", "Helvetica.ttc"])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _shape(draw: ImageDraw.ImageDraw, shape: str, box: tuple[float, float, float, float], fill: int) -> None:
    x0, y0, x1, y1 = box
    if shape == "dots" or shape == "circle":
        draw.ellipse(box, fill=fill)
    elif shape == "rounded":
        draw.rounded_rectangle(box, radius=(x1 - x0) * 0.35, fill=fill)
    elif shape == "diamond":
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        draw.polygon([(cx, y0), (x1, cy), (cx, y1), (x0, cy)], fill=fill)
    else:
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=fill)


def _gradient_layer(size: tuple[int, int], c1: str, c2: str, kind: str) -> Image.Image:
    w, h = size
    if kind == "radial":
        ramp = Image.radial_gradient("L").resize((w, h), Image.BILINEAR)
    elif kind == "diagonal":
        side = int((w * w + h * h) ** 0.5) + 2
        ramp = Image.linear_gradient("L").resize((side, side), Image.BILINEAR).rotate(45, resample=Image.BILINEAR)
        ramp = ramp.crop(((side - w) // 2, (side - h) // 2, (side - w) // 2 + w, (side - h) // 2 + h))
    elif kind == "horizontal":
        ramp = Image.linear_gradient("L").rotate(90).resize((w, h), Image.BILINEAR)
    else:
        ramp = Image.linear_gradient("L").resize((w, h), Image.BILINEAR)
    return Image.composite(Image.new("RGB", size, c2), Image.new("RGB", size, c1), ramp)


def _module_mask(lay: _Layout, opts: QROptions, scale: int, styled: bool) -> tuple[Image.Image, Image.Image, Image.Image]:
    """Máscaras (módulos, anillo de ojos, centro de ojos) a la escala indicada."""
    sym = lay.sym
    w, h = lay.cols * scale, lay.rows * scale
    if not styled:
        # Camino rápido: una imagen de 1 píxel por módulo ampliada sin suavizado.
        raw = bytes(255 if cell else 0 for row in sym.cells for cell in row)
        small = Image.frombytes("L", (sym.width, sym.height), raw)
        mask = Image.new("L", (lay.cols, lay.rows), 0)
        if sym.linear:
            small = small.resize((sym.width, lay.bar_rows), Image.NEAREST)
        mask.paste(small, (lay.bx, lay.by))
        empty = Image.new("L", (w, h), 0)
        return mask.resize((w, h), Image.NEAREST), empty, empty

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    inset = (1 - max(0.3, min(opts.module_scale, 1.0))) * scale / 2
    for y, row in enumerate(sym.cells):
        for x, cell in enumerate(row):
            if not cell or _is_eye(sym, x, y):
                continue
            x0 = (x + lay.bx) * scale + inset
            y0 = (y + lay.by) * scale + inset
            _shape(draw, opts.module_shape, (x0, y0, x0 + scale - 2 * inset, y0 + scale - 2 * inset), 255)

    ring = Image.new("L", (w, h), 0)
    inner = Image.new("L", (w, h), 0)
    rd, idraw = ImageDraw.Draw(ring), ImageDraw.Draw(inner)
    shape = {"square": "square", "rounded": "rounded", "circle": "circle"}.get(opts.eye_shape, "square")
    for fx, fy in sym.finders:
        ox, oy = (fx + lay.bx) * scale, (fy + lay.by) * scale
        _shape(rd, shape, (ox, oy, ox + 7 * scale, oy + 7 * scale), 255)
        _shape(rd, shape, (ox + scale, oy + scale, ox + 6 * scale, oy + 6 * scale), 0)
        _shape(idraw, shape, (ox + 2 * scale, oy + 2 * scale, ox + 5 * scale, oy + 5 * scale), 255)
    return mask, ring, inner


def make_image(data: str, opts: QROptions | None = None) -> Image.Image:
    """Devuelve el código como imagen PIL (RGB, o RGBA si el fondo es transparente)."""
    opts = opts or QROptions()
    lay = _layout(data, opts)
    styled = _styled(opts) and not lay.sym.linear
    ss = SUPERSAMPLE if styled else 1
    scale = opts.box_size * ss
    w, h = lay.cols * scale, lay.rows * scale
    mode = "RGBA" if opts.transparent else "RGB"
    back = (0, 0, 0, 0) if opts.transparent else _rgb(opts.back_color)

    mask, ring, inner = _module_mask(lay, opts, scale, styled)
    if opts.gradient != "none":
        fill_layer = _gradient_layer((w, h), opts.fill_color, opts.gradient_color, opts.gradient)
    else:
        fill_layer = Image.new("RGB", (w, h), opts.fill_color)
    img = Image.new(mode, (w, h), back)
    img.paste(fill_layer, (0, 0), mask)
    if lay.sym.finders and styled:
        img.paste(Image.new("RGB", (w, h), opts.eye_color) if opts.eye_color else fill_layer, (0, 0), ring)
        inner_color = opts.eye_inner_color or opts.eye_color
        img.paste(Image.new("RGB", (w, h), inner_color) if inner_color else fill_layer, (0, 0), inner)
    if ss > 1:
        img = img.resize((lay.cols * opts.box_size, lay.rows * opts.box_size), Image.LANCZOS)

    if opts.logo_path and not lay.sym.linear:
        _paste_logo(img, lay, opts)
    if lay.caption:
        img = _add_caption(img, lay, opts)
    return img


def _logo_tile(opts: QROptions, code_side: int, box: int) -> Image.Image:
    path = str(opts.logo_path)
    logo = _load_logo(path, Path(path).stat().st_mtime).copy()
    pad = max(2, box // 2) if opts.logo_pad else 0
    ratio = max(0.05, min(opts.logo_ratio, 0.35))
    max_side = max(1, int(code_side * ratio) - pad * 2)
    logo.thumbnail((max_side, max_side), Image.LANCZOS)
    if not opts.logo_pad:
        return logo
    bg = (0, 0, 0, 0) if opts.transparent else (*_rgb(opts.back_color), 255)
    tile = Image.new("RGBA", (logo.size[0] + pad * 2, logo.size[1] + pad * 2), bg)
    tile.alpha_composite(logo, (pad, pad))
    return tile


def _paste_logo(img: Image.Image, lay: _Layout, opts: QROptions) -> None:
    box = opts.box_size
    tile = _logo_tile(opts, min(lay.sym.width, lay.sym.height) * box, box)
    cx, cy = lay.cols * box // 2, lay.rows * box // 2
    img.paste(tile, (cx - tile.size[0] // 2, cy - tile.size[1] // 2), tile)


def _add_caption(img: Image.Image, lay: _Layout, opts: QROptions) -> Image.Image:
    box = opts.box_size
    band = int(lay.caption_cells * box)
    out = Image.new(img.mode, (img.size[0], img.size[1] + band), img.getpixel((0, 0)))
    out.paste(img, (0, 0))
    draw = ImageDraw.Draw(out)
    font = _font(max(8, int(lay.caption_font * box)), mono=lay.sym.linear)
    color = opts.caption_color or opts.fill_color
    top = img.size[1] - (lay.by * box if lay.sym.linear else lay.by * box // 2)
    draw.text((out.size[0] / 2, top + band / 2), lay.caption, fill=color, font=font, anchor="mm")
    return out


# ---------- SVG ----------

def _svg_shape(shape: str, x: float, y: float, s: float) -> str:
    if shape in ("dots", "circle"):
        return f'<circle cx="{x + s / 2:g}" cy="{y + s / 2:g}" r="{s / 2:g}"/>'
    if shape == "rounded":
        return f'<rect x="{x:g}" y="{y:g}" width="{s:g}" height="{s:g}" rx="{s * 0.35:g}"/>'
    if shape == "diamond":
        c = s / 2
        return f'<path d="M{x + c:g} {y:g}L{x + s:g} {y + c:g}L{x + c:g} {y + s:g}L{x:g} {y + c:g}z"/>'
    return f'<rect x="{x:g}" y="{y:g}" width="{s:g}" height="{s:g}"/>'


def _svg_eye(shape: str, x: float, y: float, s: float, hole: float) -> str:
    """Anillo de ojo como trazado con regla par-impar (hueco central)."""
    def outline(px: float, py: float, side: float) -> str:
        if shape == "circle":
            r = side / 2
            return (f"M{px + r:g} {py:g}a{r:g} {r:g} 0 1 0 0.0001 0z")
        if shape == "rounded":
            r = side * 0.3
            return (f"M{px + r:g} {py:g}h{side - 2 * r:g}a{r:g} {r:g} 0 0 1 {r:g} {r:g}v{side - 2 * r:g}"
                    f"a{r:g} {r:g} 0 0 1 -{r:g} {r:g}h-{side - 2 * r:g}a{r:g} {r:g} 0 0 1 -{r:g} -{r:g}"
                    f"v-{side - 2 * r:g}a{r:g} {r:g} 0 0 1 {r:g} -{r:g}z")
        return f"M{px:g} {py:g}h{side:g}v{side:g}h-{side:g}z"
    return outline(x, y, s) + outline(x + hole, y + hole, s - 2 * hole)


def make_svg(data: str, opts: QROptions | None = None) -> str:
    """SVG vectorial con el mismo estilo que la imagen."""
    opts = opts or QROptions()
    lay = _layout(data, opts)
    sym = lay.sym
    total_h = lay.rows + lay.caption_cells
    defs, body = [], []
    fill = opts.fill_color
    if opts.gradient != "none":
        stops = f'<stop offset="0" stop-color="{opts.fill_color}"/><stop offset="1" stop-color="{opts.gradient_color}"/>'
        if opts.gradient == "radial":
            defs.append(f'<radialGradient id="g" cx="0.5" cy="0.5" r="0.7">{stops}</radialGradient>')
        else:
            x2, y2 = {"horizontal": (1, 0), "vertical": (0, 1), "diagonal": (1, 1)}[opts.gradient]
            defs.append(f'<linearGradient id="g" x1="0" y1="0" x2="{x2}" y2="{y2}">{stops}</linearGradient>')
        fill = "url(#g)"

    if not opts.transparent:
        body.append(f'<rect width="{lay.cols}" height="{total_h:g}" fill="{opts.back_color}"/>')

    styled = _styled(opts) and not sym.linear
    if not styled:
        parts = []
        for y, row in enumerate(sym.cells):
            x = 0
            while x < sym.width:
                if row[x]:
                    start = x
                    while x < sym.width and row[x]:
                        x += 1
                    hgt = lay.bar_rows
                    parts.append(f"M{start + lay.bx} {y * hgt + lay.by}h{x - start}v{hgt}h-{x - start}z")
                else:
                    x += 1
        body.append(f'<path d="{"".join(parts)}" fill="{fill}" shape-rendering="crispEdges"/>')
    else:
        s = max(0.3, min(opts.module_scale, 1.0))
        inset = (1 - s) / 2
        shapes = [
            _svg_shape(opts.module_shape, x + lay.bx + inset, y + lay.by + inset, s)
            for y, row in enumerate(sym.cells) for x, cell in enumerate(row)
            if cell and not _is_eye(sym, x, y)
        ]
        body.append(f'<g fill="{fill}">{"".join(shapes)}</g>')
        eye_shape = opts.eye_shape if opts.eye_shape in EYE_SHAPES else "square"
        ring_color = opts.eye_color or fill
        inner_color = opts.eye_inner_color or opts.eye_color or fill
        for fx, fy in sym.finders:
            x, y = fx + lay.bx, fy + lay.by
            body.append(f'<path d="{_svg_eye(eye_shape, x, y, 7, 1)}" fill="{ring_color}" fill-rule="evenodd"/>')
            body.append(f'<g fill="{inner_color}">{_svg_shape(eye_shape, x + 2, y + 2, 3)}</g>')

    if opts.logo_path and not sym.linear:
        px = 16
        tile = _logo_tile(opts, min(sym.width, sym.height) * px, px)
        buf = io.BytesIO()
        tile.save(buf, "PNG")
        w, h = tile.size[0] / px, tile.size[1] / px
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        body.append(f'<image x="{(lay.cols - w) / 2:g}" y="{(lay.rows - h) / 2:g}" width="{w:g}" height="{h:g}" '
                    f'href="data:image/png;base64,{b64}"/>')

    if lay.caption:
        top = lay.rows - (lay.by if sym.linear else lay.by / 2)
        family = "monospace" if sym.linear else "Arial, Helvetica, sans-serif"
        body.append(
            f'<text x="{lay.cols / 2:g}" y="{top + lay.caption_cells / 2:g}" font-family="{family}" font-weight="bold" '
            f'font-size="{lay.caption_font:g}" text-anchor="middle" dominant-baseline="central" '
            f'fill="{opts.caption_color or opts.fill_color}">{escape(lay.caption)}</text>'
        )

    size_w = lay.cols * opts.box_size
    size_h = round(total_h * opts.box_size)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size_w}" height="{size_h}" '
        f'viewBox="0 0 {lay.cols} {total_h:g}">'
        + (f"<defs>{''.join(defs)}</defs>" if defs else "") + "".join(body) + "</svg>\n"
    )


def save(data: str, path: str | Path, opts: QROptions | None = None) -> Path:
    """Guarda el código en PNG, JPG, BMP o SVG según la extensión del archivo."""
    opts = opts or QROptions()
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".svg":
        path.write_text(make_svg(data, opts), encoding="utf-8")
    elif ext in (".png", ".jpg", ".jpeg", ".bmp"):
        img = make_image(data, opts)
        if ext == ".png":
            img.save(path, optimize=True)
        else:
            if img.mode == "RGBA":  # JPG/BMP no admiten transparencia
                flat = Image.new("RGB", img.size, opts.back_color)
                flat.paste(img, (0, 0), img)
                img = flat
            img.save(path, **({"quality": 95, "subsampling": 0} if ext != ".bmp" else {}))
    else:
        raise ValueError("Formato no soportado. Usa .png, .jpg, .bmp o .svg.")
    return path

