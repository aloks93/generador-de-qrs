import pytest

from qrgen import payloads
from qrgen.generator import QROptions, make_image, save


def test_url_adds_scheme():
    assert payloads.url("ejemplo.com") == "https://ejemplo.com"
    assert payloads.url("http://a.b") == "http://a.b"


def test_url_required():
    with pytest.raises(ValueError):
        payloads.url("   ")


def test_wifi_escapes_special_chars():
    assert payloads.wifi("Mi;Red", "p:a,ss") == "WIFI:T:WPA;S:Mi\\;Red;P:p\\:a\\,ss;;"


def test_wifi_open_network():
    assert payloads.wifi("Libre", "ignorada", "Ninguna") == "WIFI:T:nopass;S:Libre;;"


def test_wifi_hidden_requires_password():
    assert payloads.wifi("X", "123", "WEP", hidden=True).endswith("H:true;;")
    with pytest.raises(ValueError):
        payloads.wifi("X", "", "WPA")


def test_vcard():
    card = payloads.vcard("Ana", "López", phone="+34 600-11-22", email="ana@x.com")
    assert card.startswith("BEGIN:VCARD\nVERSION:3.0")
    assert "N:López;Ana;;;" in card
    assert "FN:Ana López" in card
    assert "TEL;TYPE=CELL:+346001122" in card
    assert card.endswith("END:VCARD")


def test_email_encoding():
    assert payloads.email("a@b.com", "Hola mundo", "¿Qué tal?") == (
        "mailto:a@b.com?subject=Hola%20mundo&body=%C2%BFQu%C3%A9%20tal%3F"
    )
    assert payloads.email("a@b.com") == "mailto:a@b.com"


def test_phone_sms_whatsapp():
    assert payloads.phone("+34 600 000 000") == "tel:+34600000000"
    assert payloads.sms("600 111", "hola") == "SMSTO:600111:hola"
    assert payloads.whatsapp("+34 600", "hola que tal") == "https://wa.me/34600?text=hola%20que%20tal"


def test_geo():
    assert payloads.geo("40,4168", "-3.7038") == "geo:40.4168,-3.7038"
    with pytest.raises(ValueError):
        payloads.geo("100", "0")
    with pytest.raises(ValueError):
        payloads.geo("abc", "0")


def test_event():
    ev = payloads.event("Fiesta", "2026-12-31 20:00", "2026-12-31 23:59", "Casa")
    assert "DTSTART:20261231T200000" in ev
    assert "DTEND:20261231T235900" in ev
    assert "LOCATION:Casa" in ev
    with pytest.raises(ValueError):
        payloads.event("X", "2026-12-31 20:00", "2026-12-30 20:00")
    with pytest.raises(ValueError):
        payloads.event("X", "31/12/2026", "2026-12-31 20:00")


def test_crypto():
    assert payloads.crypto("bc1abc", "0,5", label="Café") == "bitcoin:bc1abc?amount=0.5&label=Caf%C3%A9"
    assert payloads.crypto("0xabc", currency="ethereum") == "ethereum:0xabc"


def test_make_image_and_overflow():
    img = make_image("https://ejemplo.com", QROptions(fill_color="#ff0000"))
    assert img.mode == "RGB"
    with pytest.raises(ValueError):
        make_image("x" * 5000)


def test_save_formats(tmp_path):
    for ext in ("png", "svg", "jpg"):
        out = save("hola", tmp_path / f"qr.{ext}", QROptions(fill_color="#123456"))
        assert out.stat().st_size > 0
    assert "#123456" in (tmp_path / "qr.svg").read_text(encoding="utf-8")
