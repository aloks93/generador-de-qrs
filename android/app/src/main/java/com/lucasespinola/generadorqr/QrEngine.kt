package com.lucasespinola.generadorqr

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.MultiFormatWriter
import com.google.zxing.WriterException
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import com.google.zxing.qrcode.encoder.Encoder

/** Simbologías disponibles (mismas que la app de escritorio, salvo Micro QR que ZXing no genera). */
enum class Symbology(val label: String, val linear: Boolean, val format: BarcodeFormat, val hint: String = "", val example: String = "") {
    QR("QR Code", false, BarcodeFormat.QR_CODE),
    DATAMATRIX("Data Matrix", false, BarcodeFormat.DATA_MATRIX),
    AZTEC("Aztec", false, BarcodeFormat.AZTEC),
    PDF417("PDF417", false, BarcodeFormat.PDF_417),
    EAN13("EAN-13", true, BarcodeFormat.EAN_13, "12 o 13 dígitos (el último es el dígito de control).", "590123412345"),
    EAN8("EAN-8", true, BarcodeFormat.EAN_8, "7 u 8 dígitos.", "9638507"),
    UPCA("UPC-A", true, BarcodeFormat.UPC_A, "11 o 12 dígitos.", "03600029145"),
    UPCE("UPC-E", true, BarcodeFormat.UPC_E, "7 u 8 dígitos, empezando por 0.", "0123456"),
    CODE128("Code 128", true, BarcodeFormat.CODE_128, "Cualquier texto ASCII (letras, números y símbolos).", "ABC-12345"),
    CODE39("Code 39", true, BarcodeFormat.CODE_39, "Mayúsculas A-Z, dígitos y los símbolos - . \$ / + % y espacio.", "CODE-39"),
    CODE93("Code 93", true, BarcodeFormat.CODE_93, "Mayúsculas A-Z, dígitos y - . \$ / + % espacio.", "CODE93"),
    ITF("ITF (2 de 5)", true, BarcodeFormat.ITF, "Solo dígitos, en cantidad par.", "12345678"),
    CODABAR("Codabar", true, BarcodeFormat.CODABAR, "Dígitos y - \$ : / . + con inicio y fin A-D (p. ej. A123B).", "A40156B"),
}

/** Matriz de módulos de un código (sin zona de silencio). */
class Symbol(
    val width: Int,
    val height: Int,
    private val cells: BooleanArray,
    val linear: Boolean,
    val text: String,
    val finders: List<Pair<Int, Int>> = emptyList(),
    val version: Int? = null,
) {
    operator fun get(x: Int, y: Int) = cells[y * width + x]
    fun isEye(x: Int, y: Int) = finders.any { (fx, fy) -> x in fx until fx + 7 && y in fy until fy + 7 }
}

enum class ModuleShape(val label: String) { SQUARE("Cuadrado"), ROUNDED("Redondeado"), DOTS("Puntos"), DIAMOND("Rombo") }
enum class EyeShape(val label: String) { SQUARE("Cuadrado"), ROUNDED("Redondeado"), CIRCLE("Círculo") }
enum class Gradient(val label: String) { NONE("Sin degradado"), HORIZONTAL("Horizontal"), VERTICAL("Vertical"), DIAGONAL("Diagonal"), RADIAL("Radial") }

data class QrStyle(
    val fill: Int = 0xFF000000.toInt(),
    val back: Int = 0xFFFFFFFF.toInt(),
    val level: ErrorCorrectionLevel = ErrorCorrectionLevel.M,
    val border: Int = 4,
    val logo: Bitmap? = null,
    // Avanzado
    val version: Int? = null,
    val mask: Int? = null,
    val transparent: Boolean = false,
    val gradient: Gradient = Gradient.NONE,
    val gradientColor: Int = 0xFF1A3D8F.toInt(),
    val moduleShape: ModuleShape = ModuleShape.SQUARE,
    val moduleScale: Float = 1f,
    val eyeShape: EyeShape = EyeShape.SQUARE,
    val eyeColor: Int? = null,
    val eyeInnerColor: Int? = null,
    val logoRatio: Float = 0.22f,
    val logoPad: Boolean = true,
    val caption: String = "",
    val captionSize: Int = 0,
    val captionColor: Int? = null,
    val barHeight: Int = 40,
    val showText: Boolean = true,
) {
    val styled get() = moduleShape != ModuleShape.SQUARE || moduleScale < 1f || eyeShape != EyeShape.SQUARE ||
        eyeColor != null || eyeInnerColor != null
}

