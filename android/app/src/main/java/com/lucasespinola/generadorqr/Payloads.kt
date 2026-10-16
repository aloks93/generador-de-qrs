package com.lucasespinola.generadorqr

import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Locale

/**
 * Construcción del contenido de cada tipo de QR. Es una traducción directa de
 * `qrgen/payloads.py`: ambas versiones deben producir exactamente el mismo texto.
 */
object Payloads {

    class InvalidInput(message: String) : IllegalArgumentException(message)

    private fun required(value: String?, field: String): String {
        val v = value.orEmpty().trim()
        if (v.isEmpty()) throw InvalidInput("El campo «$field» es obligatorio.")
        return v
    }

    private fun digits(phone: String): String {
        val p = phone.trim()
        val plus = if (p.startsWith("+")) "+" else ""
        return plus + p.filter { it.isDigit() }
    }

    /** Equivale a `urllib.parse.quote(value, safe)` de Python. */
    private fun quote(value: String, safe: String = ""): String {
        var out = URLEncoder.encode(value, "UTF-8").replace("+", "%20").replace("*", "%2A").replace("%7E", "~")
        for (ch in safe) out = out.replace(URLEncoder.encode(ch.toString(), "UTF-8"), ch.toString())
        return out
    }

    private fun query(params: List<Pair<String, String>>): String =
        params.filter { it.second.isNotEmpty() }.joinToString("&") { "${it.first}=${quote(it.second)}" }

    fun url(link: String): String {
        var l = required(link, "URL")
        if ("://" !in l && !l.lowercase().startsWith("mailto:") && !l.lowercase().startsWith("tel:")) {
            l = "https://$l"
        }
        return l
    }

    fun text(content: String): String {
        if (content.isBlank()) throw InvalidInput("El campo «Texto» es obligatorio.")
        return content
    }

    private fun wifiEscape(value: String): String {
        var v = value
        for (ch in listOf("\\", ";", ",", ":", "\"")) v = v.replace(ch, "\\" + ch)
        return v
    }

    fun wifi(ssid: String, password: String, security: String, hidden: Boolean): String {
        val s = required(ssid, "Nombre de red (SSID)")
        var sec = security.uppercase()
        var pass = password
        if (sec in setOf("NINGUNA", "NOPASS", "NONE", "")) {
            sec = "nopass"
            pass = ""
        } else if (pass.isEmpty()) {
            throw InvalidInput("La contraseña es obligatoria para redes protegidas.")
        }
        val parts = mutableListOf("T:$sec", "S:${wifiEscape(s)}")
        if (pass.isNotEmpty()) parts += "P:${wifiEscape(pass)}"
        if (hidden) parts += "H:true"
        return "WIFI:" + parts.joinToString(";") + ";;"
    }

    private fun vEscape(v: String) =
        v.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    fun vcard(
        firstName: String, lastName: String, phone: String, email: String,
        company: String, title: String, website: String, address: String,
    ): String {
        val first = required(firstName, "Nombre")
        val last = lastName.trim()
        val lines = mutableListOf(
            "BEGIN:VCARD",
            "VERSION:3.0",
            "N:${vEscape(last)};${vEscape(first)};;;",
            "FN:${vEscape("$first $last".trim())}",
        )
        if (company.isNotBlank()) lines += "ORG:${vEscape(company.trim())}"
        if (title.isNotBlank()) lines += "TITLE:${vEscape(title.trim())}"
        if (phone.isNotBlank()) lines += "TEL;TYPE=CELL:${digits(phone)}"
        if (email.isNotBlank()) lines += "EMAIL:${email.trim()}"
        if (website.isNotBlank()) lines += "URL:${website.trim()}"
        if (address.isNotBlank()) lines += "ADR:;;${vEscape(address.trim())};;;;"
        lines += "END:VCARD"
        return lines.joinToString("\n")
    }

    fun email(to: String, subject: String, body: String): String {
        val t = required(to, "Destinatario")
        val q = query(listOf("subject" to subject, "body" to body))
        return "mailto:$t" + if (q.isNotEmpty()) "?$q" else ""
    }

    fun phone(number: String) = "tel:" + digits(required(number, "Teléfono"))

    fun sms(number: String, message: String) = "SMSTO:${digits(required(number, "Teléfono"))}:$message"

    fun whatsapp(number: String, message: String): String {
        val d = digits(required(number, "Teléfono")).trimStart('+')
        return "https://wa.me/$d" + if (message.isNotEmpty()) "?text=${quote(message, safe = "/")}" else ""
    }

