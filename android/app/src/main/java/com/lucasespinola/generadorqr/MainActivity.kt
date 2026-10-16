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
import androidx.compose.runtime.derivedStateOf
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

private const val PREFS = "ajustes"
private const val PREVIEW_PX = 720

private val CODE_COLORS = listOf(0xFF000000, 0xFF1A1A1A, 0xFF1A3D8F, 0xFF0B5D3B, 0xFF7A0E1E, 0xFFE05A00, 0xFF4B2A7A, 0xFFFFFFFF)
    .map { it.toInt() }
private val BACK_COLORS = listOf(0xFFFFFFFF, 0xFFF2F1ED, 0xFFFFF4E0, 0xFFE8F0FF, 0xFF0E0F11, 0xFF000000)
    .map { it.toInt() }

/** Resultado de generar: o datos válidos con su matriz, o un mensaje de error. */
private sealed interface Output {
    data class Ready(val data: String, val matrix: QrMatrix, val preview: Bitmap) : Output
    data class Invalid(val message: String) : Output
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        setContent {
            var dark by remember { mutableStateOf(prefs.getBoolean("oscuro", true)) }
            LaunchedEffect(dark) {
                val style = if (dark) SystemBarStyle.dark(AColor.TRANSPARENT)
                else SystemBarStyle.light(AColor.TRANSPARENT, AColor.TRANSPARENT)
                enableEdgeToEdge(statusBarStyle = style, navigationBarStyle = style)
                prefs.edit().putBoolean("oscuro", dark).apply()
            }
            CompositionLocalProvider(LocalPalette provides if (dark) DarkPalette else LightPalette) {
                GeneratorScreen(dark = dark, onToggleTheme = { dark = !dark })
            }
        }
    }
}

