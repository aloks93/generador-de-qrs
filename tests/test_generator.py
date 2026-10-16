import pytest
from PIL import Image

from qrgen.generator import QROptions, get_matrix, make_image, make_svg, save


def test_image_matches_matrix():
    opts = QROptions(fill_color="#112233", back_color="#ffeedd", box_size=5, border=2)
    matrix = get_matrix("hola", opts)
    img = make_image("hola", opts)
    assert img.size == (len(matrix) * 5,) * 2
    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            expected = (0x11, 0x22, 0x33) if cell else (0xFF, 0xEE, 0xDD)
            assert img.getpixel((x * 5 + 2, y * 5 + 2)) == expected


def test_empty_data_raises():
    with pytest.raises(ValueError):
        make_image("")


def test_too_long_raises():
    with pytest.raises(ValueError, match="demasiado largos"):
        make_image("x" * 5000)


def test_svg_uses_colors():
    svg = make_svg("hola", QROptions(fill_color="#ff0000", back_color="#00ff00"))
    assert 'fill="#ff0000"' in svg and 'fill="#00ff00"' in svg
    assert svg.startswith("<?xml")


def test_logo_forces_high_correction_and_embeds_in_svg(tmp_path):
    logo = tmp_path / "logo.png"
    Image.new("RGB", (40, 40), "red").save(logo)
    plain = get_matrix("https://ejemplo.com", QROptions(error_level="L (7%)"))
    with_logo = get_matrix("https://ejemplo.com", QROptions(error_level="L (7%)", logo_path=str(logo)))
    assert len(with_logo) > len(plain)  # H necesita más módulos
    assert "data:image/png;base64," in make_svg("x", QROptions(logo_path=str(logo)))
    img = make_image("https://ejemplo.com", QROptions(logo_path=str(logo)))
    center = (img.size[0] // 2, img.size[1] // 2)
    assert img.getpixel(center) == (255, 0, 0)


@pytest.mark.parametrize("ext", [".png", ".jpg", ".bmp", ".svg"])
def test_save_formats(tmp_path, ext):
    path = save("hola", tmp_path / f"qr{ext}")
    assert path.exists() and path.stat().st_size > 0


def test_save_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        save("hola", tmp_path / "qr.gif")
