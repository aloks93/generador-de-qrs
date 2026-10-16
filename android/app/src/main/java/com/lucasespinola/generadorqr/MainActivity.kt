package com.lucasespinola.generadorqr

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color as AColor
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.FileProvider
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

private const val PREFS = "ajustes"
private const val PREVIEW_PX = 720
private const val DEBOUNCE_MS = 120L

private val CODE_COLORS = listOf(0xFF000000, 0xFF1A1A1A, 0xFF1A3D8F, 0xFF0B5D3B, 0xFF7A0E1E, 0xFFE05A00, 0xFF4B2A7A, 0xFFFFFFFF)
    .map { it.toInt() }
private val BACK_COLORS = listOf(0xFFFFFFFF, 0xFFF2F1ED, 0xFFFFF4E0, 0xFFE8F0FF, 0xFF0E0F11, 0xFF000000)
    .map { it.toInt() }
private val ACCENT_COLORS = listOf(0xFFE05A00, 0xFF1A3D8F, 0xFF0B5D3B, 0xFF7A0E1E, 0xFF4B2A7A, 0xFF00A3A3, 0xFFD4A017, 0xFF000000)
    .map { it.toInt() }
private val MATRIX_SYMBOLOGIES = Symbology.values().filter { !it.linear }

/** Resultado de generar: o datos válidos con su matriz, o un mensaje de error. */
private sealed interface Output {
    data class Ready(val data: String, val symbol: Symbol, val preview: Bitmap) : Output
    data class Invalid(val message: String) : Output
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        setContent {
            var dark by remember { mutableStateOf(prefs.getBoolean("oscuro", true)) }
            var advanced by remember { mutableStateOf(prefs.getBoolean("avanzado", false)) }
            LaunchedEffect(dark) {
                val style = if (dark) SystemBarStyle.dark(AColor.TRANSPARENT)
                else SystemBarStyle.light(AColor.TRANSPARENT, AColor.TRANSPARENT)
                enableEdgeToEdge(statusBarStyle = style, navigationBarStyle = style)
                prefs.edit().putBoolean("oscuro", dark).apply()
            }
            LaunchedEffect(advanced) { prefs.edit().putBoolean("avanzado", advanced).apply() }
            CompositionLocalProvider(LocalPalette provides if (dark) DarkPalette else LightPalette) {
                GeneratorScreen(
                    dark = dark, onToggleTheme = { dark = !dark },
                    advanced = advanced, onSetAdvanced = { advanced = it },
                )
            }
        }
    }
}

