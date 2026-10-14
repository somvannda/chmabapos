package com.chmaba.pos.ui.screens.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.components.ChmabaLogo
import com.chmaba.pos.ui.components.ChmabaTextField
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaBackground
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray300
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray600
import com.chmaba.pos.ui.theme.ChmabaGray700
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaGreen
import com.chmaba.pos.ui.theme.ChmabaLime
import com.chmaba.pos.ui.theme.ChmabaRed
import com.chmaba.pos.ui.theme.ChmabaSurface
import com.chmaba.pos.ui.theme.ChmabaViolet

private val HeroInk = Color(0xFF17181C)
private val HeroMuted = Color(0xFFA9AAB2)

/**
 * Shared shell for every auth screen: a dark hero over a white sheet with a
 * rounded top edge. Mirrors `.hero` + `.sheetcard` in the prototype, which in
 * turn mirrors the web's auth split panel.
 */
@Composable
fun AuthScaffold(
    title: String,
    subtitle: String,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxSize()
            // the sheet colour also paints the 18dp strip the offset exposes
            .background(ChmabaSurface),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    Brush.radialGradient(
                        colors = listOf(ChmabaLime.copy(alpha = 0.10f), Color.Transparent),
                        radius = 600f,
                    ),
                )
                .background(HeroInk)
                .padding(start = 22.dp, end = 22.dp, top = 56.dp, bottom = 44.dp),
        ) {
            ChmabaLogo(onDark = true)
            Spacer(Modifier.height(20.dp))
            Text(
                text = title,
                color = Color.White,
                fontSize = 25.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = (-0.055).sp,
                lineHeight = 28.sp,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                text = subtitle,
                color = HeroMuted,
                fontSize = 12.5.sp,
                lineHeight = 20.sp,
                modifier = Modifier.width(280.dp),
            )
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .offset(y = (-18).dp)
                .clip(RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp))
                .background(ChmabaSurface)
                .verticalScroll(rememberScrollState())
                .padding(start = 22.dp, end = 22.dp, top = 24.dp, bottom = 28.dp),
            content = content,
        )
    }
}

/** "or continue with" rule. */
@Composable
fun OrDivider(text: String = "or continue with") {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .weight(1f)
                .height(1.dp)
                .background(ChmabaGray300),
        )
        Text(
            text = text,
            color = ChmabaGray400,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 11.dp),
        )
        Box(
            Modifier
                .weight(1f)
                .height(1.dp)
                .background(ChmabaGray300),
        )
    }
}

/** Google's four-colour mark, at true brand colours. */
@Composable
fun GoogleMark(size: Int = 17) {
    Icon(
        imageVector = GoogleG,
        contentDescription = null,
        tint = Color.Unspecified,
        modifier = Modifier.size(size.dp),
    )
}

private val GoogleG: ImageVector = ImageVector.Builder(
    name = "googleG",
    defaultWidth = 48.dp,
    defaultHeight = 48.dp,
    viewportWidth = 48f,
    viewportHeight = 48f,
).apply {
    addPath(
        pathData = addPathNodes("M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.6 2.6 30.2 0 24 0 14.6 0 6.5 5.4 2.5 13.2l7.8 6.1C12.2 13.2 17.6 9.5 24 9.5z"),
        fill = SolidColor(Color(0xFFEA4335)),
    )
    addPath(
        pathData = addPathNodes("M46.5 24.5c0-1.6-.1-2.8-.4-4.1H24v8.4h12.7c-.3 2.2-1.6 5.4-4.6 7.6l7.6 5.9c4.4-4.1 7-10.1 7-17.8z"),
        fill = SolidColor(Color(0xFF4285F4)),
    )
    addPath(
        pathData = addPathNodes("M10.3 28.7c-.5-1.5-.8-3-.8-4.7s.3-3.2.8-4.7l-7.8-6.1C.9 16.4 0 20.1 0 24s.9 7.6 2.5 10.8l7.8-6.1z"),
        fill = SolidColor(Color(0xFFFBBC05)),
    )
    addPath(
        pathData = addPathNodes("M24 48c6.5 0 11.9-2.1 15.8-5.8l-7.6-5.9c-2.1 1.4-4.9 2.4-8.2 2.4-6.4 0-11.8-3.7-13.7-9.1l-7.8 6.1C6.5 42.6 14.6 48 24 48z"),
        fill = SolidColor(Color(0xFF34A853)),
    )
}.build()

