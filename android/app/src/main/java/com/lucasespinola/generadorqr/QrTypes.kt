package com.lucasespinola.generadorqr

enum class Kind { ENTRY, TEXT, CHOICE, CHECK }

data class FieldSpec(
    val key: String,
    val label: String,
    val kind: Kind = Kind.ENTRY,
    val placeholder: String = "",
    val options: List<String> = emptyList(),
    val password: Boolean = false,
    val numeric: Boolean = false,
    val advanced: Boolean = false, // solo visible en modo avanzado
)

class QrTypeSpec(
    val code: String,
    val name: String,
    val fields: List<FieldSpec>,
    val hint: String = "",
    val symbology: Symbology? = null, // fija en los códigos de barras; null = QR / 2D elegible
    val build: (Map<String, String>) -> String,
) {
    val linear get() = symbology?.linear == true
}

private fun Map<String, String>.v(key: String) = this[key].orEmpty()

val QR_TYPES = listOf(
    QrTypeSpec("URL", "Enlace / URL", listOf(FieldSpec("link", "URL", placeholder = "https://ejemplo.com"))) {
        Payloads.url(it.v("link"))
    },
    QrTypeSpec(
        "FILE", "PDF / Archivo",
        listOf(FieldSpec("link", "Enlace al archivo", placeholder = "https://drive.google.com/...")),
        hint = "Un QR solo guarda unos 3 KB: el archivo no cabe dentro. Súbelo a Google Drive, Dropbox u " +
            "OneDrive, compártelo como «cualquiera con el enlace» y pega aquí el link.",
    ) { Payloads.url(it.v("link")) },
    QrTypeSpec("TXT", "Texto", listOf(FieldSpec("content", "Texto", Kind.TEXT))) { Payloads.text(it.v("content")) },
    QrTypeSpec(
        "WIFI", "Red WiFi",
        listOf(
            FieldSpec("ssid", "Nombre de red (SSID)"),
            FieldSpec("password", "Contraseña", password = true),
            FieldSpec("security", "Seguridad", Kind.CHOICE, options = listOf("WPA", "WEP", "Ninguna")),
            FieldSpec("hidden", "Red oculta", Kind.CHECK, advanced = true),
        ),
    ) { Payloads.wifi(it.v("ssid"), it.v("password"), it["security"] ?: "WPA", it.v("hidden") == "true") },
    QrTypeSpec(
        "VCF", "Contacto (vCard)",
        listOf(
            FieldSpec("first_name", "Nombre"), FieldSpec("last_name", "Apellidos"),
            FieldSpec("phone", "Teléfono", placeholder = "+34 600 000 000"), FieldSpec("email", "Email"),
            FieldSpec("company", "Empresa", advanced = true), FieldSpec("title", "Cargo", advanced = true),
            FieldSpec("website", "Sitio web", advanced = true), FieldSpec("address", "Dirección", advanced = true),
        ),
    ) {
        Payloads.vcard(
            it.v("first_name"), it.v("last_name"), it.v("phone"), it.v("email"),
            it.v("company"), it.v("title"), it.v("website"), it.v("address"),
        )
    },
    QrTypeSpec(
        "MECARD", "Contacto (MeCard)",
        listOf(
            FieldSpec("name", "Nombre completo"), FieldSpec("phone", "Teléfono"), FieldSpec("email", "Email"),
            FieldSpec("note", "Nota", advanced = true),
        ),
        hint = "Formato más corto que vCard: genera un QR más pequeño y fácil de leer.",
    ) { Payloads.mecard(it.v("name"), it.v("phone"), it.v("email"), it.v("note")) },
    QrTypeSpec(
        "MAIL", "Email",
        listOf(
            FieldSpec("to", "Destinatario", placeholder = "nombre@correo.com"),
            FieldSpec("subject", "Asunto"), FieldSpec("body", "Mensaje", Kind.TEXT),
        ),
    ) { Payloads.email(it.v("to"), it.v("subject"), it.v("body")) },
    QrTypeSpec("TEL", "Teléfono", listOf(FieldSpec("number", "Teléfono", placeholder = "+34 600 000 000"))) {
        Payloads.phone(it.v("number"))
    },
    QrTypeSpec("SMS", "SMS", listOf(FieldSpec("number", "Teléfono"), FieldSpec("message", "Mensaje", Kind.TEXT))) {
        Payloads.sms(it.v("number"), it.v("message"))
    },
    QrTypeSpec(
        "WA", "WhatsApp",
        listOf(
            FieldSpec("number", "Teléfono (con código de país)", placeholder = "+34 600 000 000"),
            FieldSpec("message", "Mensaje", Kind.TEXT),
        ),
    ) { Payloads.whatsapp(it.v("number"), it.v("message")) },
    QrTypeSpec("TG", "Telegram", listOf(FieldSpec("user", "Usuario o canal", placeholder = "@usuario"))) {
        Payloads.telegram(it.v("user"))
    },
    QrTypeSpec(
        "SOC", "Redes sociales",
        listOf(
            FieldSpec("network", "Red", Kind.CHOICE, options = Payloads.SOCIAL_NETWORKS.keys.toList()),
            FieldSpec("user", "Usuario", placeholder = "@usuario"),
        ),
    ) { Payloads.social(it["network"] ?: Payloads.SOCIAL_NETWORKS.keys.first(), it.v("user")) },
    QrTypeSpec(
        "GEO", "Ubicación (GPS)",
        listOf(
            FieldSpec("latitude", "Latitud", placeholder = "40.4168", numeric = true),
            FieldSpec("longitude", "Longitud", placeholder = "-3.7038", numeric = true),
        ),
    ) { Payloads.geo(it.v("latitude"), it.v("longitude")) },
    QrTypeSpec("MAPS", "Google Maps", listOf(FieldSpec("query", "Dirección o lugar", placeholder = "Plaza Mayor, Madrid"))) {
        Payloads.maps(it.v("query"))
    },
    QrTypeSpec(
        "CAL", "Evento",
        listOf(
            FieldSpec("title", "Título"),
            FieldSpec("start", "Inicio", placeholder = "2026-12-31 20:00"),
            FieldSpec("end", "Fin", placeholder = "2026-12-31 23:59"),
            FieldSpec("location", "Lugar"), FieldSpec("description", "Descripción", Kind.TEXT, advanced = true),
        ),
    ) { Payloads.event(it.v("title"), it.v("start"), it.v("end"), it.v("location"), it.v("description")) },
    QrTypeSpec(
        "PAY", "PayPal",
        listOf(
            FieldSpec("user", "Usuario de PayPal.me"),
            FieldSpec("amount", "Cantidad (opcional)", numeric = true),
            FieldSpec("currency", "Moneda", Kind.CHOICE, options = listOf("EUR", "USD", "ARS", "MXN", "GBP"), advanced = true),
        ),
    ) { Payloads.paypal(it.v("user"), it.v("amount"), it["currency"] ?: "EUR") },
    QrTypeSpec(
        "BTC", "Cripto",
        listOf(
            FieldSpec(
                "currency", "Moneda", Kind.CHOICE,
                options = listOf("bitcoin", "ethereum", "litecoin", "dogecoin", "bitcoincash"),
            ),
            FieldSpec("address", "Dirección de la billetera"),
            FieldSpec("amount", "Cantidad (opcional)", numeric = true),
            FieldSpec("label", "Etiqueta (opcional)", advanced = true),
        ),
    ) { Payloads.crypto(it.v("address"), it.v("amount"), it["currency"] ?: "bitcoin", it.v("label")) },
)

val BARCODE_TYPES = Symbology.values().filter { it.linear }.map { sym ->
    QrTypeSpec(
        sym.name, sym.label,
        listOf(FieldSpec("content", "Contenido", placeholder = sym.example)),
        hint = sym.hint, symbology = sym,
    ) { it.v("content").trim() }
}

val ALL_TYPES = QR_TYPES + BARCODE_TYPES
