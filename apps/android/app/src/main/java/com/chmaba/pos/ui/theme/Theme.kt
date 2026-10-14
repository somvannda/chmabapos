package com.chmaba.pos.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val LightColorScheme = lightColorScheme(
    primary = ChmabaBlue,
    onPrimary = ChmabaSurface,
    secondary = ChmabaLime,
    onSecondary = ChmabaGray900,
    tertiary = ChmabaViolet,
    error = ChmabaRed,
    background = ChmabaBackground,
    onBackground = ChmabaOnBackground,
    surface = ChmabaSurface,
    onSurface = ChmabaOnSurface,
    surfaceVariant = ChmabaGray100,
    onSurfaceVariant = ChmabaGray700,
    outline = ChmabaGray300,
    outlineVariant = ChmabaGray200
)

private val DarkColorScheme = darkColorScheme(
    primary = ChmabaBlue,
    onPrimary = ChmabaSurface,
    secondary = ChmabaLime,
    onSecondary = ChmabaGray900,
    tertiary = ChmabaViolet,
    error = ChmabaRed,
    background = ChmabaDarkBackground,
    onBackground = ChmabaDarkOnSurface,
    surface = ChmabaDarkSurface,
    onSurface = ChmabaDarkOnSurface,
    surfaceVariant = Color(0xFF2A2B30),
    onSurfaceVariant = ChmabaGray400,
    outline = Color(0xFF363740),
    outlineVariant = Color(0xFF2A2B30)
)

@Composable
fun ChmabaTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme
    
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = ChmabaTypography,
        content = content
    )
}
