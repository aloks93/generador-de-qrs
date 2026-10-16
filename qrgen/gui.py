"""Interfaz gráfica del generador de QRs (CustomTkinter, estilo industrial)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox
from typing import Callable

import customtkinter as ctk
from PIL import Image

from . import __version__, clipboard, payloads, theme
from .generator import EYE_SHAPES, GRADIENTS, MODULE_SHAPES, QROptions, get_symbol, make_image, save
from .symbology import ERROR_LEVELS, MATRIX_CODES, SYMBOLOGIES
from .theme import font

APP_NAME = "Generador de QRs"
PREVIEW_SIZE = 264
DEBOUNCE_MS = 150
SETTINGS_PATH = Path.home() / ".generador-qrs.json"
LEVEL_KEYS = {key[0]: key for key in ERROR_LEVELS}  # "L" -> "L (7%)"
DEFAULTS = QROptions()


@dataclass
class Field:
    key: str
    label: str
    kind: str = "entry"  # entry | text | combo | check
    placeholder: str = ""
    options: list[str] = field(default_factory=list)
    show: str = ""
    advanced: bool = False  # solo visible en modo avanzado


@dataclass
class QRType:
    code: str
    name: str
    build: Callable[..., str]
    fields: list[Field]
    hint: str = ""
    symbology: str | None = None  # fija para los códigos de barras; None = QR / 2D elegible

    @property
    def linear(self) -> bool:
        return self.symbology is not None and SYMBOLOGIES[self.symbology].linear


QR_TYPES: list[QRType] = [
    QRType("URL", "Enlace / URL", payloads.url, [Field("link", "URL", placeholder="https://ejemplo.com")]),
    QRType(
        "FILE",
        "PDF / Archivo",
        payloads.file_link,
        [Field("link", "Enlace al archivo", placeholder="https://drive.google.com/...")],
        hint=(
            "Un QR solo guarda unos 3 KB: el archivo no cabe dentro. Súbelo a Google Drive, "
            "Dropbox u OneDrive, compártelo como «cualquiera con el enlace» y pega aquí el link."
        ),
    ),
    QRType("TXT", "Texto", payloads.text, [Field("content", "Texto", kind="text")]),
    QRType(
        "WIFI",
        "Red WiFi",
        payloads.wifi,
        [
            Field("ssid", "Nombre de red (SSID)"),
            Field("password", "Contraseña", show="•"),
            Field("security", "Seguridad", kind="combo", options=["WPA", "WEP", "Ninguna"]),
            Field("hidden", "Red oculta", kind="check", advanced=True),
        ],
    ),
    QRType(
        "VCF",
        "Contacto (vCard)",
        payloads.vcard,
        [
            Field("first_name", "Nombre"),
            Field("last_name", "Apellidos"),
            Field("phone", "Teléfono", placeholder="+34 600 000 000"),
            Field("email", "Email"),
            Field("company", "Empresa", advanced=True),
            Field("title", "Cargo", advanced=True),
            Field("website", "Sitio web", advanced=True),
            Field("address", "Dirección", advanced=True),
        ],
    ),
    QRType(
        "MECARD",
        "Contacto (MeCard)",
        payloads.mecard,
        [
            Field("name", "Nombre completo"),
            Field("phone", "Teléfono"),
            Field("email", "Email"),
            Field("note", "Nota", advanced=True),
        ],
        hint="Formato más corto que vCard: genera un QR más pequeño y fácil de leer.",
    ),
    QRType(
        "MAIL",
        "Email",
        payloads.email,
        [
            Field("to", "Destinatario", placeholder="nombre@correo.com"),
            Field("subject", "Asunto"),
            Field("body", "Mensaje", kind="text"),
        ],
    ),
    QRType("TEL", "Teléfono", payloads.phone, [Field("number", "Teléfono", placeholder="+34 600 000 000")]),
    QRType("SMS", "SMS", payloads.sms, [Field("number", "Teléfono"), Field("message", "Mensaje", kind="text")]),
    QRType(
        "WA",
        "WhatsApp",
        payloads.whatsapp,
        [
            Field("number", "Teléfono (con código de país)", placeholder="+34 600 000 000"),
            Field("message", "Mensaje", kind="text"),
        ],
    ),
    QRType("TG", "Telegram", payloads.telegram, [Field("user", "Usuario o canal", placeholder="@usuario")]),
    QRType(
        "SOC",
        "Redes sociales",
        payloads.social,
        [
            Field("network", "Red", kind="combo", options=list(payloads.SOCIAL_NETWORKS)),
            Field("user", "Usuario", placeholder="@usuario"),
        ],
    ),
    QRType(
        "GEO",
        "Ubicación (GPS)",
        payloads.geo,
        [
            Field("latitude", "Latitud", placeholder="40.4168"),
            Field("longitude", "Longitud", placeholder="-3.7038"),
        ],
    ),
    QRType("MAPS", "Google Maps", payloads.maps, [Field("query", "Dirección o lugar", placeholder="Plaza Mayor, Madrid")]),
    QRType(
        "CAL",
        "Evento",
        payloads.event,
        [
            Field("title", "Título"),
            Field("start", "Inicio", placeholder="2026-12-31 20:00"),
            Field("end", "Fin", placeholder="2026-12-31 23:59"),
            Field("location", "Lugar"),
            Field("description", "Descripción", kind="text", advanced=True),
        ],
    ),
    QRType(
        "PAY",
        "PayPal",
        payloads.paypal,
        [
            Field("user", "Usuario de PayPal.me"),
            Field("amount", "Cantidad (opcional)"),
            Field("currency", "Moneda", kind="combo", options=["EUR", "USD", "ARS", "MXN", "GBP"], advanced=True),
        ],
    ),
    QRType(
        "BTC",
        "Cripto",
        payloads.crypto,
        [
            Field(
                "currency",
                "Moneda",
                kind="combo",
                options=["bitcoin", "ethereum", "litecoin", "dogecoin", "bitcoincash"],
            ),
            Field("address", "Dirección de la billetera"),
            Field("amount", "Cantidad (opcional)"),
            Field("label", "Etiqueta (opcional)", advanced=True),
        ],
    ),
]

BARCODE_TYPES: list[QRType] = [
    QRType(
        code,
        SYMBOLOGIES[code].name,
        lambda content: content.strip(),
        [Field("content", "Contenido", placeholder=SYMBOLOGIES[code].example)],
        hint=SYMBOLOGIES[code].hint,
        symbology=code,
    )
    for code in ("EAN13", "EAN8", "UPCA", "UPCE", "CODE128", "CODE39", "CODE93", "ITF", "CODABAR")
]

ALL_TYPES = QR_TYPES + BARCODE_TYPES


def resource(name: str) -> Path:
    """Ruta a un recurso, tanto en desarrollo como en el .exe de PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / name


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _store_settings(**values) -> None:
    try:
        SETTINGS_PATH.write_text(json.dumps({**_load_settings(), **values}), encoding="utf-8")
    except OSError:
        pass


