"""Interfaz gráfica del generador de QRs (CustomTkinter, estilo industrial)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox
from typing import Callable

import customtkinter as ctk
from PIL import Image

from . import __version__, clipboard, payloads, theme
from .generator import ERROR_LEVELS, QROptions, get_matrix, make_image, save
from .theme import font

APP_NAME = "Generador de QRs"
PREVIEW_SIZE = 264
DEBOUNCE_MS = 150
SETTINGS_PATH = Path.home() / ".generador-qrs.json"
LEVEL_KEYS = {key[0]: key for key in ERROR_LEVELS}  # "L" -> "L (7%)"


@dataclass
class Field:
    key: str
    label: str
    kind: str = "entry"  # entry | text | combo | check
    placeholder: str = ""
    options: list[str] = field(default_factory=list)
    show: str = ""


@dataclass
class QRType:
    code: str
    name: str
    build: Callable[..., str]
    fields: list[Field]
    hint: str = ""


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
            Field("hidden", "Red oculta", kind="check"),
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
            Field("company", "Empresa"),
            Field("title", "Cargo"),
            Field("website", "Sitio web"),
            Field("address", "Dirección"),
        ],
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
    QRType(
        "GEO",
        "Ubicación",
        payloads.geo,
        [
            Field("latitude", "Latitud", placeholder="40.4168"),
            Field("longitude", "Longitud", placeholder="-3.7038"),
        ],
    ),
    QRType(
        "CAL",
        "Evento",
        payloads.event,
        [
            Field("title", "Título"),
            Field("start", "Inicio", placeholder="2026-12-31 20:00"),
            Field("end", "Fin", placeholder="2026-12-31 23:59"),
            Field("location", "Lugar"),
            Field("description", "Descripción", kind="text"),
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
            Field("label", "Etiqueta (opcional)"),
        ],
    ),
]


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
    """Formulario de un tipo de QR. Se crea una vez y se conserva al cambiar de tipo."""

    def __init__(self, master, qr_type: QRType, on_change: Callable[..., None]) -> None:
        self.qr_type = qr_type
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self.frame.grid_columnconfigure(0, weight=1)
        self.widgets: dict[str, object] = {}

        row = 0
        for f in qr_type.fields:
            if f.kind == "check":
                var = ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(
                    self.frame, text=f.label, variable=var, command=on_change, font=font(size=13),
                    checkbox_width=18, checkbox_height=18,
                ).grid(row=row, column=0, sticky="w", pady=(14, 0))
                self.widgets[f.key] = var
                row += 1
                continue

            ctk.CTkLabel(
                self.frame, text=f.label.upper(), font=font("mono", 11), text_color=theme.MUTED, anchor="w"
            ).grid(row=row, column=0, sticky="w", pady=(14, 4))
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
            row += 1

    def values(self) -> dict:
        values = {}
        for key, widget in self.widgets.items():
            if isinstance(widget, ctk.BooleanVar):
                values[key] = widget.get()
            elif isinstance(widget, ctk.CTkTextbox):
                values[key] = widget.get("1.0", "end-1c")
            else:
                values[key] = widget.get()
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
        self.geometry("1180x720")
        self.minsize(1020, 640)
        if sys.platform == "win32" and resource("icon.ico").exists():
            self.iconbitmap(str(resource("icon.ico")))

        self.options = QROptions()
        self.forms: dict[str, Form] = {}
        self.current: Form | None = None
        self.current_data = ""
        self.current_image: Image.Image | None = None
        self._pending: str | None = None
        self._last_key: tuple | None = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_sidebar()
        self._build_form_area()
        self._build_preview_area()
        self._build_statusbar()
        self._bind_shortcuts()
        self._select_type(QR_TYPES[0])

    # ---------- Construcción de la interfaz ----------

    def _section(self, master, text: str, row: int, pady=(14, 8)) -> ctk.CTkLabel:
        label = ctk.CTkLabel(master, text=text, font=font("mono", 11, "bold"), text_color=theme.MUTED, anchor="w")
        label.grid(row=row, column=0, columnspan=3, sticky="w", padx=24, pady=pady)
        return label

    def _spec_label(self, master, text: str, row: int) -> ctk.CTkLabel:
        """Etiqueta de la columna izquierda de una fila «ficha técnica»."""
        label = ctk.CTkLabel(master, text=text, font=font("mono", 11), text_color=theme.MUTED, anchor="w", width=64)
        label.grid(row=row, column=0, sticky="w", padx=(24, 8), pady=5)
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
            bar, text=f"GENERADOR DE CÓDIGOS QR  ·  v{__version__}", font=font("mono", 11), text_color=theme.MUTED
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(bar, text="TEMA", font=font("mono", 11), text_color=theme.MUTED).grid(row=0, column=2, padx=8)
        self.theme_switch = ctk.CTkSegmentedButton(
            bar, values=["CLARO", "OSCURO"], command=self._set_appearance, font=font("mono", 11, "bold"),
            height=28, width=160,
        )
        self.theme_switch.set("CLARO" if ctk.get_appearance_mode() == "Light" else "OSCURO")
        self.theme_switch.grid(row=0, column=3, padx=(0, 16))
        ctk.CTkFrame(bar, height=1, fg_color=theme.BORDER).place(relx=0, rely=1.0, relwidth=1, anchor="sw")

    def _build_sidebar(self) -> None:
        bar = ctk.CTkFrame(self, width=220, fg_color=theme.SURFACE)
        bar.grid(row=1, column=0, sticky="nsw")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(bar, text="TIPO DE CÓDIGO", font=font("mono", 11, "bold"), text_color=theme.MUTED).grid(
            row=0, column=0, padx=20, pady=(18, 8), sticky="w"
        )

        self.type_buttons: dict[str, tuple[ctk.CTkFrame, ctk.CTkButton]] = {}
        for i, qr_type in enumerate(QR_TYPES, start=1):
            btn = ctk.CTkButton(
                bar,
                text=f"  {i:02d}   {qr_type.name}",
                anchor="w",
                height=34,
                font=font(size=13),
                fg_color="transparent",
                text_color=theme.TEXT,
                hover_color=theme.SURFACE_2,
                command=lambda t=qr_type: self._select_type(t),
            )
            btn.grid(row=i, column=0, sticky="ew", padx=10)
            # Marcador de selección: barra de acento a la izquierda del botón.
            marker = ctk.CTkFrame(bar, width=3, height=34, fg_color=theme.ACCENT)
            marker.grid(row=i, column=0, sticky="nsw", padx=(10, 0))
            marker.grid_remove()
            self.type_buttons[qr_type.code] = (marker, btn)

        bar.grid_rowconfigure(len(QR_TYPES) + 1, weight=1)
        ctk.CTkLabel(
            bar, text="CTRL+S    GUARDAR\nCTRL+⇧+C  COPIAR\nCTRL+T    TEMA", font=font("mono", 10),
            text_color=theme.MUTED, justify="left",
        ).grid(row=len(QR_TYPES) + 2, column=0, padx=20, pady=(0, 16), sticky="sw")
        ctk.CTkFrame(bar, width=1, fg_color=theme.BORDER).place(relx=1.0, rely=0, relheight=1, anchor="ne")

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
        self.hint_label = ctk.CTkLabel(self.hint, text="", justify="left", anchor="w", wraplength=460,
                                       font=font(size=12))
        self.hint_label.grid(row=0, column=1, padx=(0, 12), pady=10, sticky="w")

        self.form_host = ctk.CTkScrollableFrame(
            area, fg_color="transparent", scrollbar_button_color=theme.BG,
            scrollbar_button_hover_color=theme.BORDER,
        )
        self.form_host.grid(row=3, column=0, sticky="nsew")
        self.form_host.grid_columnconfigure(0, weight=1)

    def _build_preview_area(self) -> None:
        panel = ctk.CTkFrame(self, width=PREVIEW_SIZE + 52, fg_color=theme.SURFACE)
        panel.grid(row=1, column=2, sticky="nse")
        panel.grid_propagate(False)
        panel.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(panel, width=1, fg_color=theme.BORDER).place(relx=0, rely=0, relheight=1)
        span = {"column": 0, "columnspan": 3, "sticky": "ew", "padx": 24}

        self._section(panel, "SALIDA", 0, pady=(18, 8))
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

        self._section(panel, "AJUSTES", 4, pady=(20, 4))
        ctk.CTkFrame(panel, height=1, fg_color=theme.BORDER).grid(row=5, pady=(0, 6), **span)

        self._spec_label(panel, "COLOR", 6)
        colors = ctk.CTkFrame(panel, fg_color="transparent")
        colors.grid(row=6, column=1, columnspan=2, sticky="ew", padx=(0, 24), pady=5)
        colors.grid_columnconfigure((0, 2), weight=1)
        self.fill_btn = ctk.CTkButton(colors, height=30, width=60, font=font("mono", 11, "bold"), border_width=1,
                                      command=lambda: self._pick_color("fill_color"))
        self.fill_btn.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(colors, text="⇄", width=30, height=30, font=font(size=14), fg_color=theme.SURFACE_2,
                      hover_color=theme.BORDER, text_color=theme.TEXT, command=self._swap_colors).grid(
            row=0, column=1, padx=4
        )
        self.back_btn = ctk.CTkButton(colors, height=30, width=60, font=font("mono", 11, "bold"), border_width=1,
                                      command=lambda: self._pick_color("back_color"))
        self.back_btn.grid(row=0, column=2, sticky="ew")
        self._refresh_color_buttons()

        self._spec_label(panel, "CORR.", 7)
        self.level = ctk.CTkSegmentedButton(panel, values=list(LEVEL_KEYS), command=self._set_level,
                                            font=font("mono", 12, "bold"), height=30)
        self.level.set(self.options.error_level[0])
        self.level.grid(row=7, column=1, columnspan=2, sticky="ew", padx=(0, 24), pady=5)

        self._spec_label(panel, "MÓDULO", 8)
        self.size_slider = ctk.CTkSlider(panel, from_=4, to=30, number_of_steps=26, command=self._set_size,
                                         height=18, button_length=8, button_corner_radius=1, width=120)
        self.size_slider.set(self.options.box_size)
        self.size_slider.grid(row=8, column=1, sticky="ew", pady=5)
        self.size_label = ctk.CTkLabel(panel, text="", font=font("mono", 11, "bold"), width=44, anchor="e")
        self.size_label.grid(row=8, column=2, sticky="e", padx=(6, 24))
        self._update_size_label()

        self._spec_label(panel, "LOGO", 9)
        logo = ctk.CTkFrame(panel, fg_color="transparent")
        logo.grid(row=9, column=1, columnspan=2, sticky="ew", padx=(0, 24), pady=5)
        logo.grid_columnconfigure(0, weight=1)
        self.logo_btn = ctk.CTkButton(logo, text="SELECCIONAR…", height=30, width=60, font=font("mono", 11),
                                      fg_color=theme.SURFACE_2, hover_color=theme.BORDER, text_color=theme.TEXT,
                                      anchor="w", command=self._pick_logo)
        self.logo_btn.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(logo, text="✕", width=30, height=30, fg_color=theme.SURFACE_2, hover_color=theme.BORDER,
                      text_color=theme.TEXT, command=self._clear_logo).grid(row=0, column=1, padx=(4, 0))

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

    # ---------- Tema ----------

    def _set_appearance(self, value: str) -> None:
        mode = "light" if value == "CLARO" else "dark"
        ctk.set_appearance_mode(mode)
        _store_settings(appearance=mode)

    def _toggle_appearance(self) -> None:
        value = "OSCURO" if self.theme_switch.get() == "CLARO" else "CLARO"
        self.theme_switch.set(value)
        self._set_appearance(value)

    # ---------- Formularios ----------

    def _select_type(self, qr_type: QRType) -> None:
        for code, (marker, btn) in self.type_buttons.items():
            active = code == qr_type.code
            marker.grid() if active else marker.grid_remove()
            btn.configure(
                fg_color=theme.SURFACE_2 if active else "transparent",
                font=font(size=13, weight="bold" if active else "normal"),
            )
        index = QR_TYPES.index(qr_type) + 1
        self.form_code.configure(text=f"{index:02d} / {qr_type.code}")
        self.form_title.configure(text=qr_type.name)
        self.hint_label.configure(text=qr_type.hint)
        self.hint.grid() if qr_type.hint else self.hint.grid_remove()

        if self.current:
            self.current.frame.grid_remove()
        form = self.forms.get(qr_type.code)
        if form is None:
            form = self.forms[qr_type.code] = Form(self.form_host, qr_type, self._schedule)
            form.frame.grid(row=0, column=0, sticky="ew")
        else:
            form.frame.grid()
        self.current = form
        form.focus_first()

        # Los valores se conservan entre tipos: si ya hay datos válidos, se muestran.
        self._last_key = None
        if not self._generate(quiet=True):
            self._show_empty()
            self._set_status("Completa los campos; la vista previa se actualiza sola.")

    # ---------- Generación ----------

    def _schedule(self, *_args) -> None:
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(DEBOUNCE_MS, self._generate)

    def _options_key(self) -> tuple:
        o = self.options
        return (o.fill_color, o.back_color, o.box_size, o.border, o.error_level, o.logo_path)

    def _generate(self, quiet: bool = False) -> bool:
        self._pending = None
        assert self.current
        try:
            data = self.current.qr_type.build(**self.current.values())
            key = (data, self._options_key())
            if key == self._last_key and self.current_image is not None:
                return True  # nada cambió: no se vuelve a dibujar
            image = make_image(data, self.options)
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
        preview_src = image.resize((PREVIEW_SIZE, PREVIEW_SIZE), Image.NEAREST)
        preview = ctk.CTkImage(light_image=preview_src, dark_image=preview_src, size=(PREVIEW_SIZE, PREVIEW_SIZE))
        self.preview.configure(image=preview, text="")
        self.preview._qr_ref = preview  # evita que el recolector borre la imagen

        modules = len(get_matrix(data, self.options)) - 2 * self.options.border
        version = (modules - 17) // 4
        level = "H" if self.options.logo_path else self.options.error_level[0]
        self.readout.configure(
            text=f"V{version:02d} · {modules}×{modules} MÓD · CORR {level} · {len(data.encode('utf-8'))} B"
        )
        self._set_status(f"QR listo · {image.size[0]}×{image.size[1]} px", level="ok")
        return True

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

    def _pick_color(self, attr: str) -> None:
        color = colorchooser.askcolor(color=getattr(self.options, attr), title="Elige un color")[1]
        if color:
            setattr(self.options, attr, color)
            self._refresh_color_buttons()
            self._regenerate_if_ready()

    def _swap_colors(self) -> None:
        o = self.options
        o.fill_color, o.back_color = o.back_color, o.fill_color
        self._refresh_color_buttons()
        self._regenerate_if_ready()

    def _refresh_color_buttons(self) -> None:
        for btn, color in ((self.fill_btn, self.options.fill_color), (self.back_btn, self.options.back_color)):
            btn.configure(text=color.upper(), fg_color=color, hover_color=color,
                          text_color=_contrast_text(color), border_color=theme.BORDER_STRONG)

    def _set_level(self, value: str) -> None:
        self.options.error_level = LEVEL_KEYS[value]
        self._regenerate_if_ready()

    def _set_size(self, value: float) -> None:
        size = int(round(value))
        if size == self.options.box_size:
            return
        self.options.box_size = size
        self._update_size_label()
        self._schedule()

    def _update_size_label(self) -> None:
        self.size_label.configure(text=f"{self.options.box_size}PX")

    def _pick_logo(self) -> None:
        path = filedialog.askopenfilename(
            title="Elige un logo",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("Todos", "*.*")],
        )
        if path:
            self.options.logo_path = path
            self.logo_btn.configure(text=Path(path).name.upper())
            self.level.set("H")
            self.level.configure(state="disabled")
            self._set_status("Con logo se fuerza la corrección H (30%) para que el QR siga leyéndose.")
            self._regenerate_if_ready()

    def _clear_logo(self) -> None:
        self.options.logo_path = None
        self.logo_btn.configure(text="SELECCIONAR…")
        self.level.configure(state="normal")
        self.level.set(self.options.error_level[0])
        self._regenerate_if_ready()

    def _regenerate_if_ready(self) -> None:
        if self.current_data:
            self._generate()

    # ---------- Acciones ----------

    def _save(self) -> None:
        if not self._ensure_generated():
            return
        path = filedialog.asksaveasfilename(
            title="Guardar QR",
            defaultextension=".png",
            initialfile=f"qr-{self.current.qr_type.code.lower()}.png" if self.current else "codigo-qr.png",
            filetypes=[("PNG", "*.png"), ("SVG (vectorial)", "*.svg"), ("JPEG", "*.jpg"), ("BMP", "*.bmp")],
        )
        if not path:
            return
        try:
            save(self.current_data, path, self.options)
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
            self._set_status("Se copió el contenido del QR como texto.", level="ok")


def run() -> None:
    App().mainloop()