@Composable
private fun GeneratorScreen(dark: Boolean, onToggleTheme: () -> Unit, advanced: Boolean, onSetAdvanced: (Boolean) -> Unit) {
    val p = LocalPalette.current
    val context = LocalContext.current

    var typeIndex by remember { mutableIntStateOf(0) }
    val values = remember { mutableStateMapOf<String, String>() }
    var fill by remember { mutableIntStateOf(CODE_COLORS[0]) }
    var back by remember { mutableIntStateOf(BACK_COLORS[0]) }
    var logo by remember { mutableStateOf<Bitmap?>(null) }
    // Ajustes avanzados: se conservan aunque se vuelva al modo normal.
    var adv by remember { mutableStateOf(QrStyle()) }
    var matrixSymbology by remember { mutableStateOf(Symbology.QR) }
    var box by remember { mutableIntStateOf(16) }

    val type = ALL_TYPES[typeIndex]
    val symbology = type.symbology ?: if (advanced) matrixSymbology else Symbology.QR
    val style = if (advanced) adv.copy(fill = fill, back = back, logo = logo) else QrStyle(fill = fill, back = back, logo = logo)
    val exportBox = if (advanced) box else 16

    val fields = type.fields.filter { advanced || !it.advanced }
        .associate { it.key to (values["${type.code}.${it.key}"] ?: "") }
        .filterValues { it.isNotEmpty() }

    // El código se genera fuera del hilo principal y tras una pausa al teclear: si se
    // hiciera en cada pulsación, al escribir rápido el campo de texto perdería letras.
    var output by remember { mutableStateOf<Output>(Output.Invalid("")) }
    LaunchedEffect(typeIndex, fields, style, symbology) {
        delay(DEBOUNCE_MS)
        output = withContext(Dispatchers.Default) {
            try {
                val data = type.build(fields)
                val symbol = QrEngine.encode(data, symbology, style)
                Output.Ready(data, symbol, QrEngine.render(symbol, style, QrEngine.boxFor(symbol, style, PREVIEW_PX)))
            } catch (e: IllegalArgumentException) {
                Output.Invalid(e.message ?: "Datos no válidos.")
            }
        }
    }
    val ready = output as? Output.Ready

    val savePng = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("image/png")) { uri ->
        if (uri != null && ready != null) {
            writeTo(context, uri) { QrEngine.render(ready.symbol, style, exportBox).compress(Bitmap.CompressFormat.PNG, 100, it) }
        }
    }
    val saveSvg = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("image/svg+xml")) { uri ->
        if (uri != null && ready != null) {
            writeTo(context, uri) { it.write(QrEngine.svg(ready.symbol, style, exportBox).toByteArray()) }
        }
    }
    val pickLogo = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) logo = loadLogo(context, uri) ?: logo.also { toast(context, "No se pudo abrir la imagen.") }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(p.bg)
            .systemBarsPadding()
            .imePadding(),
    ) {
        // ---------- Cabecera ----------
        Row(
            Modifier.fillMaxWidth().height(52.dp).background(p.surface),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(Modifier.width(5.dp).fillMaxHeight().background(p.accent))
            Text(
                "QR//GEN", color = p.text, fontSize = 20.sp, fontWeight = FontWeight.Black,
                modifier = Modifier.padding(start = 14.dp).weight(1f),
            )
            Segmented(
                listOf("NORMAL", "AVANZ."), if (advanced) 1 else 0, { onSetAdvanced(it == 1) },
                Modifier.width(150.dp).height(30.dp),
            )
            Box(
                Modifier.padding(horizontal = 10.dp).size(30.dp).border(1.dp, p.border).background(p.surface2)
                    .clickable(onClick = onToggleTheme),
                contentAlignment = Alignment.Center,
            ) {
                Text(if (dark) "☾" else "☀", color = p.text, fontSize = 15.sp)
            }
        }
        Divider()

        // ---------- Tipos ----------
        Row(
            Modifier.fillMaxWidth().background(p.surface).horizontalScroll(rememberScrollState())
                .padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            ALL_TYPES.forEachIndexed { i, t ->
                if (i == QR_TYPES.size) {
                    Text("BARRAS", style = Type.label, color = p.muted, modifier = Modifier.padding(horizontal = 6.dp))
                }
                val active = i == typeIndex
                Box(
                    Modifier
                        .background(if (active) p.accent else p.surface2)
                        .border(1.dp, if (active) p.accent else p.border)
                        .clickable { typeIndex = i }
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                ) {
                    Text(
                        "%02d %s".format(i + 1, t.code), style = Type.button,
                        color = if (active) p.onAccent else p.text,
                    )
                }
            }
        }
        Divider()

        Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp)) {
            val group = if (type.linear) "BARRAS" else "QR"
            Text("%02d / %s / %s".format(typeIndex + 1, group, type.code), style = Type.label, color = p.accent)
            Text(type.name, style = Type.title, color = p.text, modifier = Modifier.padding(bottom = 8.dp))

            // ---------- Vista previa ----------
            val ratio = ready?.let { it.preview.width.toFloat() / it.preview.height } ?: 1f
            Box(
                Modifier.fillMaxWidth(if (ratio > 1.2f) 1f else 0.7f).align(Alignment.CenterHorizontally)
                    .aspectRatio(ratio.coerceAtLeast(0.5f))
                    .background(p.surface).border(1.dp, p.borderStrong).padding(2.dp),
                contentAlignment = Alignment.Center,
            ) {
                when (val o = output) {
                    is Output.Ready -> Image(
                        o.preview.asImageBitmap(), contentDescription = "Código generado",
                        modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Fit,
                        filterQuality = if (style.styled) FilterQuality.Medium else FilterQuality.None,
                    )
                    is Output.Invalid -> Text(
                        "SIN DATOS\ncompleta los campos", style = Type.label, color = p.muted,
                        textAlign = TextAlign.Center,
                    )
                }
            }
            val readout = when (val o = output) {
                is Output.Ready -> {
                    val s = o.symbol
                    when {
                        s.linear -> "${symbology.label.uppercase()} · ${s.width} MÓD · ${s.text}"
                        s.version != null -> "V%02d · %d×%d MÓD · CORR %s · %d B".format(
                            s.version, s.width, s.height, if (logo != null) "H" else style.level.name, o.data.toByteArray().size,
                        )
                        else -> "${symbology.label.uppercase()} · ${s.width}×${s.height} MÓD · ${o.data.toByteArray().size} B"
                    }
                }
                is Output.Invalid -> o.message
            }
            Text(
                readout, style = Type.label.copy(fontWeight = FontWeight.Normal),
                color = if (ready == null && fields.isNotEmpty()) p.error else p.muted,
                modifier = Modifier.padding(top = 6.dp, bottom = 10.dp),
            )

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                IndButton("GUARDAR PNG", primary = true, enabled = ready != null, modifier = Modifier.weight(1f)) {
                    savePng.launch("codigo-${type.code.lowercase()}.png")
                }
                IndButton("COMPARTIR", enabled = ready != null, modifier = Modifier.weight(1f)) {
                    ready?.let { share(context, QrEngine.render(it.symbol, style, exportBox)) }
                }
            }
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                IndButton("SVG", enabled = ready != null, modifier = Modifier.weight(1f)) {
                    saveSvg.launch("codigo-${type.code.lowercase()}.svg")
                }
                IndButton("COPIAR TEXTO", enabled = ready != null, modifier = Modifier.weight(1f)) {
                    ready?.let { copyText(context, it.data) }
                }
            }

            // ---------- Formulario ----------
            if (type.hint.isNotEmpty()) {
                Row(
                    Modifier.padding(top = 18.dp).fillMaxWidth().background(p.warnBg).border(1.dp, p.accent)
                        .padding(12.dp),
                ) {
                    Text("NOTA", style = Type.label, color = p.accent, modifier = Modifier.padding(end = 10.dp))
                    Text(type.hint, style = Type.body.copy(fontSize = 13.sp), color = p.text)
                }
            }
            SectionTitle("DATOS")
            type.fields.filter { advanced || !it.advanced }.forEach { f ->
                val key = "${type.code}.${f.key}"
                when (f.kind) {
                    Kind.CHECK -> CheckRow(f.label, values[key] == "true") { values[key] = it.toString() }
                    Kind.CHOICE -> {
                        FieldLabel(f.label)
                        val selected = f.options.indexOf(values[key] ?: f.options[0]).coerceAtLeast(0)
                        ChoiceGrid(f.options, selected) { values[key] = f.options[it] }
                    }
                    else -> {
                        FieldLabel(f.label)
                        Input(
                            value = values[key] ?: "",
                            onChange = { values[key] = it },
                            placeholder = f.placeholder,
                            multiline = f.kind == Kind.TEXT,
                            password = f.password,
                            numeric = f.numeric,
                        )
                    }
                }
            }

            // ---------- Ajustes básicos ----------
            SectionTitle(if (advanced) "AJUSTES AVANZADOS" else "AJUSTES")
            FieldLabel("Color del código")
            Swatches(CODE_COLORS, fill) { fill = it ?: fill }
            FieldLabel("Color de fondo")
            Swatches(BACK_COLORS, back) { back = it ?: back }
            if (!type.linear) {
                FieldLabel("Logo central")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IndButton(if (logo == null) "ELEGIR IMAGEN" else "CAMBIAR LOGO", modifier = Modifier.weight(1f)) {
                        pickLogo.launch("image/*")
                    }
                    if (logo != null) IndButton("QUITAR", modifier = Modifier.width(110.dp)) { logo = null }
                }
            }
            if (!advanced) {
                Text(
                    "Activa el modo AVANZ. para elegir formato (Data Matrix, Aztec, PDF417), forma de módulos y ojos, " +
                        "degradados, transparencia, texto, bordes y más.",
                    style = Type.body.copy(fontSize = 13.sp), color = p.muted, modifier = Modifier.padding(top = 16.dp),
                )
            }

            // ---------- Ajustes avanzados ----------
            if (advanced) {
                val is2d = !symbology.linear
                if (type.symbology == null) {
                    FieldLabel("Formato 2D")
                    ChoiceGrid(MATRIX_SYMBOLOGIES.map { it.label }, MATRIX_SYMBOLOGIES.indexOf(matrixSymbology)) {
                        matrixSymbology = MATRIX_SYMBOLOGIES[it]
                    }
                }
                if (symbology == Symbology.QR) {
                    FieldLabel(if (logo != null) "Corrección (H forzada por el logo)" else "Corrección de errores")
                    val levels = listOf(ErrorCorrectionLevel.L, ErrorCorrectionLevel.M, ErrorCorrectionLevel.Q, ErrorCorrectionLevel.H)
                    Segmented(
                        levels.map { it.name }, levels.indexOf(if (logo != null) ErrorCorrectionLevel.H else adv.level),
                        { if (logo == null) adv = adv.copy(level = levels[it]) }, Modifier.fillMaxWidth().height(40.dp),
                    )
                    Stepper("Versión mínima", adv.version, 1, 40) { adv = adv.copy(version = it) }
                    Stepper("Máscara", adv.mask, 0, 7) { adv = adv.copy(mask = it) }
                }
                if (is2d) {
                    FieldLabel("Forma de los módulos")
                    ChoiceGrid(ModuleShape.values().map { it.label }, adv.moduleShape.ordinal) {
                        adv = adv.copy(moduleShape = ModuleShape.values()[it])
                    }
                    SliderRow("Escala del módulo", "${(adv.moduleScale * 100).toInt()}%", adv.moduleScale * 100, 50f..100f, 9) {
                        adv = adv.copy(moduleScale = it / 100f)
                    }
                }
                if (symbology == Symbology.QR) {
                    FieldLabel("Forma de los ojos")
                    ChoiceGrid(EyeShape.values().map { it.label }, adv.eyeShape.ordinal) {
                        adv = adv.copy(eyeShape = EyeShape.values()[it])
                    }
                    FieldLabel("Color del ojo exterior")
                    Swatches(ACCENT_COLORS, adv.eyeColor, allowSame = true) { adv = adv.copy(eyeColor = it) }
                    FieldLabel("Color del ojo interior")
                    Swatches(ACCENT_COLORS, adv.eyeInnerColor, allowSame = true) { adv = adv.copy(eyeInnerColor = it) }
                }
                FieldLabel("Degradado")
                ChoiceGrid(Gradient.values().map { it.label }, adv.gradient.ordinal) {
                    adv = adv.copy(gradient = Gradient.values()[it])
                }
                if (adv.gradient != Gradient.NONE) {
                    FieldLabel("Segundo color")
                    Swatches(ACCENT_COLORS, adv.gradientColor) { adv = adv.copy(gradientColor = it ?: adv.gradientColor) }
                }
                CheckRow("Fondo transparente (PNG/SVG)", adv.transparent) { adv = adv.copy(transparent = it) }
                SliderRow("Borde (zona de silencio)", "${adv.border}", adv.border.toFloat(), 0f..10f, 9) {
                    adv = adv.copy(border = it.toInt())
                }
                SliderRow("Tamaño al exportar", "$box px/mód", box.toFloat(), 2f..30f, 27) { box = it.toInt() }
                if (is2d && logo != null) {
                    SliderRow("Tamaño del logo", "${(adv.logoRatio * 100).toInt()}%", adv.logoRatio * 100, 10f..35f, 24) {
                        adv = adv.copy(logoRatio = it / 100f)
                    }
                    CheckRow("Recuadro detrás del logo", adv.logoPad) { adv = adv.copy(logoPad = it) }
                }
                if (symbology.linear) {
                    SliderRow("Altura de las barras", "${adv.barHeight}", adv.barHeight.toFloat(), 10f..120f, 21) {
                        adv = adv.copy(barHeight = it.toInt())
                    }
                    CheckRow("Mostrar los dígitos", adv.showText) { adv = adv.copy(showText = it) }
                }
                if (!symbology.linear || !adv.showText) {
                    FieldLabel("Texto debajo del código")
                    Input(adv.caption, { adv = adv.copy(caption = it) }, "p. ej. ESCANÉAME", multiline = false, password = false, numeric = false)
                }
                SliderRow(
                    "Tamaño del texto", if (adv.captionSize == 0) "AUTO" else "${adv.captionSize}",
                    adv.captionSize.toFloat(), 0f..60f, 59,
                ) { adv = adv.copy(captionSize = it.toInt()) }
                FieldLabel("Color del texto")
                Swatches(ACCENT_COLORS, adv.captionColor, allowSame = true) { adv = adv.copy(captionColor = it) }
                Box(Modifier.padding(top = 18.dp)) {
                    IndButton("RESTABLECER AJUSTES", modifier = Modifier.fillMaxWidth()) {
                        adv = QrStyle(); matrixSymbology = Symbology.QR; box = 16
                    }
                }
            }

            Text(
                "© Lucas Espinola · MIT · v1.1", style = Type.label.copy(fontWeight = FontWeight.Normal), color = p.muted,
                modifier = Modifier.fillMaxWidth().padding(top = 28.dp, bottom = 12.dp), textAlign = TextAlign.Center,
            )
        }
    }
}