def _contrast_text(color: str) -> str:
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#000000" if (r * 299 + g * 587 + b * 114) / 1000 > 140 else "#FFFFFF"


class Form:
    """Formulario de un tipo de código. Se crea una vez y se conserva al cambiar de tipo."""

    def __init__(self, master, qr_type: QRType, on_change: Callable[..., None]) -> None:
        self.qr_type = qr_type
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)
        self.widgets: dict[str, object] = {}
        self.advanced_rows: list[ctk.CTkBaseClass] = []

        row = 0
        for f in qr_type.fields:
            parts: list = []
            if f.kind == "check":
                var = ctk.BooleanVar(value=False)
                box = ctk.CTkCheckBox(
                    self.frame, text=f.label, variable=var, command=on_change, font=font(size=13),
                    checkbox_width=18, checkbox_height=18,
                )
                box.grid(row=row, column=0, sticky="w", pady=(14, 0))
                self.widgets[f.key] = var
                parts.append(box)
                row += 1
            else:
                label = ctk.CTkLabel(
                    self.frame, text=f.label.upper(), font=font("mono", 11), text_color=theme.MUTED, anchor="w"
                )
                label.grid(row=row, column=0, sticky="w", pady=(14, 4))
                row += 1
                if f.kind == "text":
                    widget = ctk.CTkTextbox(self.frame, height=110, font=font(size=13))
                    widget.bind("<KeyRelease>", on_change)
                elif f.kind == "combo" and len(f.options) <= 3:
                    widget = ctk.CTkSegmentedButton(
                        self.frame, values=f.options, command=on_change, font=font("mono", 12), height=34
                    )
                    widget.set(f.options[0])
                elif f.kind == "combo":
                    widget = ctk.CTkOptionMenu(
                        self.frame, values=f.options, command=on_change, font=font(size=13), height=34,
                        dropdown_font=font(size=13),
                    )
                    widget.set(f.options[0])
                else:
                    widget = ctk.CTkEntry(
                        self.frame, placeholder_text=f.placeholder, show=f.show, height=36, font=font(size=13)
                    )
                    widget.bind("<KeyRelease>", on_change)
                widget.grid(row=row, column=0, sticky="ew")
                self.widgets[f.key] = widget
                parts += [label, widget]
                row += 1
            if f.advanced:
                self.advanced_rows += parts

    def set_advanced(self, advanced: bool) -> None:
        for widget in self.advanced_rows:
            widget.grid() if advanced else widget.grid_remove()

    def values(self, advanced: bool) -> dict:
        values = {}
        for f in self.qr_type.fields:
            if f.advanced and not advanced:
                continue  # en modo normal los campos avanzados no se usan
            widget = self.widgets[f.key]
            if isinstance(widget, ctk.BooleanVar):
                values[f.key] = widget.get()
            elif isinstance(widget, ctk.CTkTextbox):
                values[f.key] = widget.get("1.0", "end-1c")
            else:
                values[f.key] = widget.get()
        return values

    def focus_first(self) -> None:
        for widget in self.widgets.values():
            if isinstance(widget, (ctk.CTkEntry, ctk.CTkTextbox)):
                widget.focus_set()
                return