@Composable
fun GoogleButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    ChmabaButton(
        onClick = onClick,
        text = text,
        modifier = modifier.fillMaxWidth(),
        variant = ButtonVariant.Outline,
        size = ButtonSize.Large,
        leadingIcon = { GoogleMark() },
    )
}

/** Bottom-of-screen link line, e.g. "New to Chmaba? Create an account". */
@Composable
fun AuthSwap(lead: String, action: String, onAction: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 20.dp),
        horizontalArrangement = Arrangement.Center,
    ) {
        Text(lead, color = ChmabaGray500, fontSize = 12.5.sp)
        Spacer(Modifier.width(5.dp))
        Text(
            text = action,
            color = ChmabaBlue,
            fontSize = 12.5.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.clickable(onClick = onAction),
        )
    }
}

@Composable
fun AuthNote(text: String) {
    Text(
        text = text,
        color = ChmabaGray400,
        fontSize = 10.5.sp,
        textAlign = TextAlign.Center,
        lineHeight = 16.sp,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 16.dp),
    )
}

/** Password field with a show/hide affordance, matching the web Field. */
@Composable
fun PasswordField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    hint: String? = null,
    imeAction: ImeAction = ImeAction.Done,
) {
    var visible by remember { mutableStateOf(false) }
    Column(modifier) {
        ChmabaTextField(
            value = value,
            onValueChange = onValueChange,
            label = label,
            placeholder = "••••••••",
            visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = imeAction),
            trailingIcon = {
                Icon(
                    imageVector = if (visible) ChmabaIcons.EyeOff else ChmabaIcons.Eye,
                    contentDescription = if (visible) "Hide password" else "Show password",
                    tint = ChmabaGray400,
                    modifier = Modifier
                        .size(20.dp)
                        .clickable { visible = !visible },
                )
            },
        )
        if (hint != null) {
            Text(
                text = hint,
                color = ChmabaGray400,
                fontSize = 10.5.sp,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }
}

/**
 * Six-box one-time-code field.
 *
 * The code is offered by Android itself (Autofill / Gmail suggestion strip above
 * the keyboard) — the app deliberately draws NO "autofill" button, matching the
 * prototype. To receive the suggestion, mark the field with the platform OTP
 * autofill hint; see the TODO below.
 */
@Composable
fun OtpField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val focusRequesters = remember { List(6) { FocusRequester() } }
    val digits = remember(value) { value.padEnd(6, ' ').take(6).toList() }

    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        digits.forEachIndexed { index, char ->
            val isFocusedBox = char != ' ' && index == value.length.coerceAtMost(5)
            OutlinedTextField(
                value = if (char == ' ') "" else char.toString(),
                onValueChange = { input ->
                    val cleaned = input.filter { it.isDigit() }.take(1)
                    val next = value.toMutableList()
                    while (next.size < 6) next.add(' ')
                    next[index] = cleaned.firstOrNull() ?: ' '
                    onValueChange(String(next.toCharArray()).trimEnd())
                    if (cleaned.isNotEmpty() && index < 5) {
                        focusRequesters[index + 1].requestFocus()
                    }
                },
                modifier = Modifier
                    .weight(1f)
                    .focusRequester(focusRequesters[index])
                    // TODO(autofill): Compose 1.7+ exposes
                    //   Modifier.semantics { contentType = ContentType.SmsOtp }
                    // which is what surfaces the system "From Gmail 428•••" chip.
                    // On this BOM use an AndroidView EditText with
                    //   autofillHints = AUTOFILL_HINT_SMS_OTP
                    // so the suggestion appears above the keyboard.
                    ,
                singleLine = true,
                textStyle = MaterialTheme.typography.titleMedium.copy(
                    textAlign = TextAlign.Center,
                    fontWeight = FontWeight.ExtraBold,
                ),
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.NumberPassword,
                    imeAction = ImeAction.Next,
                ),
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = ChmabaViolet,
                    unfocusedBorderColor = ChmabaGray300,
                    focusedContainerColor = ChmabaSurface,
                    unfocusedContainerColor = ChmabaSurface,
                    cursorColor = ChmabaBlue,
                    focusedTextColor = if (isFocusedBox) ChmabaBlue else ChmabaGray900,
                    unfocusedTextColor = ChmabaGray900,
                ),
            )
        }
    }
}

@Composable
fun VerifyBadge() {
    Box(
        modifier = Modifier
            .size(42.dp)
            .clip(RoundedCornerShape(14.dp))
            .background(ChmabaGreen.copy(alpha = 0.12f)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = ChmabaIcons.Mail,
            contentDescription = null,
            tint = ChmabaGreen,
            modifier = Modifier.size(20.dp),
        )
    }
}