    private fun plain(v: Double): String {
        // Como el float de Python ("40.0", "-3.7038"), sin notación científica.
        val s = v.toString()
        return if (s.contains('E')) java.math.BigDecimal.valueOf(v).toPlainString() else s
    }

    fun geo(latitude: String, longitude: String): String {
        val latS = required(latitude, "Latitud").replace(",", ".")
        val lonS = required(longitude, "Longitud").replace(",", ".")
        val lat = latS.toDoubleOrNull()
        val lon = lonS.toDoubleOrNull()
        if (lat == null || lon == null) throw InvalidInput("Latitud y longitud deben ser números.")
        if (lat !in -90.0..90.0 || lon !in -180.0..180.0) throw InvalidInput("Coordenadas fuera de rango.")
        return "geo:${plain(lat)},${plain(lon)}"
    }

    private fun icalDate(value: String, field: String): String {
        val v = required(value, field)
        val parser = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.ROOT).apply { isLenient = false }
        val date = runCatching { parser.parse(v) }.getOrNull()
            ?: throw InvalidInput("«$field» debe tener el formato AAAA-MM-DD HH:MM.")
        return SimpleDateFormat("yyyyMMdd'T'HHmmss", Locale.ROOT).format(date)
    }

    fun event(title: String, start: String, end: String, location: String, description: String): String {
        val t = required(title, "Título")
        val s = icalDate(start, "Inicio")
        val e = icalDate(end, "Fin")
        if (e < s) throw InvalidInput("La fecha de fin no puede ser anterior al inicio.")
        val lines = mutableListOf("BEGIN:VEVENT", "SUMMARY:$t", "DTSTART:$s", "DTEND:$e")
        if (location.isNotBlank()) lines += "LOCATION:${location.trim()}"
        if (description.isNotBlank()) lines += "DESCRIPTION:${description.trim()}"
        lines += "END:VEVENT"
        return lines.joinToString("\n")
    }

    fun crypto(address: String, amount: String, currency: String, label: String): String {
        val a = required(address, "Dirección")
        val params = mutableListOf<Pair<String, String>>()
        if (amount.isNotBlank()) {
            val normalized = amount.trim().replace(",", ".")
            normalized.toDoubleOrNull() ?: throw InvalidInput("La cantidad debe ser un número.")
            params += "amount" to normalized
        }
        if (label.isNotBlank()) params += "label" to label.trim()
        val q = query(params)
        return "${currency.lowercase()}:$a" + if (q.isNotEmpty()) "?$q" else ""
    }

    val SOCIAL_NETWORKS = linkedMapOf(
        "Instagram" to "https://instagram.com/%s",
        "Facebook" to "https://facebook.com/%s",
        "TikTok" to "https://tiktok.com/@%s",
        "X / Twitter" to "https://x.com/%s",
        "YouTube" to "https://youtube.com/@%s",
        "LinkedIn" to "https://linkedin.com/in/%s",
        "GitHub" to "https://github.com/%s",
        "Twitch" to "https://twitch.tv/%s",
    )

    private fun handle(user: String, field: String): String =
        quote(required(user, field).trimStart('@').trim('/'), safe = "._-")

    fun social(network: String, user: String): String {
        val template = SOCIAL_NETWORKS[network] ?: throw InvalidInput("Red social no soportada.")
        return template.format(handle(user, "Usuario"))
    }

    fun telegram(user: String) = "https://t.me/${handle(user, "Usuario")}"

    fun maps(query: String) =
        "https://www.google.com/maps/search/?api=1&query=" + quote(required(query, "Dirección o lugar"))

    fun paypal(user: String, amount: String, currency: String): String {
        var link = "https://paypal.me/${handle(user, "Usuario de PayPal")}"
        if (amount.isNotBlank()) {
            val normalized = amount.trim().replace(",", ".")
            normalized.toDoubleOrNull() ?: throw InvalidInput("La cantidad debe ser un número.")
            link += "/$normalized${currency.uppercase()}"
        }
        return link
    }

    private fun meEscape(v: String): String {
        var out = v
        for (ch in listOf("\\", ";", ",", ":")) out = out.replace(ch, "\\" + ch)
        return out
    }

    fun mecard(name: String, phone: String, email: String, note: String): String {
        val parts = mutableListOf("N:${meEscape(required(name, "Nombre"))}")
        if (phone.isNotBlank()) parts += "TEL:${digits(phone)}"
        if (email.isNotBlank()) parts += "EMAIL:${meEscape(email.trim())}"
        if (note.isNotBlank()) parts += "NOTE:${meEscape(note.trim())}"
        return "MECARD:" + parts.joinToString(";") + ";;"
    }
}
