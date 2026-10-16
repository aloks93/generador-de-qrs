"""Cada código generado debe poder leerse con un decodificador real (zxing-cpp)."""

import pytest
import zxingcpp
from PIL import Image

from qrgen.generator import QROptions, make_image, make_svg
from qrgen.symbology import SYMBOLOGIES, encode


def _read(img: Image.Image) -> str:
    if img.mode == "RGBA":
        flat = Image.new("RGB", img.size, "white")
        flat.paste(img, (0, 0), img)
        img = flat
    result = zxingcpp.read_barcode(img)
    assert result is not None, "el código no se pudo leer"
    return result.text


CONTENT = {s.code: s.example or "https://ejemplo.com/123" for s in SYMBOLOGIES.values()}
CONTENT["MICROQR"] = "HOLA 123"


@pytest.mark.parametrize("code", list(SYMBOLOGIES))
def test_every_symbology_scans(code):
    data = CONTENT[code]
    img = make_image(data, QROptions(symbology=code, box_size=6))
    # Los lineales añaden el dígito de control: se compara con el texto codificado.
    assert _read(img) == encode(data, code).text


@pytest.mark.parametrize(
    "style",
    [
        dict(module_shape="dots", module_scale=0.9),
        dict(module_shape="rounded", eye_shape="rounded", eye_color="#e05a00"),
        dict(module_shape="diamond", eye_shape="circle", eye_inner_color="#ff0000"),
        dict(gradient="diagonal", gradient_color="#1a3d8f"),
        dict(gradient="radial", gradient_color="#0b5d3b", module_shape="dots"),
        dict(transparent=True),
        dict(caption="ESCANÉAME", border=2),
        dict(fill_color="#ffffff", back_color="#101010"),
    ],
)
def test_styled_qr_still_scans(style):
    data = "https://github.com/aloks93/generador-de-qrs"
    img = make_image(data, QROptions(box_size=8, error_level="Q (25%)", **style))
    if style.get("fill_color") == "#ffffff":
        from PIL import ImageOps
        img = ImageOps.invert(img.convert("RGB"))
    assert _read(img) == data


def test_qr_version_and_mask():
    sym = encode("hola", "QR", "M (15%)", 5, 3)
    assert sym.version == 5 and sym.width == 37


def test_linear_has_caption_and_height():
    img = make_image("590123412345", QROptions(symbology="EAN13", box_size=3, bar_height=30))
    assert img.size[1] > 30 * 3
    no_text = make_image("590123412345", QROptions(symbology="EAN13", box_size=3, bar_height=30, show_text=False))
    assert no_text.size[1] < img.size[1]


def test_invalid_barcode_content_message():
    with pytest.raises(ValueError, match="EAN-13"):
        make_image("abc", QROptions(symbology="EAN13"))


@pytest.mark.parametrize("code", ["QR", "EAN13", "DATAMATRIX"])
def test_svg_all_styles(code):
    svg = make_svg(CONTENT[code], QROptions(symbology=code, module_shape="dots", eye_shape="circle",
                                            gradient="vertical", caption="Hola & adiós", transparent=True,
                                            show_text=False))
    assert "<svg" in svg and "linearGradient" in svg and "Hola &amp; adiós" in svg
