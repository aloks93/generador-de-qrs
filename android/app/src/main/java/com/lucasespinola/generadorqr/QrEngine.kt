package com.lucasespinola.generadorqr

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Rect
import com.google.zxing.EncodeHintType
import com.google.zxing.WriterException
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import com.google.zxing.qrcode.encoder.Encoder

/** Matriz de módulos de un QR (sin borde). */
class QrMatrix(val size: Int, val version: Int, private val cells: BooleanArray) {
    operator fun get(x: Int, y: Int) = cells[y * size + x]
}

data class QrStyle(
    val fill: Int = 0xFF000000.toInt(),
    val back: Int = 0xFFFFFFFF.toInt(),
    val level: ErrorCorrectionLevel = ErrorCorrectionLevel.M,
    val border: Int = 4,
    val logo: Bitmap? = null,
)

object QrEngine {

    private const val LOGO_RATIO = 0.22f

    fun encode(data: String, level: ErrorCorrectionLevel): QrMatrix {
        if (data.isEmpty()) throw Payloads.InvalidInput("No hay contenido para generar el QR.")
        val code = try {
            Encoder.encode(data, level, mapOf(EncodeHintType.CHARACTER_SET to "UTF-8"))
        } catch (e: WriterException) {
            throw Payloads.InvalidInput("Los datos son demasiado largos para un código QR. Reduce el contenido o usa un enlace.")
        }
        val m = code.matrix
        val n = m.width
        val cells = BooleanArray(n * n) { m.get(it % n, it / n).toInt() == 1 }
        return QrMatrix(n, code.version.versionNumber, cells)
    }

    /** Dibuja el QR a [box] píxeles por módulo, con bordes nítidos. */
    fun render(matrix: QrMatrix, style: QrStyle, box: Int): Bitmap {
        val n = matrix.size + style.border * 2
        val pixels = IntArray(n * n) { i ->
            val x = i % n - style.border
            val y = i / n - style.border
            val on = x in 0 until matrix.size && y in 0 until matrix.size && matrix[x, y]
            if (on) style.fill else style.back
        }
        val small = Bitmap.createBitmap(pixels, n, n, Bitmap.Config.ARGB_8888)
        val big = Bitmap.createScaledBitmap(small, n * box, n * box, false)
        if (big !== small) small.recycle()
        style.logo?.let { drawLogo(big, it, matrix.size * box, box, style.back) }
        return big
    }

    private fun drawLogo(target: Bitmap, logo: Bitmap, codeSide: Int, box: Int, back: Int) {
        val pad = maxOf(2, box / 2)
        val maxSide = maxOf(1, (codeSide * LOGO_RATIO).toInt() - pad * 2)
        val scale = minOf(maxSide.toFloat() / logo.width, maxSide.toFloat() / logo.height, 1f)
        val w = maxOf(1, (logo.width * scale).toInt())
        val h = maxOf(1, (logo.height * scale).toInt())
        val left = (target.width - w) / 2
        val top = (target.height - h) / 2
        val canvas = Canvas(target)
        canvas.drawRect(
            Rect(left - pad, top - pad, left + w + pad, top + h + pad),
            Paint().apply { color = back },
        )
        canvas.drawBitmap(logo, null, Rect(left, top, left + w, top + h), Paint(Paint.FILTER_BITMAP_FLAG))
    }

    fun svg(matrix: QrMatrix, style: QrStyle, box: Int): String {
        val b = style.border
        val n = matrix.size + b * 2
        val path = StringBuilder()
        for (y in 0 until matrix.size) {
            var x = 0
            while (x < matrix.size) {
                if (matrix[x, y]) {
                    val start = x
                    while (x < matrix.size && matrix[x, y]) x++
                    path.append("M${start + b} ${y + b}h${x - start}v1h-${x - start}z")
                } else {
                    x++
                }
            }
        }
        val size = n * box
        return """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="$size" height="$size" viewBox="0 0 $n $n"><rect width="$n" height="$n" fill="${hex(style.back)}"/><path d="$path" fill="${hex(style.fill)}" shape-rendering="crispEdges"/></svg>
"""
    }

    fun hex(color: Int) = String.format("#%06X", color and 0xFFFFFF)
}