// ---------- Componentes ----------

@Composable
private fun Divider() {
    Box(Modifier.fillMaxWidth().height(1.dp).background(LocalPalette.current.border))
}

@Composable
private fun SectionTitle(text: String) {
    val p = LocalPalette.current
    Column(Modifier.padding(top = 24.dp, bottom = 4.dp)) {
        Text(text, style = Type.label, color = p.muted)
        Box(Modifier.padding(top = 6.dp).fillMaxWidth().height(1.dp).background(p.border))
    }
}

@Composable
private fun FieldLabel(text: String) {
    Text(
        text.uppercase(), style = Type.label.copy(fontWeight = FontWeight.Normal),
        color = LocalPalette.current.muted, modifier = Modifier.padding(top = 14.dp, bottom = 6.dp),
    )
}

@Composable
private fun IndButton(
    text: String,
    modifier: Modifier = Modifier,
    primary: Boolean = false,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    val p = LocalPalette.current
    val bg = if (primary) p.accent else Color.Transparent
    val fg = if (primary) p.onAccent else p.text
    Box(
        modifier
            .heightIn(min = 46.dp)
            .background(if (enabled) bg else p.surface2)
            .border(BorderStroke(1.dp, if (primary && enabled) p.accent else p.borderStrong))
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, style = Type.button, color = if (enabled) fg else p.muted)
    }
}

