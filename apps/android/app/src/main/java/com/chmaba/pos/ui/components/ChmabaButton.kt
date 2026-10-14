package com.chmaba.pos.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.chmaba.pos.ui.theme.*

/**
 * Chmaba Button Components
 * Matching web design from apps/web/src/components/ui.jsx
 */

@Composable
fun ChmabaButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    text: String,
    enabled: Boolean = true,
    variant: ButtonVariant = ButtonVariant.Primary,
    size: ButtonSize = ButtonSize.Medium,
    leadingIcon: @Composable (() -> Unit)? = null,
    trailingIcon: @Composable (() -> Unit)? = null
) {
    val colors = when (variant) {
        ButtonVariant.Primary -> ButtonDefaults.buttonColors(
            containerColor = ChmabaBlue,
            contentColor = Color.White
        )
        ButtonVariant.Outline -> ButtonDefaults.outlinedButtonColors(
            containerColor = Color.White,
            contentColor = ChmabaGray900
        )
        ButtonVariant.Soft -> ButtonDefaults.buttonColors(
            containerColor = ChmabaLavender,
            contentColor = ChmabaViolet
        )
        ButtonVariant.Ghost -> ButtonDefaults.textButtonColors(
            contentColor = ChmabaGray600
        )
        ButtonVariant.Danger -> ButtonDefaults.buttonColors(
            containerColor = Color(0xFFFFF0EE),
            contentColor = ChmabaRed
        )
        ButtonVariant.Lime -> ButtonDefaults.buttonColors(
            containerColor = ChmabaLime,
            contentColor = Color(0xFF1B2715)
        )
    }
    
    val height = when (size) {
        ButtonSize.Small -> 36.dp
        ButtonSize.Medium -> 40.dp
        ButtonSize.Large -> 48.dp
    }
    
    val fontSize = when (size) {
        ButtonSize.Small -> MaterialTheme.typography.labelMedium
        ButtonSize.Medium -> MaterialTheme.typography.labelLarge
        ButtonSize.Large -> MaterialTheme.typography.labelLarge
    }

    Button(
        onClick = onClick,
        modifier = modifier.height(height),
        enabled = enabled,
        colors = colors,
        shape = RoundedCornerShape(12.dp),
        contentPadding = PaddingValues(horizontal = 16.dp)
    ) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            leadingIcon?.invoke()
            Text(
                text = text,
                style = fontSize,
                fontWeight = FontWeight.SemiBold
            )
            trailingIcon?.invoke()
        }
    }
}

enum class ButtonVariant {
    Primary, Outline, Soft, Ghost, Danger, Lime
}

enum class ButtonSize {
    Small, Medium, Large
}
