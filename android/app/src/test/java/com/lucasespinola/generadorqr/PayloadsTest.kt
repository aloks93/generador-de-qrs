package com.lucasespinola.generadorqr

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Mismos casos que tests/test_payloads.py: ambas apps deben generar idéntico contenido. */
class PayloadsTest {

    private inline fun fails(block: () -> Unit) {
        try {
            block()
        } catch (e: Payloads.InvalidInput) {
            return
        }
        throw AssertionError("Se esperaba InvalidInput")
    }

    @Test fun url() {
        assertEquals("https://ejemplo.com", Payloads.url("ejemplo.com"))
        assertEquals("http://a.b", Payloads.url("http://a.b"))
        fails { Payloads.url("   ") }
    }

    @Test fun wifi() {
        assertEquals("WIFI:T:WPA;S:Mi\\;Red;P:p\\:a\\,ss;;", Payloads.wifi("Mi;Red", "p:a,ss", "WPA", false))
        assertEquals("WIFI:T:nopass;S:Libre;;", Payloads.wifi("Libre", "ignorada", "Ninguna", false))
        assertTrue(Payloads.wifi("X", "123", "WEP", true).endsWith("H:true;;"))
        fails { Payloads.wifi("X", "", "WPA", false) }
    }

    @Test fun vcard() {
        val card = Payloads.vcard("Ana", "López", "+34 600-11-22", "ana@x.com", "", "", "", "")
        assertTrue(card.startsWith("BEGIN:VCARD\nVERSION:3.0"))
        assertTrue("N:López;Ana;;;" in card)
        assertTrue("FN:Ana López" in card)
        assertTrue("TEL;TYPE=CELL:+346001122" in card)
        assertTrue(card.endsWith("END:VCARD"))
    }

    @Test fun email() {
        assertEquals(
            "mailto:a@b.com?subject=Hola%20mundo&body=%C2%BFQu%C3%A9%20tal%3F",
            Payloads.email("a@b.com", "Hola mundo", "¿Qué tal?"),
        )
        assertEquals("mailto:a@b.com", Payloads.email("a@b.com", "", ""))
    }

    @Test fun phoneSmsWhatsapp() {
        assertEquals("tel:+34600000000", Payloads.phone("+34 600 000 000"))
        assertEquals("SMSTO:600111:hola", Payloads.sms("600 111", "hola"))
        assertEquals("https://wa.me/34600?text=hola%20que%20tal", Payloads.whatsapp("+34 600", "hola que tal"))
    }

    @Test fun geo() {
        assertEquals("geo:40.4168,-3.7038", Payloads.geo("40,4168", "-3.7038"))
        assertEquals("geo:40.0,3.0", Payloads.geo("40", "3"))
        fails { Payloads.geo("100", "0") }
        fails { Payloads.geo("abc", "0") }
    }

    @Test fun event() {
        val ev = Payloads.event("Fiesta", "2026-12-31 20:00", "2026-12-31 23:59", "Casa", "")
        assertTrue("DTSTART:20261231T200000" in ev)
        assertTrue("DTEND:20261231T235900" in ev)
        assertTrue("LOCATION:Casa" in ev)
        fails { Payloads.event("X", "2026-12-31 20:00", "2026-12-30 20:00", "", "") }
        fails { Payloads.event("X", "31/12/2026", "2026-12-31 20:00", "", "") }
    }

    @Test fun crypto() {
        assertEquals("bitcoin:bc1abc?amount=0.5&label=Caf%C3%A9", Payloads.crypto("bc1abc", "0,5", "bitcoin", "Café"))
        assertEquals("ethereum:0xabc", Payloads.crypto("0xabc", "", "ethereum", ""))
    }

    @Test fun newContentTypes() {
        assertEquals("https://instagram.com/lucas.e", Payloads.social("Instagram", "@lucas.e"))
        assertEquals("https://tiktok.com/@lucas", Payloads.social("TikTok", "lucas"))
        assertEquals("https://t.me/canal_x", Payloads.telegram("@canal_x"))
        assertEquals(
            "https://www.google.com/maps/search/?api=1&query=Plaza%20Mayor%2C%20Madrid",
            Payloads.maps("Plaza Mayor, Madrid"),
        )
        assertEquals("https://paypal.me/lucas/12.5USD", Payloads.paypal("lucas", "12,5", "usd"))
        assertEquals("https://paypal.me/lucas", Payloads.paypal("lucas", "", "EUR"))
        assertEquals(
            "MECARD:N:Ana\\; López;TEL:+34600;EMAIL:a@b.com;;",
            Payloads.mecard("Ana; López", "+34 600", "a@b.com", ""),
        )
        fails { Payloads.social("MySpace", "x") }
    }

    @Test fun encodeAndOverflow() {
        val m = QrEngine.encode("https://ejemplo.com", Symbology.QR, QrStyle())
        assertEquals(17 + 4 * m.version!!, m.width)
        assertEquals(37, QrEngine.encode("hola", Symbology.QR, QrStyle(version = 5, mask = 3)).width)
        fails { QrEngine.encode("x".repeat(5000), Symbology.QR, QrStyle()) }
        fails { QrEngine.encode("abc", Symbology.EAN13, QrStyle()) }
    }

    /** Cada simbología se decodifica con el lector de ZXing a partir de la matriz generada. */
    @Test fun everySymbologyDecodes() {
        for (sym in Symbology.values()) {
            val data = sym.example.ifEmpty { "https://ejemplo.com/123" }
            val code = QrEngine.encode(data, sym, QrStyle())
            val scale = 4
            val quiet = 10
            val rows = if (code.linear) 40 else code.height
            val w = (code.width + 2 * quiet) * scale
            val h = (rows + 2 * quiet) * scale
            val pixels = IntArray(w * h) { i ->
                val x = (i % w) / scale - quiet
                val y = (i / w) / scale - quiet
                val inside = x in 0 until code.width && y in 0 until rows
                val on = inside && code[x, if (code.linear) 0 else y]
                if (on) 0xFF000000.toInt() else 0xFFFFFFFF.toInt()
            }
            val source = com.google.zxing.RGBLuminanceSource(w, h, pixels)
            val bitmap = com.google.zxing.BinaryBitmap(com.google.zxing.common.HybridBinarizer(source))
            val hints = mapOf(
                com.google.zxing.DecodeHintType.POSSIBLE_FORMATS to listOf(sym.format),
                com.google.zxing.DecodeHintType.TRY_HARDER to true,
            )
            val result = com.google.zxing.MultiFormatReader().decode(bitmap, hints)
            if (sym == Symbology.UPCE) continue // se lee expandido; basta con que decodifique
            assertTrue("${sym.name}: ${result.text} vs ${code.text}", result.text == code.text || code.text.contains(result.text))
        }
    }
}