@Composable
private fun Segmented(options: List<String>, selected: Int, onSelect: (Int) -> Unit, modifier: Modifier = Modifier) {
    val p = LocalPalette.current
    Row(modifier.border(1.dp, p.border).background(p.border).padding(1.dp)) {
        options.forEachIndexed { i, label ->
            SegmentCell(label, i == selected) { onSelect(i) }
            if (i < options.lastIndex) Spacer(Modifier.width(1.dp))
        }
    }
}

@Composable
private fun RowScope.SegmentCell(label: String, active: Boolean, onClick: () -> Unit) {
    val p = LocalPalette.current
    Box(
        Modifier.weight(1f).fillMaxHeight().background(if (active) p.accent else p.surface2).clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = Type.button.copy(fontSize = 12.sp), color = if (active) p.onAccent else p.text, textAlign = TextAlign.Center)
    }
}

@Composable
private fun ChoiceGrid(options: List<String>, selected: Int, onSelect: (Int) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        options.chunked(3).forEachIndexed { row, chunk ->
            Segmented(chunk, selected - row * 3, { onSelect(row * 3 + it) }, Modifier.fillMaxWidth().height(40.dp))
        }
    }
}

@Composable
private fun Stepper(label: String, value: Int?, min: Int, max: Int, onChange: (Int?) -> Unit) {
    val p = LocalPalette.current
    FieldLabel(label)
    Row(Modifier.fillMaxWidth().height(40.dp).border(1.dp, p.border), verticalAlignment = Alignment.CenterVertically) {
        StepButton("−") { onChange(value?.let { if (it <= min) null else it - 1 }) }
        Text(
            value?.toString() ?: "AUTO", style = Type.button, color = p.text, textAlign = TextAlign.Center,
            modifier = Modifier.weight(1f),
        )
        StepButton("+") { onChange(((value ?: (min - 1)) + 1).coerceAtMost(max)) }
    }
}

