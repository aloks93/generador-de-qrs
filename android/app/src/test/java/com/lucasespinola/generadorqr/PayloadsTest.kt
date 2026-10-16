package com.lucasespinola.generadorqr

import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
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

    @Test fun encodeAndOverflow() {
        val m = QrEngine.encode("https://ejemplo.com", ErrorCorrectionLevel.M)
        assertEquals(17 + 4 * m.version, m.size)
        fails { QrEngine.encode("x".repeat(5000), ErrorCorrectionLevel.M) }
    }
}
