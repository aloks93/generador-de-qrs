"""Construcción del contenido (payload) de cada tipo de código QR.

Cada función recibe los datos del formulario y devuelve el texto que se
codificará en el QR. Lanzan ``ValueError`` si faltan datos obligatorios.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote, urlencode


def _required(value: str, field: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"El campo «{field}» es obligatorio.")
    return value


def _digits(phone: str) -> str:
    """Deja solo dígitos y un '+' inicial."""
    phone = phone.strip()
    plus = "+" if phone.startswith("+") else ""
    return plus + "".join(c for c in phone if c.isdigit())


def url(link: str) -> str:
    link = _required(link, "URL")
    if "://" not in link and not link.lower().startswith(("mailto:", "tel:")):
        link = "https://" + link
    return link


def file_link(link: str) -> str:
    """PDF, imagen, video u otro archivo ya alojado en internet."""
    return url(link)


def text(content: str) -> str:
    if not content or not content.strip():
        raise ValueError("El campo «Texto» es obligatorio.")
    return content


def _wifi_escape(value: str) -> str:
    for ch in ("\\", ";", ",", ":", '"'):
        value = value.replace(ch, "\\" + ch)
    return value


def wifi(ssid: str, password: str = "", security: str = "WPA", hidden: bool = False) -> str:
    ssid = _required(ssid, "Nombre de red (SSID)")
    security = (security or "WPA").upper()
    if security in ("NINGUNA", "NOPASS", "NONE", ""):
        security = "nopass"
        password = ""
    elif not password:
        raise ValueError("La contraseña es obligatoria para redes protegidas.")
    parts = [f"T:{security}", f"S:{_wifi_escape(ssid)}"]
    if password:
        parts.append(f"P:{_wifi_escape(password)}")
    if hidden:
        parts.append("H:true")
    return "WIFI:" + ";".join(parts) + ";;"


def _vcard_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    )


def vcard(
    first_name: str,
    last_name: str = "",
    phone: str = "",
    email: str = "",
    company: str = "",
    title: str = "",
    website: str = "",
    address: str = "",
) -> str:
    first_name = _required(first_name, "Nombre")
    e = _vcard_escape
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{e(last_name.strip())};{e(first_name)};;;",
        f"FN:{e((first_name + ' ' + last_name.strip()).strip())}",
    ]
    if company.strip():
        lines.append(f"ORG:{e(company.strip())}")
    if title.strip():
        lines.append(f"TITLE:{e(title.strip())}")
    if phone.strip():
        lines.append(f"TEL;TYPE=CELL:{_digits(phone)}")
    if email.strip():
        lines.append(f"EMAIL:{email.strip()}")
    if website.strip():
        lines.append(f"URL:{website.strip()}")
    if address.strip():
        lines.append(f"ADR:;;{e(address.strip())};;;;")
    lines.append("END:VCARD")
    return "\n".join(lines)


def email(to: str, subject: str = "", body: str = "") -> str:
    to = _required(to, "Destinatario")
    params = {k: v for k, v in (("subject", subject), ("body", body)) if v}
    query = urlencode(params, quote_via=quote)
    return f"mailto:{to}" + (f"?{query}" if query else "")


def phone(number: str) -> str:
    return "tel:" + _digits(_required(number, "Teléfono"))


def sms(number: str, message: str = "") -> str:
    return f"SMSTO:{_digits(_required(number, 'Teléfono'))}:{message}"


def whatsapp(number: str, message: str = "") -> str:
    digits = _digits(_required(number, "Teléfono")).lstrip("+")
    link = f"https://wa.me/{digits}"
    if message:
        link += "?text=" + quote(message)
    return link


def geo(latitude: str, longitude: str) -> str:
    try:
        lat = float(_required(latitude, "Latitud").replace(",", "."))
        lon = float(_required(longitude, "Longitud").replace(",", "."))
    except ValueError as exc:
        if "obligatorio" in str(exc):
            raise
        raise ValueError("Latitud y longitud deben ser números.") from None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordenadas fuera de rango.")
    return f"geo:{lat},{lon}"


DATE_FORMAT = "%Y-%m-%d %H:%M"


def _ical_date(value: str, field: str) -> str:
    try:
        dt = datetime.strptime(_required(value, field), DATE_FORMAT)
    except ValueError as exc:
        if "obligatorio" in str(exc):
            raise
        raise ValueError(f"«{field}» debe tener el formato AAAA-MM-DD HH:MM.") from None
    return dt.strftime("%Y%m%dT%H%M%S")


def event(title: str, start: str, end: str, location: str = "", description: str = "") -> str:
    title = _required(title, "Título")
    dtstart = _ical_date(start, "Inicio")
    dtend = _ical_date(end, "Fin")
    if dtend < dtstart:
        raise ValueError("La fecha de fin no puede ser anterior al inicio.")
    lines = ["BEGIN:VEVENT", f"SUMMARY:{title}", f"DTSTART:{dtstart}", f"DTEND:{dtend}"]
    if location.strip():
        lines.append(f"LOCATION:{location.strip()}")
    if description.strip():
        lines.append(f"DESCRIPTION:{description.strip()}")
    lines.append("END:VEVENT")
    return "\n".join(lines)


def crypto(address: str, amount: str = "", currency: str = "bitcoin", label: str = "") -> str:
    address = _required(address, "Dirección")
    params = {}
    if amount.strip():
        try:
            float(amount.replace(",", "."))
        except ValueError:
            raise ValueError("La cantidad debe ser un número.") from None
        params["amount"] = amount.strip().replace(",", ".")
    if label.strip():
        params["label"] = label.strip()
    query = urlencode(params, quote_via=quote)
    return f"{currency.lower()}:{address}" + (f"?{query}" if query else "")


SOCIAL_NETWORKS = {
    "Instagram": "https://instagram.com/{}",
    "Facebook": "https://facebook.com/{}",
    "TikTok": "https://tiktok.com/@{}",
    "X / Twitter": "https://x.com/{}",
    "YouTube": "https://youtube.com/@{}",
    "LinkedIn": "https://linkedin.com/in/{}",
    "GitHub": "https://github.com/{}",
    "Twitch": "https://twitch.tv/{}",
}


def _handle(user: str, field: str) -> str:
    return quote(_required(user, field).lstrip("@").strip("/"), safe="._-")


def social(network: str, user: str) -> str:
    template = SOCIAL_NETWORKS.get(network)
    if template is None:
        raise ValueError("Red social no soportada.")
    return template.format(_handle(user, "Usuario"))


def telegram(user: str) -> str:
    return f"https://t.me/{_handle(user, 'Usuario')}"


def maps(query: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + quote(_required(query, "Dirección o lugar"))


def paypal(user: str, amount: str = "", currency: str = "EUR") -> str:
    link = f"https://paypal.me/{_handle(user, 'Usuario de PayPal')}"
    if amount.strip():
        try:
            float(amount.replace(",", "."))
        except ValueError:
            raise ValueError("La cantidad debe ser un número.") from None
        link += f"/{amount.strip().replace(',', '.')}{currency.upper()}"
    return link


def _mecard_escape(value: str) -> str:
    for ch in ("\\", ";", ",", ":"):
        value = value.replace(ch, "\\" + ch)
    return value


def mecard(name: str, phone: str = "", email: str = "", note: str = "") -> str:
    """Contacto en formato MeCard: más corto que vCard (QR más pequeño)."""
    e = _mecard_escape
    parts = [f"N:{e(_required(name, 'Nombre'))}"]
    if phone.strip():
        parts.append(f"TEL:{_digits(phone)}")
    if email.strip():
        parts.append(f"EMAIL:{e(email.strip())}")
    if note.strip():
        parts.append(f"NOTE:{e(note.strip())}")
    return "MECARD:" + ";".join(parts) + ";;"