@Composable
private fun StepButton(text: String, onClick: () -> Unit) {
    val p = LocalPalette.current
    Box(
        Modifier.width(56.dp).fillMaxHeight().background(p.surface2).clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { Text(text, color = p.text, fontSize = 18.sp, fontWeight = FontWeight.Bold) }
}

@Composable
private fun SliderRow(
    label: String, valueText: String, value: Float, range: ClosedFloatingPointRange<Float>, steps: Int,
    onChange: (Float) -> Unit,
) {
    val p = LocalPalette.current
    Row(Modifier.fillMaxWidth().padding(top = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label.uppercase(), style = Type.label.copy(fontWeight = FontWeight.Normal), color = p.muted, modifier = Modifier.weight(1f))
        Text(valueText, style = Type.label, color = p.text)
    }
    Slider(
        value = value, onValueChange = onChange, valueRange = range, steps = steps,
        colors = SliderDefaults.colors(
            thumbColor = p.accent, activeTrackColor = p.accent, inactiveTrackColor = p.surface2,
            activeTickColor = Color.Transparent, inactiveTickColor = Color.Transparent,
        ),
    )
}

@Composable
private fun CheckRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    val p = LocalPalette.current
    Row(
        Modifier.padding(top = 16.dp).clickable { onChange(!checked) },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(22.dp).background(if (checked) p.accent else Color.Transparent)
                .border(2.dp, if (checked) p.accent else p.borderStrong),
            contentAlignment = Alignment.Center,
        ) {
            if (checked) Text("✓", color = p.onAccent, fontWeight = FontWeight.Bold, fontSize = 14.sp)
        }
        Text(label, style = Type.body, color = p.text, modifier = Modifier.padding(start = 10.dp))
    }
}