class App(ctk.CTk):
    def __init__(self) -> None:
        self.settings = _load_settings()
        ctk.set_appearance_mode(self.settings.get("appearance", "dark"))
        theme.apply()
        super().__init__()
        theme.Fonts.load()

        self.title(APP_NAME)
        self.geometry("1240x760")
        self.minsize(1080, 660)
        if sys.platform == "win32" and resource("icon.ico").exists():
            self.iconbitmap(str(resource("icon.ico")))

        self.advanced = bool(self.settings.get("advanced", False))
        self.options = QROptions()
        self.matrix_symbology = "QR"  # simbología 2D elegida para los tipos de contenido QR
        self.forms: dict[str, Form] = {}
        self.current: Form | None = None
        self.current_data = ""
        self.current_image: Image.Image | None = None
        self._pending: str | None = None
        self._last_key: tuple | None = None
        self.setting_rows: list[tuple[str, list]] = []  # (grupo, widgets)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_sidebar()
        self._build_form_area()
        self._build_preview_area()
        self._build_statusbar()
        self._bind_shortcuts()
        self._select_type(ALL_TYPES[0])

    # ---------- Construcción de la interfaz ----------

    def _section(self, master, text: str, row: int, pady=(14, 8), padx=24) -> ctk.CTkLabel:
        label = ctk.CTkLabel(master, text=text, font=font("mono", 11, "bold"), text_color=theme.MUTED, anchor="w")
        label.grid(row=row, column=0, columnspan=3, sticky="w", padx=padx, pady=pady)
        return label

    def _build_header(self) -> None:
        bar = ctk.CTkFrame(self, height=52, fg_color=theme.SURFACE)
        bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_rowconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkFrame(bar, width=6, height=52, fg_color=theme.ACCENT).place(x=0, y=0, relheight=1)
        ctk.CTkLabel(bar, text="QR//GEN", font=font("display", 22, "bold")).grid(row=0, column=0, padx=(24, 14))
        ctk.CTkLabel(
            bar, text=f"GENERADOR DE CÓDIGOS QR Y DE BARRAS  ·  v{__version__}", font=font("mono", 11),
            text_color=theme.MUTED,
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(bar, text="MODO", font=font("mono", 11), text_color=theme.MUTED).grid(row=0, column=2, padx=8)
        self.mode_switch = ctk.CTkSegmentedButton(
            bar, values=["NORMAL", "AVANZADO"], command=self._set_mode, font=font("mono", 11, "bold"),
            height=28, width=190,
        )
        self.mode_switch.set("AVANZADO" if self.advanced else "NORMAL")
        self.mode_switch.grid(row=0, column=3, padx=(0, 20))

        ctk.CTkLabel(bar, text="TEMA", font=font("mono", 11), text_color=theme.MUTED).grid(row=0, column=4, padx=8)
        self.theme_switch = ctk.CTkSegmentedButton(
            bar, values=["CLARO", "OSCURO"], command=self._set_appearance, font=font("mono", 11, "bold"),
            height=28, width=160,
        )
        self.theme_switch.set("CLARO" if ctk.get_appearance_mode() == "Light" else "OSCURO")
        self.theme_switch.grid(row=0, column=5, padx=(0, 16))
        ctk.CTkFrame(bar, height=1, fg_color=theme.BORDER).place(relx=0, rely=1.0, relwidth=1, anchor="sw")

    def _build_sidebar(self) -> None:
        outer = ctk.CTkFrame(self, width=230, fg_color=theme.SURFACE)
        outer.grid(row=1, column=0, sticky="nsw")
        outer.grid_propagate(False)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=1)
        bar = ctk.CTkScrollableFrame(
            outer, fg_color="transparent", scrollbar_button_color=theme.SURFACE,
            scrollbar_button_hover_color=theme.BORDER,
        )
        bar.grid(row=0, column=0, sticky="nsew")
        bar.grid_columnconfigure(0, weight=1)

        self.type_buttons: dict[str, tuple[ctk.CTkFrame, ctk.CTkButton]] = {}
        row = 0
        for title, group in (("CÓDIGOS QR", QR_TYPES), ("CÓDIGOS DE BARRAS", BARCODE_TYPES)):
            ctk.CTkLabel(bar, text=title, font=font("mono", 11, "bold"), text_color=theme.MUTED).grid(
                row=row, column=0, padx=10, pady=(14 if row else 6, 6), sticky="w"
            )
            row += 1
            for qr_type in group:
                index = ALL_TYPES.index(qr_type) + 1
                btn = ctk.CTkButton(
                    bar,
                    text=f"  {index:02d}   {qr_type.name}",
                    anchor="w",
                    height=32,
                    font=font(size=13),
                    fg_color="transparent",
                    text_color=theme.TEXT,
                    hover_color=theme.SURFACE_2,
                    command=lambda t=qr_type: self._select_type(t),
                )
                btn.grid(row=row, column=0, sticky="ew")
                # Marcador de selección: barra de acento a la izquierda del botón.
                marker = ctk.CTkFrame(bar, width=3, height=32, fg_color=theme.ACCENT)
                marker.grid(row=row, column=0, sticky="nsw")
                marker.grid_remove()
                self.type_buttons[qr_type.code] = (marker, btn)
                row += 1

        ctk.CTkLabel(
            outer, text="CTRL+S    GUARDAR\nCTRL+⇧+C  COPIAR\nCTRL+T    TEMA\nCTRL+M    MODO", font=font("mono", 10),
            text_color=theme.MUTED, justify="left",
        ).grid(row=1, column=0, padx=20, pady=(8, 14), sticky="sw")
        ctk.CTkFrame(outer, width=1, fg_color=theme.BORDER).place(relx=1.0, rely=0, relheight=1, anchor="ne")

    def _build_form_area(self) -> None:
        area = ctk.CTkFrame(self, fg_color="transparent")
        area.grid(row=1, column=1, sticky="nsew", padx=28, pady=(20, 12))
        area.grid_columnconfigure(0, weight=1)
        area.grid_rowconfigure(3, weight=1)

        self.form_code = ctk.CTkLabel(area, text="", font=font("mono", 12, "bold"), text_color=theme.ACCENT)
        self.form_code.grid(row=0, column=0, sticky="w")
        self.form_title = ctk.CTkLabel(area, text="", font=font("display", 28, "bold"))
        self.form_title.grid(row=1, column=0, sticky="w", pady=(0, 4))

        self.hint = ctk.CTkFrame(area, fg_color=theme.WARN_BG, border_width=1, border_color=theme.ACCENT)
        self.hint.grid(row=2, column=0, sticky="ew", pady=(6, 4))
        self.hint.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.hint, text="NOTA", font=font("mono", 11, "bold"), text_color=theme.ACCENT).grid(
            row=0, column=0, padx=(12, 10), pady=10, sticky="nw"
        )
        self.hint_label = ctk.CTkLabel(self.hint, text="", justify="left", anchor="w", wraplength=440,
                                       font=font(size=12))
        self.hint_label.grid(row=0, column=1, padx=(0, 12), pady=10, sticky="w")

        self.form_host = ctk.CTkScrollableFrame(
            area, fg_color="transparent", scrollbar_button_color=theme.BG,
            scrollbar_button_hover_color=theme.BORDER,
        )
        self.form_host.grid(row=3, column=0, sticky="nsew")
        self.form_host.grid_columnconfigure(0, weight=1)

    def _build_preview_area(self) -> None:
        panel = ctk.CTkFrame(self, width=PREVIEW_SIZE + 76, fg_color=theme.SURFACE)
        panel.grid(row=1, column=2, sticky="nse")
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(5, weight=1)
        ctk.CTkFrame(panel, width=1, fg_color=theme.BORDER).place(relx=0, rely=0, relheight=1)
        span = {"column": 0, "sticky": "ew", "padx": 24}

        self._section(panel, "SALIDA", 0, pady=(16, 8))
        frame = ctk.CTkFrame(panel, fg_color=theme.BG, border_width=1, border_color=theme.BORDER_STRONG)
        frame.grid(row=1, **span)
        self.preview = ctk.CTkLabel(
            frame, text="SIN DATOS\ncompleta los campos", width=PREVIEW_SIZE, height=PREVIEW_SIZE,
            font=font("mono", 12), text_color=theme.MUTED,
        )
        self.preview.pack(padx=2, pady=2)
        self.readout = ctk.CTkLabel(panel, text="—", font=font("mono", 11), text_color=theme.MUTED, anchor="w")
        self.readout.grid(row=2, pady=(4, 0), **span)

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=3, pady=(8, 0), **span)
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions, text="GUARDAR", height=40, font=font("display", 14, "bold"),
                      command=self._save).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(actions, text="COPIAR", height=40, font=font("display", 14, "bold"), fg_color="transparent",
                      hover_color=theme.SURFACE_2, text_color=theme.TEXT, border_width=1,
                      border_color=theme.BORDER_STRONG, command=self._copy).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.grid(row=4, pady=(16, 0), **span)
        head.grid_columnconfigure(0, weight=1)
        self.settings_title = ctk.CTkLabel(head, text="AJUSTES", font=font("mono", 11, "bold"),
                                           text_color=theme.MUTED, anchor="w")
        self.settings_title.grid(row=0, column=0, sticky="w")
        self.reset_btn = ctk.CTkButton(head, text="RESTABLECER", width=90, height=22, font=font("mono", 10),
                                       fg_color="transparent", hover_color=theme.SURFACE_2, text_color=theme.MUTED,
                                       command=self._reset_style)
        self.reset_btn.grid(row=0, column=1, sticky="e")
        ctk.CTkFrame(head, height=1, fg_color=theme.BORDER).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        self.settings_box = ctk.CTkScrollableFrame(
            panel, fg_color="transparent", scrollbar_button_color=theme.SURFACE_2,
            scrollbar_button_hover_color=theme.BORDER,
        )
        self.settings_box.grid(row=5, column=0, sticky="nsew", padx=(14, 4), pady=(4, 12))
        self.settings_box.grid_columnconfigure(1, weight=1)
        self._build_settings(self.settings_box)

    # ---------- Panel de ajustes ----------

    def _setting(self, group: str, label: str, widget, extra=None) -> None:
        """Añade una fila «etiqueta | control [| extra]» al panel de ajustes.

        Grupos: basic (siempre), adv (avanzado), adv2d (avanzado y código 2D), advqr
        (avanzado y QR), adveye (avanzado y QR con ojos), advlin (avanzado y lineal).
        """
        row = len(self.setting_rows)
        lab = ctk.CTkLabel(self.settings_box, text=label, font=font("mono", 11), text_color=theme.MUTED,
                           anchor="w", width=72)
        lab.grid(row=row, column=0, sticky="w", padx=(6, 6), pady=4)
        widget.grid(row=row, column=1, columnspan=1 if extra else 2, sticky="ew", pady=4)
        parts = [lab, widget]
        if extra is not None:
            extra.grid(row=row, column=2, padx=(4, 4), pady=4)
            parts.append(extra)
        self.setting_rows.append((group, parts))

    def _menu(self, values: list[str], command, width: int = 120) -> ctk.CTkOptionMenu:
        return ctk.CTkOptionMenu(self.settings_box, values=values, command=command, height=28, width=width,
                                 font=font(size=12), dropdown_font=font(size=12))

    def _small_btn(self, text: str, command) -> ctk.CTkButton:
        return ctk.CTkButton(self.settings_box, text=text, width=28, height=28, fg_color=theme.SURFACE_2,
                             hover_color=theme.BORDER, text_color=theme.TEXT, command=command)

    def _color_btn(self, command) -> ctk.CTkButton:
        return ctk.CTkButton(self.settings_box, height=28, width=60, font=font("mono", 11, "bold"), border_width=1,
                             command=command)

    def _slider(self, frm: float, to: float, steps: int, command) -> ctk.CTkSlider:
        return ctk.CTkSlider(self.settings_box, from_=frm, to=to, number_of_steps=steps, command=command,
                             height=16, button_length=8, button_corner_radius=1, width=110)

    def _value_label(self) -> ctk.CTkLabel:
        return ctk.CTkLabel(self.settings_box, text="", font=font("mono", 11, "bold"), width=40, anchor="e")

    def _build_settings(self, box) -> None:
        # --- Básicos ---
        colors = ctk.CTkFrame(box, fg_color="transparent")
        colors.grid_columnconfigure((0, 2), weight=1)
        self.fill_btn = ctk.CTkButton(colors, height=28, width=60, font=font("mono", 11, "bold"), border_width=1,
                                      command=lambda: self._pick_color("fill_color"))
        self.fill_btn.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(colors, text="⇄", width=28, height=28, font=font(size=14), fg_color=theme.SURFACE_2,
                      hover_color=theme.BORDER, text_color=theme.TEXT, command=self._swap_colors).grid(
            row=0, column=1, padx=4
        )
        self.back_btn = ctk.CTkButton(colors, height=28, width=60, font=font("mono", 11, "bold"), border_width=1,
                                      command=lambda: self._pick_color("back_color"))
        self.back_btn.grid(row=0, column=2, sticky="ew")
        self._setting("basic", "COLOR", colors)

        logo = ctk.CTkFrame(box, fg_color="transparent")
        logo.grid_columnconfigure(0, weight=1)
        self.logo_btn = ctk.CTkButton(logo, text="SELECCIONAR…", height=28, width=60, font=font("mono", 11),
                                      fg_color=theme.SURFACE_2, hover_color=theme.BORDER, text_color=theme.TEXT,
                                      anchor="w", command=self._pick_logo)
        self.logo_btn.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(logo, text="✕", width=28, height=28, fg_color=theme.SURFACE_2, hover_color=theme.BORDER,
                      text_color=theme.TEXT, command=self._clear_logo).grid(row=0, column=1, padx=(4, 0))
        self._setting("basic2d", "LOGO", logo)

        # --- Avanzados: simbología y datos ---
        self.matrix_menu = self._menu([SYMBOLOGIES[c].name for c in MATRIX_CODES], self._set_matrix_symbology)
        self.matrix_menu.set(SYMBOLOGIES["QR"].name)
        self._setting("advcontent", "FORMATO", self.matrix_menu)

        self.level = ctk.CTkSegmentedButton(box, values=list(LEVEL_KEYS), command=self._set_level,
                                            font=font("mono", 12, "bold"), height=28)
        self.level.set(self.options.error_level[0])
        self._setting("advqr", "CORR.", self.level)

        self.version_menu = self._menu(["Auto"] + [str(v) for v in range(1, 41)],
                                       lambda v: self._set_opt("version", None if v == "Auto" else int(v)), 80)
        self.version_menu.set("Auto")
        self._setting("advqronly", "VERSIÓN", self.version_menu)
        self.mask_menu = self._menu(["Auto"] + [str(v) for v in range(8)],
                                    lambda v: self._set_opt("mask", None if v == "Auto" else int(v)), 80)
        self.mask_menu.set("Auto")
        self._setting("advqronly", "MÁSCARA", self.mask_menu)

        # --- Avanzados: forma ---
        names = {v: k for k, v in MODULE_SHAPES.items()}
        self.shape_menu = self._menu(list(MODULE_SHAPES.values()), lambda v: self._set_opt("module_shape", names[v]))
        self._setting("adv2d", "MÓDULOS", self.shape_menu)
        self.scale_label = self._value_label()
        self.scale_slider = self._slider(50, 100, 10, self._set_scale)
        self.scale_slider.set(100)
        self._setting("adv2d", "ESCALA", self.scale_slider, self.scale_label)

        eyes = {v: k for k, v in EYE_SHAPES.items()}
        self.eye_menu = self._menu(list(EYE_SHAPES.values()), lambda v: self._set_opt("eye_shape", eyes[v]))
        self._setting("adveye", "OJOS", self.eye_menu)
        self.eye_btn = self._color_btn(lambda: self._pick_color("eye_color", allow_none=True))
        self._setting("adveye", "OJO EXT.", self.eye_btn, self._small_btn("✕", lambda: self._clear_color("eye_color")))
        self.eye_inner_btn = self._color_btn(lambda: self._pick_color("eye_inner_color", allow_none=True))
        self._setting("adveye", "OJO INT.", self.eye_inner_btn,
                      self._small_btn("✕", lambda: self._clear_color("eye_inner_color")))

        # --- Avanzados: color ---
        grads = {v: k for k, v in GRADIENTS.items()}
        self.gradient_menu = self._menu(list(GRADIENTS.values()), lambda v: self._set_opt("gradient", grads[v]))
        self._setting("adv", "DEGRADADO", self.gradient_menu)
        self.gradient_btn = self._color_btn(lambda: self._pick_color("gradient_color"))
        self._setting("adv", "COLOR 2", self.gradient_btn)
        self.transparent_var = ctk.BooleanVar(value=False)
        self._setting("adv", "FONDO", ctk.CTkCheckBox(
            box, text="Transparente (PNG/SVG)", variable=self.transparent_var, font=font(size=12),
            checkbox_width=16, checkbox_height=16,
            command=lambda: self._set_opt("transparent", self.transparent_var.get()),
        ))

        # --- Avanzados: tamaño ---
        self.size_label = self._value_label()
        self.size_slider = self._slider(2, 30, 28, self._set_size)
        self.size_slider.set(self.options.box_size)
        self._setting("adv", "MÓDULO", self.size_slider, self.size_label)
        self.border_label = self._value_label()
        self.border_slider = self._slider(0, 10, 10, self._set_border)
        self.border_slider.set(self.options.border)
        self._setting("adv", "BORDE", self.border_slider, self.border_label)

        # --- Avanzados: logo ---
        self.logo_size_label = self._value_label()
        self.logo_size_slider = self._slider(10, 35, 25, self._set_logo_ratio)
        self.logo_size_slider.set(22)
        self._setting("adv2d", "LOGO %", self.logo_size_slider, self.logo_size_label)
        self.logo_pad_var = ctk.BooleanVar(value=True)
        self._setting("adv2d", "LOGO FONDO", ctk.CTkCheckBox(
            box, text="Recuadro detrás del logo", variable=self.logo_pad_var, font=font(size=12),
            checkbox_width=16, checkbox_height=16,
            command=lambda: self._set_opt("logo_pad", self.logo_pad_var.get()),
        ))

        # --- Avanzados: texto ---
        self.caption_entry = ctk.CTkEntry(box, placeholder_text="p. ej. ESCANÉAME", height=28, font=font(size=12))
        self.caption_entry.bind("<KeyRelease>", lambda _e: self._set_opt("caption", self.caption_entry.get(), now=False))
        self._setting("adv", "TEXTO", self.caption_entry)
        self.caption_size_label = self._value_label()
        self.caption_size_slider = self._slider(0, 60, 60, self._set_caption_size)
        self.caption_size_slider.set(0)
        self._setting("adv", "TAM. TEXTO", self.caption_size_slider, self.caption_size_label)
        self.caption_color_btn = self._color_btn(lambda: self._pick_color("caption_color", allow_none=True))
        self._setting("adv", "COLOR TXT", self.caption_color_btn,
                      self._small_btn("✕", lambda: self._clear_color("caption_color")))

        # --- Avanzados: códigos de barras ---
        self.bar_label = self._value_label()
        self.bar_slider = self._slider(10, 120, 22, self._set_bar_height)
        self.bar_slider.set(self.options.bar_height)
        self._setting("advlin", "ALTURA", self.bar_slider, self.bar_label)
        self.show_text_var = ctk.BooleanVar(value=True)
        self._setting("advlin", "LEGIBLE", ctk.CTkCheckBox(
            box, text="Mostrar los dígitos", variable=self.show_text_var, font=font(size=12),
            checkbox_width=16, checkbox_height=16,
            command=lambda: self._set_opt("show_text", self.show_text_var.get()),
        ))
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        """Actualiza textos de botones/valores y muestra solo las filas que aplican."""
        o = self.options
        for btn, color in ((self.fill_btn, o.fill_color), (self.back_btn, o.back_color),
                           (self.gradient_btn, o.gradient_color)):
            btn.configure(text=color.upper(), fg_color=color, hover_color=color, text_color=_contrast_text(color),
                          border_color=theme.BORDER_STRONG)
        for btn, color in ((self.eye_btn, o.eye_color), (self.eye_inner_btn, o.eye_inner_color),
                           (self.caption_color_btn, o.caption_color)):
            if color:
                btn.configure(text=color.upper(), fg_color=color, hover_color=color, text_color=_contrast_text(color))
            else:
                btn.configure(text="IGUAL AL CÓDIGO", fg_color=theme.SURFACE_2, hover_color=theme.BORDER,
                              text_color=theme.TEXT)
        self.scale_label.configure(text=f"{round(o.module_scale * 100)}%")
        self.size_label.configure(text=f"{o.box_size}PX")
        self.border_label.configure(text=str(o.border))
        self.logo_size_label.configure(text=f"{round(o.logo_ratio * 100)}%")
        self.caption_size_label.configure(text="AUTO" if not o.caption_size else str(o.caption_size))
        self.bar_label.configure(text=str(o.bar_height))
        self.level.configure(state="disabled" if o.logo_path else "normal")
        self.level.set("H" if o.logo_path else o.error_level[0])

        qr_type = self.current.qr_type if self.current else ALL_TYPES[0]
        symbology = self._symbology()
        linear = SYMBOLOGIES[symbology].linear
        visible = {
            "basic": True,
            "basic2d": not linear,
            "adv": self.advanced,
            "advcontent": self.advanced and qr_type.symbology is None,
            "advqr": self.advanced and symbology in ("QR", "MICROQR"),
            "advqronly": self.advanced and symbology == "QR",
            "adveye": self.advanced and symbology in ("QR", "MICROQR"),
            "adv2d": self.advanced and not linear,
            "advlin": self.advanced and linear,
        }
        for group, parts in self.setting_rows:
            for widget in parts:
                widget.grid() if visible[group] else widget.grid_remove()
        self.settings_title.configure(text="AJUSTES AVANZADOS" if self.advanced else "AJUSTES")
        self.reset_btn.grid() if self.advanced else self.reset_btn.grid_remove()

    def _build_statusbar(self) -> None:
        bar = ctk.CTkFrame(self, height=30, fg_color=theme.SURFACE_2)
        bar.grid(row=2, column=0, columnspan=3, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)
        self.status_dot = ctk.CTkFrame(bar, width=8, height=8, fg_color=theme.MUTED)
        self.status_dot.grid(row=0, column=0, padx=(16, 10), pady=11)
        self.status = ctk.CTkLabel(bar, text="", anchor="w", font=font("mono", 11), text_color=theme.TEXT)
        self.status.grid(row=0, column=1, sticky="ew", pady=3)
        ctk.CTkLabel(bar, text="© Lucas Espinola", font=font("mono", 10), text_color=theme.MUTED).grid(
            row=0, column=2, padx=16
        )

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-s>", lambda _e: self._save())
        self.bind("<Control-C>", lambda _e: self._copy())  # Ctrl+Shift+C
        self.bind("<Control-t>", lambda _e: self._toggle_appearance())
        self.bind("<Control-m>", lambda _e: self._toggle_mode())

    # ---------- Tema y modo ----------

    def _set_appearance(self, value: str) -> None:
        mode = "light" if value == "CLARO" else "dark"
        ctk.set_appearance_mode(mode)
        _store_settings(appearance=mode)

    def _toggle_appearance(self) -> None:
        value = "OSCURO" if self.theme_switch.get() == "CLARO" else "CLARO"
        self.theme_switch.set(value)
        self._set_appearance(value)

    def _set_mode(self, value: str) -> None:
        self.advanced = value == "AVANZADO"
        _store_settings(advanced=self.advanced)
        for form in self.forms.values():
            form.set_advanced(self.advanced)
        self._refresh_controls()
        self._last_key = None
        self._regenerate()

    def _toggle_mode(self) -> None:
        value = "NORMAL" if self.advanced else "AVANZADO"
        self.mode_switch.set(value)
        self._set_mode(value)

    # ---------- Formularios ----------

    def _select_type(self, qr_type: QRType) -> None:
        for code, (marker, btn) in self.type_buttons.items():
            active = code == qr_type.code
            marker.grid() if active else marker.grid_remove()
            btn.configure(
                fg_color=theme.SURFACE_2 if active else "transparent",
                font=font(size=13, weight="bold" if active else "normal"),
            )
        index = ALL_TYPES.index(qr_type) + 1
        group = "BARRAS" if qr_type.linear else "QR"
        self.form_code.configure(text=f"{index:02d} / {group} / {qr_type.code}")
        self.form_title.configure(text=qr_type.name)
        self.hint_label.configure(text=qr_type.hint)
        self.hint.grid() if qr_type.hint else self.hint.grid_remove()

        if self.current:
            self.current.frame.grid_remove()
        form = self.forms.get(qr_type.code)
        if form is None:
            form = self.forms[qr_type.code] = Form(self.form_host, qr_type, self._schedule)
            form.frame.grid(row=0, column=0, sticky="ew")
            form.set_advanced(self.advanced)
        else:
            form.frame.grid()
        self.current = form
        form.focus_first()
        self._refresh_controls()

        # Los valores se conservan entre tipos: si ya hay datos válidos, se muestran.
        self._last_key = None
        if not self._generate(quiet=True):
            self._show_empty()
            self._set_status("Completa los campos; la vista previa se actualiza sola.")

    # ---------- Generación ----------

    def _symbology(self) -> str:
        qr_type = self.current.qr_type if self.current else ALL_TYPES[0]
        if qr_type.symbology:
            return qr_type.symbology
        return self.matrix_symbology if self.advanced else "QR"

    def _effective_options(self) -> QROptions:
        """En modo normal se ignoran los ajustes avanzados (se conservan para volver a ellos)."""
        o = self.options
        if not self.advanced:
            basic = {f.name: getattr(o, f.name) for f in fields(QROptions)
                     if f.name in ("fill_color", "back_color", "logo_path")}
            o = replace(DEFAULTS, **basic)
        return replace(o, symbology=self._symbology())

    def _schedule(self, *_args) -> None:
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(DEBOUNCE_MS, self._generate)

    def _generate(self, quiet: bool = False) -> bool:
        self._pending = None
        assert self.current
        opts = self._effective_options()
        try:
            data = self.current.qr_type.build(**self.current.values(self.advanced))
            key = (data, repr(opts))
            if key == self._last_key and self.current_image is not None:
                return True  # nada cambió: no se vuelve a dibujar
            image = make_image(data, opts)
            sym = get_symbol(data, opts)
        except ValueError as exc:
            if not quiet:
                self._set_status(str(exc), level="error")
            self.current_data = ""
            return False
        except OSError as exc:
            self._set_status(f"No se pudo abrir el logo: {exc}", level="error")
            self.current_data = ""
            return False

        self._last_key = key
        self.current_data = data
        self.current_image = image
        self._show_preview(image)

        name = SYMBOLOGIES[opts.symbology].name.upper()
        size = f"{len(data.encode('utf-8'))} B"
        if sym.linear:
            text = f"{name} · {sym.width} MÓD · {sym.text}"
        elif sym.version:
            level = "H" if opts.logo_path else opts.error_level[0]
            text = f"V{sym.version:02d} · {sym.width}×{sym.height} MÓD · CORR {level} · {size}"
        else:
            text = f"{name} · {sym.width}×{sym.height} MÓD · {size}"
        self.readout.configure(text=text)
        self._set_status(f"Código listo · {image.size[0]}×{image.size[1]} px", level="ok")
        return True

    def _show_preview(self, image: Image.Image) -> None:
        w, h = image.size
        ratio = min(PREVIEW_SIZE / w, PREVIEW_SIZE / h)
        size = (max(1, round(w * ratio)), max(1, round(h * ratio)))
        if image.mode == "RGBA":
            # Fondo a cuadros para que se note la transparencia.
            checker = Image.new("RGB", image.size, "#cfcfcf")
            tile = max(4, w // 24)
            for y in range(0, h, tile):
                for x in range((y // tile) % 2 * tile, w, tile * 2):
                    checker.paste("#f4f4f4", (x, y, x + tile, y + tile))
            checker.paste(image, (0, 0), image)
            image = checker
        resample = Image.NEAREST if ratio >= 1 else Image.LANCZOS
        src = image.resize(size, resample)
        preview = ctk.CTkImage(light_image=src, dark_image=src, size=size)
        self.preview.configure(image=preview, text="")
        self.preview._qr_ref = preview  # evita que el recolector borre la imagen

    def _show_empty(self) -> None:
        self.current_data = ""
        self.current_image = None
        self.preview.configure(image=None, text="SIN DATOS\ncompleta los campos")
        self.readout.configure(text="—")

    def _ensure_generated(self) -> bool:
        if self._pending:
            self.after_cancel(self._pending)
        if not self._generate():
            messagebox.showwarning(APP_NAME, self.status.cget("text"))
            return False
        return True

    def _set_status(self, text: str, level: str = "info") -> None:
        color = {"error": theme.ERROR, "ok": theme.OK}.get(level, theme.MUTED)
        self.status_dot.configure(fg_color=color)
        self.status.configure(text=text, text_color=theme.ERROR if level == "error" else theme.TEXT)

    # ---------- Opciones ----------

    def _set_opt(self, attr: str, value, now: bool = True) -> None:
        setattr(self.options, attr, value)
        self._refresh_controls()
        self._regenerate() if now else self._schedule()

    def _regenerate(self) -> None:
        if self.current:
            self._last_key = None
            if not self._generate(quiet=not self.current_data):
                if not self.current_data:
                    self._show_empty()

    def _pick_color(self, attr: str, allow_none: bool = False) -> None:
        current = getattr(self.options, attr) or self.options.fill_color
        color = colorchooser.askcolor(color=current, title="Elige un color")[1]
        if color:
            self._set_opt(attr, color)

    def _clear_color(self, attr: str) -> None:
        self._set_opt(attr, None)

    def _swap_colors(self) -> None:
        o = self.options
        o.fill_color, o.back_color = o.back_color, o.fill_color
        self._refresh_controls()
        self._regenerate()

    def _set_matrix_symbology(self, name: str) -> None:
        self.matrix_symbology = next(c for c in MATRIX_CODES if SYMBOLOGIES[c].name == name)
        self._refresh_controls()
        self._regenerate()

    def _set_level(self, value: str) -> None:
        self._set_opt("error_level", LEVEL_KEYS[value])

    def _slider_opt(self, attr: str, value) -> None:
        if getattr(self.options, attr) != value:
            setattr(self.options, attr, value)
            self._refresh_controls()
            self._schedule()

    def _set_size(self, value: float) -> None:
        self._slider_opt("box_size", int(round(value)))

    def _set_border(self, value: float) -> None:
        self._slider_opt("border", int(round(value)))

    def _set_scale(self, value: float) -> None:
        self._slider_opt("module_scale", round(value) / 100)

    def _set_logo_ratio(self, value: float) -> None:
        self._slider_opt("logo_ratio", round(value) / 100)

    def _set_caption_size(self, value: float) -> None:
        self._slider_opt("caption_size", int(round(value)))

    def _set_bar_height(self, value: float) -> None:
        self._slider_opt("bar_height", int(round(value)))

    def _reset_style(self) -> None:
        keep = {"fill_color": self.options.fill_color, "back_color": self.options.back_color,
                "logo_path": self.options.logo_path}
        self.options = replace(DEFAULTS, **keep)
        self.matrix_symbology = "QR"
        self.matrix_menu.set(SYMBOLOGIES["QR"].name)
        for menu in (self.version_menu, self.mask_menu):
            menu.set("Auto")
        self.shape_menu.set(MODULE_SHAPES["square"])
        self.eye_menu.set(EYE_SHAPES["square"])
        self.gradient_menu.set(GRADIENTS["none"])
        for slider, value in ((self.scale_slider, 100), (self.size_slider, DEFAULTS.box_size),
                              (self.border_slider, DEFAULTS.border), (self.logo_size_slider, 22),
                              (self.caption_size_slider, 0), (self.bar_slider, DEFAULTS.bar_height)):
            slider.set(value)
        for var, value in ((self.transparent_var, False), (self.logo_pad_var, True), (self.show_text_var, True)):
            var.set(value)
        self.caption_entry.delete(0, "end")
        self._refresh_controls()
        self._regenerate()

    def _pick_logo(self) -> None:
        path = filedialog.askopenfilename(
            title="Elige un logo",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("Todos", "*.*")],
        )
        if path:
            self.logo_btn.configure(text=Path(path).name.upper())
            self._set_opt("logo_path", path)
            self._set_status("Con logo se fuerza la corrección H (30%) para que el código siga leyéndose.")

    def _clear_logo(self) -> None:
        self.logo_btn.configure(text="SELECCIONAR…")
        self._set_opt("logo_path", None)

    # ---------- Acciones ----------

    def _save(self) -> None:
        if not self._ensure_generated():
            return
        name = self.current.qr_type.code.lower() if self.current else "codigo"
        path = filedialog.asksaveasfilename(
            title="Guardar código",
            defaultextension=".png",
            initialfile=f"codigo-{name}.png",
            filetypes=[("PNG", "*.png"), ("SVG (vectorial)", "*.svg"), ("JPEG", "*.jpg"), ("BMP", "*.bmp")],
        )
        if not path:
            return
        try:
            save(self.current_data, path, self._effective_options())
        except (ValueError, OSError) as exc:
            messagebox.showerror(APP_NAME, f"No se pudo guardar: {exc}")
            return
        self._set_status(f"Guardado en {path}", level="ok")

    def _copy(self) -> None:
        if not self._ensure_generated():
            return
        try:
            clipboard.copy_image(self.current_image)
            self._set_status("Imagen copiada al portapapeles.", level="ok")
        except RuntimeError:
            self.clipboard_clear()
            self.clipboard_append(self.current_data)
            self._set_status("Se copió el contenido como texto.", level="ok")


def run() -> None:
    App().mainloop()
