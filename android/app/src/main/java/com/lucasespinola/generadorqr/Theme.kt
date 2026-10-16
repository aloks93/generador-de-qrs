package com.lucasespinola.generadorqr

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/** Paleta industrial: grafito / hormigón con acento naranja (igual que la app de escritorio). */
@Immutable
data class Palette(
    val bg: Color,
    val surface: Color,
    val surface2: Color,
    val border: Color,
    val borderStrong: Color,
    val text: Color,
    val muted: Color,
    val accent: Color,
    val onAccent: Color,
    val warnBg: Color,
    val error: Color,
    val ok: Color,
)

val DarkPalette = Palette(
    bg = Color(0xFF0E0F11), surface = Color(0xFF16181B), surface2 = Color(0xFF1E2125),
    border = Color(0xFF2E3238), borderStrong = Color(0xFF4A5058), text = Color(0xFFE8E6E1),
    muted = Color(0xFF8A9097), accent = Color(0xFFFF7A1A), onAccent = Color(0xFF0E0F11),
    warnBg = Color(0xFF2A1F12), error = Color(0xFFFF6B5E), ok = Color(0xFF7BD88F),
)

val LightPalette = Palette(
    bg = Color(0xFFE4E2DD), surface = Color(0xFFF2F1ED), surface2 = Color(0xFFD9D6CF),
    border = Color(0xFFA9A49A), borderStrong = Color(0xFF6E6A62), text = Color(0xFF121212),
    muted = Color(0xFF5E5B55), accent = Color(0xFFE05A00), onAccent = Color(0xFFFFFFFF),
    warnBg = Color(0xFFF6E7D2), error = Color(0xFFB3261E), ok = Color(0xFF2E6B2E),
)

val LocalPalette = staticCompositionLocalOf { DarkPalette }

object Type {
    val mono = FontFamily.Monospace
    val label = TextStyle(fontFamily = mono, fontSize = 11.sp, letterSpacing = 1.sp, fontWeight = FontWeight.Bold)
    val body = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 15.sp)
    val title = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 26.sp, fontWeight = FontWeight.Black)
    val button = TextStyle(fontFamily = mono, fontSize = 13.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
}
