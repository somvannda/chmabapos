package com.chmaba.pos.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaLime

/**
 * The chmaba brand mark: a chip holding two overlapping rings, optionally with
 * the wordmark. Mirrors `Logo` in apps/web/src/components/ui.jsx so the Android
 * app and the web app render the same shape.
 *
 * The chip is always the brand lime with dark rings (the `favicon-dark.svg`
 * treatment) so the mark matches the launcher icon. `onDark` only affects the
 * wordmark colour, for use over a dark hero.
 */
@Composable
fun ChmabaLogo(
    modifier: Modifier = Modifier,
    onDark: Boolean = false,
    wordmark: Boolean = true,
    chipSize: Dp = 32.dp,
    wordSize: Int = 19,
) {
    val chipColor = ChmabaLime
    val ringColor = ChmabaGray900
    val wordColor = if (onDark) Color.White else ChmabaGray900
    val k = chipSize.value / 32f

    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp * k),
    ) {
        Box(
            modifier = Modifier
                .size(chipSize)
                .clip(RoundedCornerShape(10.dp * k))
                .background(chipColor),
        ) {
            Box(
                modifier = Modifier
                    .offset(x = 6.dp * k, y = 9.dp * k)
                    .size(12.dp * k)
                    .border(2.5.dp * k, ringColor, CircleShape),
            )
            Box(
                modifier = Modifier
                    .offset(x = 19.dp * k, y = 6.dp * k)
                    .size(12.dp * k)
                    .border(2.5.dp * k, ringColor, CircleShape),
            )
        }
        if (wordmark) {
            Text(
                text = "chmaba",
                color = wordColor,
                fontSize = wordSize.sp,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = (-0.04).sp,
            )
        }
    }
}
