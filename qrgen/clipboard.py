"""Copiar imágenes al portapapeles (solo Windows, sin dependencias extra)."""

from __future__ import annotations

import io
import sys

from PIL import Image


def copy_image(img: Image.Image) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Copiar imágenes al portapapeles solo está disponible en Windows.")

    import ctypes
    from ctypes import wintypes

    buffer = io.BytesIO()
    if img.mode == "RGBA":  # el portapapeles no admite transparencia: se aplana sobre blanco
        flat = Image.new("RGB", img.size, "white")
        flat.paste(img, (0, 0), img)
        img = flat
    img.convert("RGB").save(buffer, "BMP")
    data = buffer.getvalue()[14:]  # CF_DIB no lleva la cabecera de archivo BMP

    CF_DIB = 8
    GMEM_MOVEABLE = 0x0002
    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise RuntimeError("No se pudo reservar memoria para el portapapeles.")
    ptr = kernel32.GlobalLock(handle)
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(handle)

    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(handle)
        raise RuntimeError("No se pudo abrir el portapapeles.")
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_DIB, handle):
            kernel32.GlobalFree(handle)
            raise RuntimeError("No se pudo copiar la imagen.")
    finally:
        user32.CloseClipboard()