@Composable
private fun GeneratorScreen(dark: Boolean, onToggleTheme: () -> Unit) {
    val p = LocalPalette.current
    val context = LocalContext.current

    var typeIndex by remember { mutableIntStateOf(0) }
    val values = remember { mutableStateMapOf<String, String>() }
    var fill by remember { mutableIntStateOf(CODE_COLORS[0]) }
    var back by remember { mutableIntStateOf(BACK_COLORS[0]) }
    var level by remember { mutableStateOf(ErrorCorrectionLevel.M) }
    var box by remember { mutableIntStateOf(16) }
    var logo by remember { mutableStateOf<Bitmap?>(null) }

    val type = QR_TYPES[typeIndex]
    val effectiveLevel = if (logo != null) ErrorCorrectionLevel.H else level
    val style = QrStyle(fill = fill, back = back, level = effectiveLevel, logo = logo)

    // Solo se recalcula cuando cambian los datos o el estilo (no con cada recomposición).
    val output by remember(typeIndex, style) {
        derivedStateOf {
            val fields = type.fields.associate { it.key to (values["${type.code}.${it.key}"] ?: "") }
                .filterValues { it.isNotEmpty() }
            try {
                val data = type.build(fields)
                val matrix = QrEngine.encode(data, effectiveLevel)
                val n = matrix.size + style.border * 2
                Output.Ready(data, matrix, QrEngine.render(matrix, style, maxOf(1, PREVIEW_PX / n)))
            } catch (e: IllegalArgumentException) {
                Output.Invalid(e.message ?: "Datos no válidos.")
            }
        }
    }
    val ready = output as? Output.Ready

    val savePng = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("image/png")) { uri ->
        if (uri != null && ready != null) {
            writeTo(context, uri) { QrEngine.render(ready.matrix, style, box).compress(Bitmap.CompressFormat.PNG, 100, it) }
        }
    }
    val saveSvg = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("image/svg+xml")) { uri ->
        if (uri != null && ready != null) {
            writeTo(context, uri) { it.write(QrEngine.svg(ready.matrix, style, box).toByteArray()) }
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
                modifier = Modifier.padding(start = 16.dp),
            )
            Text("v1.0", style = Type.label, color = p.muted, modifier = Modifier.padding(start = 10.dp).weight(1f))
            Segmented(
                listOf("CLARO", "OSCURO"), if (dark) 1 else 0, { if ((it == 1) != dark) onToggleTheme() },
                Modifier.padding(end = 12.dp).width(150.dp).height(30.dp),
            )
        }
        Divider()

        // ---------- Tipos ----------
        Row(
            Modifier.fillMaxWidth().background(p.surface).horizontalScroll(rememberScrollState())
                .padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            QR_TYPES.forEachIndexed { i, t ->
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
            Text("%02d / %s".format(typeIndex + 1, type.code), style = Type.label, color = p.accent)
            Text(type.name, style = Type.title, color = p.text, modifier = Modifier.padding(bottom = 8.dp))

            // ---------- Vista previa ----------
            Box(
                Modifier.fillMaxWidth().aspectRatio(1f).background(p.surface)
                    .border(1.dp, p.borderStrong).padding(2.dp),
                contentAlignment = Alignment.Center,
            ) {
                when (val o = output) {
                    is Output.Ready -> Image(
                        o.preview.asImageBitmap(), contentDescription = "Código QR",
                        modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Fit,
                        filterQuality = FilterQuality.None,
                    )
                    is Output.Invalid -> Text(
                        "SIN DATOS\ncompleta los campos", style = Type.label, color = p.muted,
                        textAlign = TextAlign.Center,
                    )
                }
            }
            val readout = when (val o = output) {
                is Output.Ready -> "V%02d · %d×%d MÓD · CORR %s · %d B".format(
                    o.matrix.version, o.matrix.size, o.matrix.size, effectiveLevel.name, o.data.toByteArray().size,
                )
                is Output.Invalid -> o.message
            }
            Text(
                readout, style = Type.label.copy(fontWeight = FontWeight.Normal),
                color = if (ready == null && values.keys.any { it.startsWith("${type.code}.") }) p.error else p.muted,
                modifier = Modifier.padding(top = 6.dp, bottom = 10.dp),
            )

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                IndButton("GUARDAR PNG", primary = true, enabled = ready != null, modifier = Modifier.weight(1f)) {
                    savePng.launch("qr-${type.code.lowercase()}.png")
                }
                IndButton("COMPARTIR", enabled = ready != null, modifier = Modifier.weight(1f)) {
                    ready?.let { share(context, QrEngine.render(it.matrix, style, box)) }
                }
            }
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                IndButton("SVG", enabled = ready != null, modifier = Modifier.weight(1f)) {
                    saveSvg.launch("qr-${type.code.lowercase()}.svg")
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
            type.fields.forEach { f ->
                val key = "${type.code}.${f.key}"
                when (f.kind) {
                    Kind.CHECK -> CheckRow(f.label, values[key] == "true") { values[key] = it.toString() }
                    Kind.CHOICE -> {
                        FieldLabel(f.label)
                        val selected = f.options.indexOf(values[key] ?: f.options[0]).coerceAtLeast(0)
                        if (f.options.size <= 3) {
                            Segmented(f.options, selected, { values[key] = f.options[it] }, Modifier.fillMaxWidth().height(40.dp))
                        } else {
                            ChoiceGrid(f.options, selected) { values[key] = f.options[it] }
                        }
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

            // ---------- Ajustes ----------
            SectionTitle("AJUSTES")
            FieldLabel("Color del código")
            Swatches(CODE_COLORS, fill) { fill = it }
            FieldLabel("Color de fondo")
            Swatches(BACK_COLORS, back) { back = it }

            FieldLabel(if (logo != null) "Corrección (H forzada por el logo)" else "Corrección de errores")
            val levels = listOf(ErrorCorrectionLevel.L, ErrorCorrectionLevel.M, ErrorCorrectionLevel.Q, ErrorCorrectionLevel.H)
            Segmented(
                levels.map { it.name }, levels.indexOf(effectiveLevel),
                { if (logo == null) level = levels[it] }, Modifier.fillMaxWidth().height(40.dp),
            )

            FieldLabel("Tamaño al exportar · $box px/módulo")
            Slider(
                value = box.toFloat(), onValueChange = { box = it.toInt() }, valueRange = 4f..30f, steps = 25,
                colors = SliderDefaults.colors(
                    thumbColor = p.accent, activeTrackColor = p.accent, inactiveTrackColor = p.surface2,
                    activeTickColor = Color.Transparent, inactiveTickColor = Color.Transparent,
                ),
            )

            FieldLabel("Logo central")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                IndButton(if (logo == null) "ELEGIR IMAGEN" else "CAMBIAR LOGO", modifier = Modifier.weight(1f)) {
                    pickLogo.launch("image/*")
                }
                if (logo != null) IndButton("QUITAR", modifier = Modifier.width(110.dp)) { logo = null }
            }

            Text(
                "© Lucas Espinola · MIT", style = Type.label.copy(fontWeight = FontWeight.Normal), color = p.muted,
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
            SegmentCell(label, i == selected, { onSelect(i) })
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
        Text(label, style = Type.button.copy(fontSize = 12.sp), color = if (active) p.onAccent else p.text)
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

@Composable
private fun Swatches(colors: List<Int>, selected: Int, onSelect: (Int) -> Unit) {
    val p = LocalPalette.current
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
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
    val file = File(dir, "codigo-qr.png")
    file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "image/png"
        putExtra(Intent.EXTRA_STREAM, uri)
        clipData = ClipData.newRawUri("QR", uri)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    context.startActivity(Intent.createChooser(intent, "Compartir QR"))
}

private fun copyText(context: Context, text: String) {
    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
    cm.setPrimaryClip(ClipData.newPlainText("QR", text))
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
