"""Interfaz gráfica del generador de QRs (CustomTkinter)."""

from __future__ import annotations

from dataclasses import dataclass, field
from tkinter import colorchooser, filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from . import clipboard, payloads
from .generator import ERROR_LEVELS, QROptions, make_image, save

PREVIEW_SIZE = 320


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
    name: str
    build: Callable[..., str]
    fields: list[Field]
    hint: str = ""


QR_TYPES: list[QRType] = [
    QRType("🔗 Enlace / URL", payloads.url, [Field("link", "URL", placeholder="https://ejemplo.com")]),
    QRType(
        "📄 PDF / Archivo",
        payloads.file_link,
        [Field("link", "Enlace al archivo", placeholder="https://drive.google.com/...")],
        hint=(
            "Un QR solo puede guardar unos 3 KB, así que el archivo no cabe dentro.\n"
            "Sube tu PDF, imagen o video a Google Drive, Dropbox, OneDrive, etc., "
            "compártelo como «cualquiera con el enlace» y pega aquí el link."
        ),
    ),
    QRType("📝 Texto", payloads.text, [Field("content", "Texto", kind="text")]),
    QRType(
        "📶 WiFi",
        payloads.wifi,
        [
            Field("ssid", "Nombre de red (SSID)"),
            Field("password", "Contraseña", show="•"),
            Field("security", "Seguridad", kind="combo", options=["WPA", "WEP", "Ninguna"]),
            Field("hidden", "Red oculta", kind="check"),
        ],
    ),
    QRType(
        "👤 Contacto (vCard)",
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
        "✉️ Email",
        payloads.email,
        [
            Field("to", "Destinatario", placeholder="nombre@correo.com"),
            Field("subject", "Asunto"),
            Field("body", "Mensaje", kind="text"),
        ],
    ),
    QRType("📞 Teléfono", payloads.phone, [Field("number", "Teléfono", placeholder="+34 600 000 000")]),
    QRType(
        "💬 SMS",
        payloads.sms,
        [Field("number", "Teléfono"), Field("message", "Mensaje", kind="text")],
    ),
    QRType(
        "🟢 WhatsApp",
        payloads.whatsapp,
        [
            Field("number", "Teléfono (con código de país)", placeholder="+34 600 000 000"),
            Field("message", "Mensaje", kind="text"),
        ],
    ),
    QRType(
        "📍 Ubicación",
        payloads.geo,
        [
            Field("latitude", "Latitud", placeholder="40.4168"),
            Field("longitude", "Longitud", placeholder="-3.7038"),
        ],
    ),
    QRType(
        "📅 Evento",
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
        "₿ Cripto",
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


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        self.title("Generador de QRs")
        self.geometry("1150x680")
        self.minsize(980, 600)

        self.options = QROptions()
        self.current_type: QRType = QR_TYPES[0]
        self.widgets: dict[str, object] = {}
        self.current_data = ""
        self.current_image = None
        self._pending = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_form_area()
        self._build_preview_area()
        self._select_type(QR_TYPES[0])

    # ---------- Construcción de la interfaz ----------

    def _build_sidebar(self) -> None:
        bar = ctk.CTkScrollableFrame(self, width=200, corner_radius=0)
        bar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(bar, text="Tipo de QR", font=ctk.CTkFont(size=18, weight="bold")).pack(
            padx=12, pady=(16, 10), anchor="w"
        )
        self.type_buttons: dict[str, ctk.CTkButton] = {}
        for qr_type in QR_TYPES:
            btn = ctk.CTkButton(
                bar,
                text=qr_type.name,
                anchor="w",
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray75", "gray30"),
                command=lambda t=qr_type: self._select_type(t),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self.type_buttons[qr_type.name] = btn

        ctk.CTkLabel(bar, text="Tema").pack(padx=12, pady=(20, 4), anchor="w")
        theme = ctk.CTkOptionMenu(
            bar,
            values=["Sistema", "Claro", "Oscuro"],
            command=lambda v: ctk.set_appearance_mode(
                {"Sistema": "system", "Claro": "light", "Oscuro": "dark"}[v]
            ),
        )
        theme.pack(fill="x", padx=8)

    def _build_form_area(self) -> None:
        area = ctk.CTkFrame(self, fg_color="transparent")
        area.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        area.grid_columnconfigure(0, weight=1)
        area.grid_rowconfigure(2, weight=1)

        self.form_title = ctk.CTkLabel(area, text="", font=ctk.CTkFont(size=22, weight="bold"))
        self.form_title.grid(row=0, column=0, sticky="w")
        self.hint_label = ctk.CTkLabel(
            area, text="", justify="left", wraplength=480, text_color=("#8a5a00", "#f0c060")
        )
        self.hint_label.grid(row=1, column=0, sticky="w", pady=(4, 8))

        self.form = ctk.CTkScrollableFrame(area)
        self.form.grid(row=2, column=0, sticky="nsew")
        self.form.grid_columnconfigure(0, weight=1)

        self.status = ctk.CTkLabel(area, text="", anchor="w", justify="left", wraplength=480)
        self.status.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    def _build_preview_area(self) -> None:
        panel = ctk.CTkFrame(self)
        panel.grid(row=0, column=2, sticky="nsew", padx=(0, 16), pady=16)

        self.preview = ctk.CTkLabel(panel, text="La vista previa\naparecerá aquí", width=PREVIEW_SIZE,
                                    height=PREVIEW_SIZE, fg_color=("gray85", "gray20"), corner_radius=8)
        self.preview.pack(padx=16, pady=(16, 10))

        colors = ctk.CTkFrame(panel, fg_color="transparent")
        colors.pack(fill="x", padx=16, pady=4)
        colors.grid_columnconfigure((0, 1), weight=1)
        self.fill_btn = ctk.CTkButton(colors, text="Color QR", command=lambda: self._pick_color("fill_color"))
        self.fill_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.back_btn = ctk.CTkButton(colors, text="Color fondo", command=lambda: self._pick_color("back_color"))
        self.back_btn.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._refresh_color_buttons()

        opts = ctk.CTkFrame(panel, fg_color="transparent")
        opts.pack(fill="x", padx=16, pady=4)
        opts.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(opts, text="Corrección").grid(row=0, column=0, sticky="w", pady=4)
        self.level_menu = ctk.CTkOptionMenu(opts, values=list(ERROR_LEVELS), command=self._set_level)
        self.level_menu.set(self.options.error_level)
        self.level_menu.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ctk.CTkLabel(opts, text="Tamaño").grid(row=1, column=0, sticky="w", pady=4)
        self.size_label = ctk.CTkLabel(opts, text="")
        self.size_slider = ctk.CTkSlider(opts, from_=4, to=30, number_of_steps=26, command=self._set_size)
        self.size_slider.set(self.options.box_size)
        self.size_slider.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        self.size_label.grid(row=2, column=1, sticky="e")
        self._update_size_label()

        logo = ctk.CTkFrame(panel, fg_color="transparent")
        logo.pack(fill="x", padx=16, pady=4)
        logo.grid_columnconfigure(0, weight=1)
        self.logo_btn = ctk.CTkButton(logo, text="Añadir logo…", command=self._pick_logo)
        self.logo_btn.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(logo, text="✕", width=36, command=self._clear_logo).grid(row=0, column=1, padx=(6, 0))

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(12, 16))
        actions.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(actions, text="💾 Guardar", height=38, command=self._save).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ctk.CTkButton(actions, text="📋 Copiar", height=38, command=self._copy).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

    # ---------- Formularios ----------

    def _select_type(self, qr_type: QRType) -> None:
        self.current_type = qr_type
        for name, btn in self.type_buttons.items():
            btn.configure(fg_color=("gray75", "gray30") if name == qr_type.name else "transparent")
        self.form_title.configure(text=qr_type.name)
        self.hint_label.configure(text=qr_type.hint)
        self.hint_label.grid() if qr_type.hint else self.hint_label.grid_remove()

        for child in self.form.winfo_children():
            child.destroy()
        self.widgets.clear()

        row = 0
        for f in qr_type.fields:
            if f.kind == "check":
                var = ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(self.form, text=f.label, variable=var, command=self._schedule).grid(
                    row=row, column=0, sticky="w", padx=12, pady=8
                )
                self.widgets[f.key] = var
                row += 1
                continue

            ctk.CTkLabel(self.form, text=f.label).grid(row=row, column=0, sticky="w", padx=12, pady=(10, 2))
            row += 1
            if f.kind == "text":
                widget = ctk.CTkTextbox(self.form, height=110)
                widget.bind("<KeyRelease>", self._schedule)
            elif f.kind == "combo":
                widget = ctk.CTkOptionMenu(self.form, values=f.options, command=self._schedule)
                widget.set(f.options[0])
            else:
                widget = ctk.CTkEntry(self.form, placeholder_text=f.placeholder, show=f.show)
                widget.bind("<KeyRelease>", self._schedule)
            widget.grid(row=row, column=0, sticky="ew", padx=12)
            self.widgets[f.key] = widget
            row += 1

        self.current_data = ""
        self.current_image = None
        self.preview.configure(image=None, text="La vista previa\naparecerá aquí")
        self._set_status("Completa los campos; la vista previa se actualiza sola.")

    def _values(self) -> dict:
        values = {}
        for key, widget in self.widgets.items():
            if isinstance(widget, ctk.BooleanVar):
                values[key] = widget.get()
            elif isinstance(widget, ctk.CTkTextbox):
                values[key] = widget.get("1.0", "end-1c")
            else:
                values[key] = widget.get()
        return values

    # ---------- Generación ----------

    def _schedule(self, *_args) -> None:
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(300, self._generate)

    def _generate(self) -> bool:
        self._pending = None
        try:
            data = self.current_type.build(**self._values())
            image = make_image(data, self.options)
        except ValueError as exc:
            self._set_status(f"⚠️ {exc}", error=True)
            return False
        except OSError as exc:
            self._set_status(f"⚠️ No se pudo abrir el logo: {exc}", error=True)
            return False

        self.current_data = data
        self.current_image = image
        preview = ctk.CTkImage(light_image=image, dark_image=image, size=(PREVIEW_SIZE, PREVIEW_SIZE))
        self.preview.configure(image=preview, text="")
        self.preview._qr_ref = preview  # evita que el recolector borre la imagen
        self._set_status(f"✅ QR listo · {len(data.encode('utf-8'))} bytes · {image.size[0]}×{image.size[1]} px")
        return True

    def _ensure_generated(self) -> bool:
        if self._pending:
            self.after_cancel(self._pending)
        if not self._generate():
            messagebox.showwarning("Generador de QRs", self.status.cget("text").lstrip("⚠️ "))
            return False
        return True

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status.configure(text=text, text_color=("#b00020", "#ff6b6b") if error else ("gray20", "gray80"))

    # ---------- Opciones ----------

    def _pick_color(self, attr: str) -> None:
        color = colorchooser.askcolor(color=getattr(self.options, attr), title="Elige un color")[1]
        if color:
            setattr(self.options, attr, color)
            self._refresh_color_buttons()
            self._regenerate_if_ready()

    def _refresh_color_buttons(self) -> None:
        for btn, color in ((self.fill_btn, self.options.fill_color), (self.back_btn, self.options.back_color)):
            r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
            text = "black" if (r * 299 + g * 587 + b * 114) / 1000 > 140 else "white"
            btn.configure(fg_color=color, hover_color=color, text_color=text, border_width=1,
                          border_color=("gray60", "gray40"))

    def _set_level(self, value: str) -> None:
        self.options.error_level = value
        self._regenerate_if_ready()

    def _set_size(self, value: float) -> None:
        self.options.box_size = int(value)
        self._update_size_label()
        self._regenerate_if_ready()

    def _update_size_label(self) -> None:
        self.size_label.configure(text=f"{self.options.box_size} px por módulo")

    def _pick_logo(self) -> None:
        path = filedialog.askopenfilename(
            title="Elige un logo",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("Todos", "*.*")],
        )
        if path:
            self.options.logo_path = path
            self.logo_btn.configure(text="Logo: " + path.replace("\\", "/").split("/")[-1])
            self._set_status("Con logo se usa corrección H (30%) para que el QR siga leyéndose.")
            self._regenerate_if_ready()

    def _clear_logo(self) -> None:
        self.options.logo_path = None
        self.logo_btn.configure(text="Añadir logo…")
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
            initialfile="codigo-qr.png",
            filetypes=[("PNG", "*.png"), ("SVG (vectorial)", "*.svg"), ("JPEG", "*.jpg"), ("BMP", "*.bmp")],
        )
        if not path:
            return
        if path.lower().endswith(".svg") and self.options.logo_path:
            messagebox.showinfo("Generador de QRs", "El formato SVG no incluye el logo. Usa PNG si lo necesitas.")
        try:
            save(self.current_data, path, self.options)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Generador de QRs", f"No se pudo guardar: {exc}")
            return
        self._set_status(f"💾 Guardado en {path}")

    def _copy(self) -> None:
        if not self._ensure_generated():
            return
        try:
            clipboard.copy_image(self.current_image)
            self._set_status("📋 Imagen copiada al portapapeles.")
        except RuntimeError:
            self.clipboard_clear()
            self.clipboard_append(self.current_data)
            self._set_status("📋 Se copió el contenido del QR como texto.")


def run() -> None:
    App().mainloop()