@Composable
private fun Input(
    value: String,
    onChange: (String) -> Unit,
    placeholder: String,
    multiline: Boolean,
    password: Boolean,
    numeric: Boolean,
) {
    val p = LocalPalette.current
    BasicTextField(
        value = value,
        onValueChange = onChange,
        singleLine = !multiline,
        minLines = if (multiline) 4 else 1,
        textStyle = TextStyle(color = p.text, fontSize = 15.sp),
        cursorBrush = SolidColor(p.accent),
        visualTransformation = if (password) PasswordVisualTransformation() else VisualTransformation.None,
        keyboardOptions = KeyboardOptions(
            keyboardType = when {
                password -> KeyboardType.Password
                numeric -> KeyboardType.Decimal
                else -> KeyboardType.Text
            },
        ),
        modifier = Modifier.fillMaxWidth(),
        decorationBox = { inner ->
            Box(
                Modifier.fillMaxWidth().background(p.surface).border(1.dp, p.border)
                    .padding(horizontal = 12.dp, vertical = 12.dp),
            ) {
                if (value.isEmpty() && placeholder.isNotEmpty()) Text(placeholder, color = p.muted, fontSize = 15.sp)
                inner()
            }
        },
    )
}

/** Muestras de color; con [allowSame] la primera significa «igual que el código» (null). */
@Composable
private fun Swatches(colors: List<Int>, selected: Int?, allowSame: Boolean = false, onSelect: (Int?) -> Unit) {
    val p = LocalPalette.current
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        if (allowSame) {
            val active = selected == null
            Box(
                Modifier.size(36.dp).border(if (active) 2.dp else 1.dp, if (active) p.accent else p.border)
                    .background(p.surface2).clickable { onSelect(null) },
                contentAlignment = Alignment.Center,
            ) { Text("=", color = p.text, fontWeight = FontWeight.Bold) }
        }
        colors.forEach { c ->
            val active = c == selected
            Box(
                Modifier.size(36.dp).border(if (active) 2.dp else 1.dp, if (active) p.accent else p.border)
                    .padding(if (active) 4.dp else 1.dp).background(Color(c)).clickable { onSelect(c) },
            )
        }
    }
}

// ---------- Acciones ----------

private fun writeTo(context: Context, uri: Uri, block: (java.io.OutputStream) -> Unit) {
    runCatching {
        context.contentResolver.openOutputStream(uri)?.use(block) ?: error("sin flujo")
    }.onSuccess { toast(context, "Guardado.") }
        .onFailure { toast(context, "No se pudo guardar: ${it.message}") }
}

private fun share(context: Context, bitmap: Bitmap) {
    val dir = File(context.cacheDir, "shared").apply { mkdirs() }
    val file = File(dir, "codigo.png")
    file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "image/png"
        putExtra(Intent.EXTRA_STREAM, uri)
        clipData = ClipData.newRawUri("Código", uri)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    context.startActivity(Intent.createChooser(intent, "Compartir código"))
}

private fun copyText(context: Context, text: String) {
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText("Código", text))
    toast(context, "Contenido copiado.")
}

private fun loadLogo(context: Context, uri: Uri): Bitmap? = runCatching {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
    var sample = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= 512) sample *= 2
    val opts = BitmapFactory.Options().apply { inSampleSize = sample }
    context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, opts) }
}.getOrNull()

private fun toast(context: Context, text: String) = Toast.makeText(context, text, Toast.LENGTH_SHORT).show()
