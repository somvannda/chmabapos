package com.chmaba.pos.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.theme.*

/**
 * Chmaba Badge Component
 * Matching web design badge styles
 */

@Composable
fun ChmabaBadge(
    text: String,
    tone: BadgeTone = BadgeTone.Neutral,
    showDot: Boolean = false,
    modifier: Modifier = Modifier
) {
    val (backgroundColor, textColor, dotColor) = when (tone) {
        BadgeTone.Neutral -> Triple(
            Color(0xFFF1F1F5),
            Color(0xFF686974),
            Color(0xFF9899A4)
        )
        BadgeTone.Green -> Triple(
            Color(0xFFEDF9E4),
            Color(0xFF4F8B32),
            Color(0xFF77BB4B)
        )
        BadgeTone.Yellow -> Triple(
            Color(0xFFFFF6DF),
            Color(0xFFAD7D1C),
            Color(0xFFDCA93C)
        )
        BadgeTone.Red -> Triple(
            Color(0xFFFFF0EE),
            Color(0xFFC2564B),
            Color(0xFFDC6B60)
        )
        BadgeTone.Violet -> Triple(
            ChmabaLavender,
            Color(0xFF6555DF),
            Color(0xFF7969EC)
        )
        BadgeTone.Blue -> Triple(
            Color(0xFFEAF4FF),
            Color(0xFF3579B8),
            Color(0xFF63A2D8)
        )
    }

    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(6.dp),
        color = backgroundColor
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (showDot) {
                Box(
                    modifier = Modifier
                        .size(6.dp)
                        .background(dotColor, shape = RoundedCornerShape(3.dp))
                )
            }
            
            Text(
                text = text,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.SemiBold,
                color = textColor,
                fontSize = 11.sp
            )
        }
    }
}

enum class BadgeTone {
    Neutral, Green, Yellow, Red, Violet, Blue
}

/**
 * Status Badge for Orders
 */
@Composable
fun StatusBadge(
    status: OrderStatus,
    modifier: Modifier = Modifier
) {
    val (text, tone) = when (status) {
        OrderStatus.Paid -> "Paid" to BadgeTone.Green
        OrderStatus.Pending -> "Pending" to BadgeTone.Yellow
        OrderStatus.Pickup -> "Pickup" to BadgeTone.Violet
        OrderStatus.Failed -> "Failed" to BadgeTone.Red
        OrderStatus.Cancelled -> "Cancelled" to BadgeTone.Neutral
        OrderStatus.Refunded -> "Refunded" to BadgeTone.Violet
    }

    ChmabaBadge(
        text = text,
        tone = tone,
        showDot = true,
        modifier = modifier
    )
}

/** Mirrors the web's order status tones (sales.jsx LiveOrdersWithReceipt). */
enum class OrderStatus {
    Paid, Pending, Pickup, Failed, Cancelled, Refunded
}
