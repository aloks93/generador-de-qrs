"""Codificación de cada simbología (QR, 2D y códigos de barras lineales) a una matriz de módulos."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import qrcode
import zxingcpp
from qrcode.exceptions import DataOverflowError

ERROR_LEVELS = {
    "L (7%)": qrcode.constants.ERROR_CORRECT_L,
    "M (15%)": qrcode.constants.ERROR_CORRECT_M,
    "Q (25%)": qrcode.constants.ERROR_CORRECT_Q,
    "H (30%)": qrcode.constants.ERROR_CORRECT_H,
}


@dataclass(frozen=True)
class Symbology:
    code: str
    name: str
    linear: bool
    zx: str | None = None  # nombre en zxingcpp.BarcodeFormat (None = librería qrcode)
    hint: str = ""
    example: str = ""


SYMBOLOGIES: dict[str, Symbology] = {s.code: s for s in (
    Symbology("QR", "QR Code", False),
    Symbology("MICROQR", "Micro QR", False, "MicroQRCode", "Versión compacta del QR: hasta ~35 caracteres."),
    Symbology("DATAMATRIX", "Data Matrix", False, "DataMatrix"),
    Symbology("AZTEC", "Aztec", False, "Aztec"),
    Symbology("PDF417", "PDF417", False, "PDF417"),
    Symbology("EAN13", "EAN-13", True, "EAN13", "12 o 13 dígitos (el último es el dígito de control).", "590123412345"),
    Symbology("EAN8", "EAN-8", True, "EAN8", "7 u 8 dígitos.", "9638507"),
    Symbology("UPCA", "UPC-A", True, "UPCA", "11 o 12 dígitos.", "03600029145"),
    Symbology("UPCE", "UPC-E", True, "UPCE", "7 u 8 dígitos, empezando por 0.", "0123456"),
    Symbology("CODE128", "Code 128", True, "Code128", "Cualquier texto ASCII (letras, números y símbolos).", "ABC-12345"),
    Symbology("CODE39", "Code 39", True, "Code39", "Mayúsculas A-Z, dígitos y los símbolos - . $ / + % y espacio.", "CODE-39"),
    Symbology("CODE93", "Code 93", True, "Code93", "Mayúsculas A-Z, dígitos y - . $ / + % espacio.", "CODE93"),
    Symbology("ITF", "ITF (2 de 5)", True, "ITF", "Solo dígitos, en cantidad par.", "12345678"),
    Symbology("CODABAR", "Codabar", True, "Codabar", "Dígitos y - $ : / . + con inicio y fin A-D (p. ej. A123B).", "A40156B"),
)}

MATRIX_CODES = [c for c, s in SYMBOLOGIES.items() if not s.linear]
LINEAR_CODES = [c for c, s in SYMBOLOGIES.items() if s.linear]


@dataclass(frozen=True)
class Symbol:
    """Resultado de codificar: matriz de módulos (sin zona de silencio)."""

    cells: tuple[tuple[bool, ...], ...]
    linear: bool
    text: str  # texto legible (en lineales incluye el dígito de control)
    finders: tuple[tuple[int, int], ...] = field(default=())  # esquinas de los «ojos» 7x7
    version: int | None = None

    @property
    def width(self) -> int:
        return len(self.cells[0])

    @property
    def height(self) -> int:
        return len(self.cells)


def _qr(data: str, level: int, version: int | None, mask: int | None) -> Symbol:
    qr = qrcode.QRCode(error_correction=level, border=0, version=version, mask_pattern=mask)
    qr.add_data(data)
    try:
        qr.make(fit=True)
    except (DataOverflowError, ValueError):
        raise ValueError(
            "Los datos son demasiado largos para un código QR. Reduce el contenido o usa un enlace."
        ) from None
    cells = tuple(tuple(row) for row in qr.get_matrix())
    n = len(cells)
    return Symbol(cells, False, data, ((0, 0), (n - 7, 0), (0, n - 7)), qr.version)


def _zx(sym: Symbology, data: str, ec_level: str) -> Symbol:
    fmt = getattr(zxingcpp.BarcodeFormat, sym.zx)
    kwargs = {"ec_level": ec_level[0]} if sym.code == "MICROQR" else {}
    try:
        barcode = zxingcpp.create_barcode(data, fmt, **kwargs)
    except (ValueError, RuntimeError):
        detail = f" {sym.hint}" if sym.hint else ""
        raise ValueError(f"Contenido no válido para {sym.name}.{detail}") from None
    img = barcode.to_image(scale=1, add_quiet_zones=False, add_hrt=False)
    view = memoryview(img)
    h, w = view.shape[0], view.shape[1]
    raw = bytes(view)
    if sym.linear:
        rows = (tuple(raw[x] < 128 for x in range(w)),)
        return Symbol(rows, True, barcode.text)
    cells = tuple(tuple(raw[y * w + x] < 128 for x in range(w)) for y in range(h))
    finders = ((0, 0),) if sym.code == "MICROQR" else ()
    return Symbol(cells, False, barcode.text, finders)


@lru_cache(maxsize=256)
def encode(
    data: str,
    symbology: str = "QR",
    error_level: str = "M (15%)",
    version: int | None = None,
    mask: int | None = None,
) -> Symbol:
    if not data:
        raise ValueError("No hay contenido para generar el código.")
    sym = SYMBOLOGIES.get(symbology)
    if sym is None:
        raise ValueError(f"Simbología desconocida: {symbology}")
    if sym.zx is None:
        level = ERROR_LEVELS.get(error_level, qrcode.constants.ERROR_CORRECT_M)
        return _qr(data, level, version, mask)
    return _zx(sym, data, error_level)