object QrEngine {

    fun encode(data: String, symbology: Symbology, style: QrStyle): Symbol {
        if (data.isEmpty()) throw Payloads.InvalidInput("No hay contenido para generar el código.")
        return if (symbology == Symbology.QR) encodeQr(data, style) else encodeOther(data, symbology)
    }

    private fun encodeQr(data: String, style: QrStyle): Symbol {
        val level = if (style.logo != null) ErrorCorrectionLevel.H else style.level
        // La versión elegida es la mínima: si no caben los datos se prueba la siguiente.
        val versions: List<Int?> = style.version?.let { (it..40).toList() } ?: listOf(null)
        for (v in versions) {
            val hints = mutableMapOf<EncodeHintType, Any>(EncodeHintType.CHARACTER_SET to "UTF-8")
            v?.let { hints[EncodeHintType.QR_VERSION] = it }
            style.mask?.let { hints[EncodeHintType.QR_MASK_PATTERN] = it }
            val code = try {
                Encoder.encode(data, level, hints)
            } catch (e: WriterException) {
                continue
            }
            val m = code.matrix
            val n = m.width
            val cells = BooleanArray(n * n) { m.get(it % n, it / n).toInt() == 1 }
            return Symbol(n, n, cells, false, data, listOf(0 to 0, n - 7 to 0, 0 to n - 7), code.version.versionNumber)
        }
        throw Payloads.InvalidInput("Los datos son demasiado largos para un código QR. Reduce el contenido o usa un enlace.")
    }

    private fun encodeOther(data: String, sym: Symbology): Symbol {
        val hints = mutableMapOf<EncodeHintType, Any>(EncodeHintType.MARGIN to 0)
        if (!sym.linear) hints[EncodeHintType.CHARACTER_SET] = "UTF-8"
        val matrix = try {
            MultiFormatWriter().encode(data, sym.format, 0, 0, hints)
        } catch (e: Exception) { // WriterException o IllegalArgumentException según el formato
            val detail = if (sym.hint.isNotEmpty()) " ${sym.hint}" else ""
            throw Payloads.InvalidInput("Contenido no válido para ${sym.label}.$detail")
        }
        if (sym.linear) {
            val w = matrix.width
            return Symbol(w, 1, BooleanArray(w) { matrix.get(it, 0) }, true, readable(data, sym))
        }
        // Se recorta el margen que algunos escritores añaden igualmente.
        val rect = matrix.enclosingRectangle ?: intArrayOf(0, 0, matrix.width, matrix.height)
        val (left, top, w, h) = rect.toList()
        val cells = BooleanArray(w * h) { matrix.get(left + it % w, top + it / w) }
        return Symbol(w, h, cells, false, data)
    }

    /** Texto legible bajo las barras: en EAN/UPC incluye el dígito de control. */
    private fun readable(data: String, sym: Symbology): String {
        val length = when (sym) {
            Symbology.EAN13 -> 12
            Symbology.EAN8 -> 7
            Symbology.UPCA -> 11
            else -> return data
        }
        if (data.length != length) return data
        val digits = data.map { it - '0' }
        val sum = digits.reversed().mapIndexed { i, d -> if (i % 2 == 0) d * 3 else d }.sum()
        return data + ((10 - sum % 10) % 10)
    }

    // ---------- Geometría ----------

    private class Layout(
        val sym: Symbol, val cols: Int, val rows: Int, val bx: Int, val by: Int, val barRows: Int,
        val caption: String, val captionCells: Float, val captionFont: Float,
    )

    private fun layout(sym: Symbol, style: QrStyle, box: Int): Layout {
        val bx: Int
        val by: Int
        val barRows: Int
        if (sym.linear) {
            bx = maxOf(style.border, 1) * 2
            by = maxOf(style.border / 2, 1)
            barRows = maxOf(style.barHeight, 5)
        } else {
            bx = style.border
            by = style.border
            barRows = 1
        }
        val rows = (if (sym.linear) barRows else sym.height) + 2 * by
        val cols = sym.width + 2 * bx
        val caption = if (sym.linear && style.showText) sym.text else style.caption.trim()
        var font = if (style.captionSize > 0) style.captionSize.toFloat() / box
        else maxOf(2f, cols * if (sym.linear) 0.09f else 0.07f)
        if (sym.linear && style.captionSize == 0) font = minOf(font, barRows * 0.35f)
        return Layout(sym, cols, rows, bx, by, barRows, caption, if (caption.isNotEmpty()) font * 1.5f else 0f, font)
    }

    // ---------- Imagen ----------

    fun render(sym: Symbol, style: QrStyle, box: Int): Bitmap {
        val lay = layout(sym, style, box)
        val w = lay.cols * box
        val codeH = lay.rows * box
        val h = codeH + (lay.captionCells * box).toInt()
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bmp)
        canvas.drawColor(if (style.transparent) Color.TRANSPARENT else style.back)

        val paint = Paint(Paint.ANTI_ALIAS_FLAG)
        paint.color = style.fill
        gradientShader(style, w.toFloat(), codeH.toFloat())?.let { paint.shader = it }
        val s = box.toFloat()

        if (sym.linear) {
            paint.isAntiAlias = false
            var x = 0
            while (x < sym.width) {
                if (sym[x, 0]) {
                    val start = x
                    while (x < sym.width && sym[x, 0]) x++
                    canvas.drawRect((start + lay.bx) * s, lay.by * s, (x + lay.bx) * s, (lay.by + lay.barRows) * s, paint)
                } else x++
            }
        } else if (!style.styled) {
            paint.isAntiAlias = false
            for (y in 0 until sym.height) {
                var x = 0
                while (x < sym.width) {
                    if (sym[x, y]) {
                        val start = x
                        while (x < sym.width && sym[x, y]) x++
                        canvas.drawRect((start + lay.bx) * s, (y + lay.by) * s, (x + lay.bx) * s, (y + 1 + lay.by) * s, paint)
                    } else x++
                }
            }
        } else {
            val inset = (1 - style.moduleScale.coerceIn(0.3f, 1f)) * s / 2
            for (y in 0 until sym.height) for (x in 0 until sym.width) {
                if (!sym[x, y] || sym.isEye(x, y)) continue
                val r = RectF((x + lay.bx) * s + inset, (y + lay.by) * s + inset, (x + 1 + lay.bx) * s - inset, (y + 1 + lay.by) * s - inset)
                drawShape(canvas, style.moduleShape.name, r, paint)
            }
            val ring = Paint(paint)
            style.eyeColor?.let { ring.shader = null; ring.color = it }
            val inner = Paint(paint)
            (style.eyeInnerColor ?: style.eyeColor)?.let { inner.shader = null; inner.color = it }
            for ((fx, fy) in sym.finders) {
                val ox = (fx + lay.bx) * s
                val oy = (fy + lay.by) * s
                val path = Path().apply {
                    fillType = Path.FillType.EVEN_ODD
                    addShape(this, style.eyeShape, RectF(ox, oy, ox + 7 * s, oy + 7 * s))
                    addShape(this, style.eyeShape, RectF(ox + s, oy + s, ox + 6 * s, oy + 6 * s))
                }
                canvas.drawPath(path, ring)
                drawShape(canvas, style.eyeShape.name, RectF(ox + 2 * s, oy + 2 * s, ox + 5 * s, oy + 5 * s), inner)
            }
        }

        if (!sym.linear) style.logo?.let { drawLogo(canvas, it, lay, style, box) }
        if (lay.caption.isNotEmpty()) {
            val captionColor = style.captionColor ?: style.fill
            val text = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = captionColor
                textSize = lay.captionFont * s
                textAlign = Paint.Align.CENTER
                typeface = Typeface.create(if (sym.linear) Typeface.MONOSPACE else Typeface.SANS_SERIF, Typeface.BOLD)
            }
            val top = codeH - (if (sym.linear) lay.by * s else lay.by * s / 2)
            val centerY = top + lay.captionCells * s / 2
            canvas.drawText(lay.caption, w / 2f, centerY - (text.descent() + text.ascent()) / 2, text)
        }
        return bmp
    }

    private fun gradientShader(style: QrStyle, w: Float, h: Float): Shader? = when (style.gradient) {
        Gradient.NONE -> null
        Gradient.HORIZONTAL -> LinearGradient(0f, 0f, w, 0f, style.fill, style.gradientColor, Shader.TileMode.CLAMP)
        Gradient.VERTICAL -> LinearGradient(0f, 0f, 0f, h, style.fill, style.gradientColor, Shader.TileMode.CLAMP)
        Gradient.DIAGONAL -> LinearGradient(0f, 0f, w, h, style.fill, style.gradientColor, Shader.TileMode.CLAMP)
        Gradient.RADIAL -> RadialGradient(w / 2, h / 2, maxOf(w, h) * 0.7f, style.fill, style.gradientColor, Shader.TileMode.CLAMP)
    }

    private fun drawShape(canvas: Canvas, shape: String, r: RectF, paint: Paint) {
        when (shape) {
            "DOTS", "CIRCLE" -> canvas.drawOval(r, paint)
            "ROUNDED" -> canvas.drawRoundRect(r, r.width() * 0.35f, r.height() * 0.35f, paint)
            "DIAMOND" -> canvas.drawPath(Path().apply {
                moveTo(r.centerX(), r.top); lineTo(r.right, r.centerY()); lineTo(r.centerX(), r.bottom)
                lineTo(r.left, r.centerY()); close()
            }, paint)
            else -> canvas.drawRect(r, paint)
        }
    }

    private fun addShape(path: Path, shape: EyeShape, r: RectF) {
        when (shape) {
            EyeShape.CIRCLE -> path.addOval(r, Path.Direction.CW)
            EyeShape.ROUNDED -> path.addRoundRect(r, r.width() * 0.3f, r.height() * 0.3f, Path.Direction.CW)
            EyeShape.SQUARE -> path.addRect(r, Path.Direction.CW)
        }
    }

    private fun drawLogo(canvas: Canvas, logo: Bitmap, lay: Layout, style: QrStyle, box: Int) {
        val codeSide = minOf(lay.sym.width, lay.sym.height) * box
        val pad = if (style.logoPad) maxOf(2, box / 2) else 0
        val maxSide = maxOf(1, (codeSide * style.logoRatio.coerceIn(0.05f, 0.35f)).toInt() - pad * 2)
        val scale = minOf(maxSide.toFloat() / logo.width, maxSide.toFloat() / logo.height, 1f)
        val w = maxOf(1, (logo.width * scale).toInt())
        val h = maxOf(1, (logo.height * scale).toInt())
        val left = (lay.cols * box - w) / 2
        val top = (lay.rows * box - h) / 2
        if (style.logoPad) {
            val bg = Paint()
            bg.color = style.back
            if (style.transparent) bg.xfermode = android.graphics.PorterDuffXfermode(android.graphics.PorterDuff.Mode.CLEAR)
            canvas.drawRect(Rect(left - pad, top - pad, left + w + pad, top + h + pad), bg)
        }
        canvas.drawBitmap(logo, null, Rect(left, top, left + w, top + h), Paint(Paint.FILTER_BITMAP_FLAG))
    }

    // ---------- SVG ----------

    private fun f(v: Float): String = if (v == v.toInt().toFloat()) v.toInt().toString() else "%.3f".format(java.util.Locale.ROOT, v).trimEnd('0')

    private fun svgShape(shape: String, x: Float, y: Float, s: Float): String = when (shape) {
        "DOTS", "CIRCLE" -> "<circle cx=\"${f(x + s / 2)}\" cy=\"${f(y + s / 2)}\" r=\"${f(s / 2)}\"/>"
        "ROUNDED" -> "<rect x=\"${f(x)}\" y=\"${f(y)}\" width=\"${f(s)}\" height=\"${f(s)}\" rx=\"${f(s * 0.35f)}\"/>"
        "DIAMOND" -> "<path d=\"M${f(x + s / 2)} ${f(y)}L${f(x + s)} ${f(y + s / 2)}L${f(x + s / 2)} ${f(y + s)}L${f(x)} ${f(y + s / 2)}z\"/>"
        else -> "<rect x=\"${f(x)}\" y=\"${f(y)}\" width=\"${f(s)}\" height=\"${f(s)}\"/>"
    }

    fun svg(sym: Symbol, style: QrStyle, box: Int): String {
        val lay = layout(sym, style, box)
        val totalH = lay.rows + lay.captionCells
        val sb = StringBuilder()
        var fill = hex(style.fill)
        if (style.gradient != Gradient.NONE) {
            val stops = "<stop offset=\"0\" stop-color=\"${hex(style.fill)}\"/><stop offset=\"1\" stop-color=\"${hex(style.gradientColor)}\"/>"
            sb.append("<defs>")
            if (style.gradient == Gradient.RADIAL) {
                sb.append("<radialGradient id=\"g\" cx=\"0.5\" cy=\"0.5\" r=\"0.7\">$stops</radialGradient>")
            } else {
                val (x2, y2) = when (style.gradient) { Gradient.HORIZONTAL -> 1 to 0; Gradient.VERTICAL -> 0 to 1; else -> 1 to 1 }
                sb.append("<linearGradient id=\"g\" x1=\"0\" y1=\"0\" x2=\"$x2\" y2=\"$y2\">$stops</linearGradient>")
            }
            sb.append("</defs>")
            fill = "url(#g)"
        }
        if (!style.transparent) sb.append("<rect width=\"${lay.cols}\" height=\"${f(totalH)}\" fill=\"${hex(style.back)}\"/>")
        if (sym.linear || !style.styled) {
            val path = StringBuilder()
            for (y in 0 until sym.height) {
                var x = 0
                while (x < sym.width) {
                    if (sym[x, y]) {
                        val start = x
                        while (x < sym.width && sym[x, y]) x++
                        path.append("M${start + lay.bx} ${y * lay.barRows + lay.by}h${x - start}v${lay.barRows}h-${x - start}z")
                    } else x++
                }
            }
            sb.append("<path d=\"$path\" fill=\"$fill\" shape-rendering=\"crispEdges\"/>")
        } else {
            val sc = style.moduleScale.coerceIn(0.3f, 1f)
            val inset = (1 - sc) / 2
            sb.append("<g fill=\"$fill\">")
            for (y in 0 until sym.height) for (x in 0 until sym.width) {
                if (sym[x, y] && !sym.isEye(x, y)) sb.append(svgShape(style.moduleShape.name, x + lay.bx + inset, y + lay.by + inset, sc))
            }
            sb.append("</g>")
            val ring = style.eyeColor?.let { hex(it) } ?: fill
            val inner = (style.eyeInnerColor ?: style.eyeColor)?.let { hex(it) } ?: fill
            for ((fx, fy) in sym.finders) {
                val x = (fx + lay.bx).toFloat()
                val y = (fy + lay.by).toFloat()
                sb.append("<g fill=\"$ring\">")
                // Anillo: forma exterior menos la interior (se dibuja el hueco con el fondo).
                sb.append("<path fill-rule=\"evenodd\" d=\"${eyePath(style.eyeShape, x, y, 7f)}${eyePath(style.eyeShape, x + 1, y + 1, 5f)}\"/>")
                sb.append("</g><g fill=\"$inner\">${svgShape(style.eyeShape.name, x + 2, y + 2, 3f)}</g>")
            }
        }
        if (lay.caption.isNotEmpty()) {
            val top = lay.rows - if (sym.linear) lay.by.toFloat() else lay.by / 2f
            val family = if (sym.linear) "monospace" else "Arial, Helvetica, sans-serif"
            val text = lay.caption.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sb.append("<text x=\"${f(lay.cols / 2f)}\" y=\"${f(top + lay.captionCells / 2)}\" font-family=\"$family\" font-weight=\"bold\" ")
            sb.append("font-size=\"${f(lay.captionFont)}\" text-anchor=\"middle\" dominant-baseline=\"central\" ")
            sb.append("fill=\"${hex(style.captionColor ?: style.fill)}\">$text</text>")
        }
        return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<svg xmlns=\"http://www.w3.org/2000/svg\" " +
            "width=\"${lay.cols * box}\" height=\"${(totalH * box).toInt()}\" viewBox=\"0 0 ${lay.cols} ${f(totalH)}\">$sb</svg>\n"
    }

    private fun eyePath(shape: EyeShape, x: Float, y: Float, s: Float): String = when (shape) {
        EyeShape.CIRCLE -> { val r = s / 2; "M${f(x + r)} ${f(y)}a${f(r)} ${f(r)} 0 1 0 0.0001 0z" }
        EyeShape.ROUNDED -> {
            val r = s * 0.3f; val l = s - 2 * r
            "M${f(x + r)} ${f(y)}h${f(l)}a${f(r)} ${f(r)} 0 0 1 ${f(r)} ${f(r)}v${f(l)}a${f(r)} ${f(r)} 0 0 1 -${f(r)} ${f(r)}" +
                "h-${f(l)}a${f(r)} ${f(r)} 0 0 1 -${f(r)} -${f(r)}v-${f(l)}a${f(r)} ${f(r)} 0 0 1 ${f(r)} -${f(r)}z"
        }
        EyeShape.SQUARE -> "M${f(x)} ${f(y)}h${f(s)}v${f(s)}h-${f(s)}z"
    }

    /** Píxeles por módulo para que el lado mayor de la imagen ronde [target]. */
    fun boxFor(sym: Symbol, style: QrStyle, target: Int): Int {
        val lay = layout(sym, style, 1)
        return maxOf(1, target / maxOf(lay.cols, lay.rows))
    }

    fun hex(color: Int) = String.format("#%06X", color and 0xFFFFFF)
}
