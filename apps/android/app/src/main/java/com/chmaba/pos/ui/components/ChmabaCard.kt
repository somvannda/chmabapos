package com.chmaba.pos.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.theme.*

/**
 * Chmaba Card Component
 * Matching web design cards with rounded corners and shadows
 */

@Composable
fun ChmabaCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = ChmabaSurface
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = 2.dp
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            content = content
        )
    }
}

/**
 * Product Card for POS Grid
 */
@Composable
fun ProductCard(
    name: String,
    price: String,
    imageUrl: String?,
    stock: Int,
    color: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        onClick = onClick,
        modifier = modifier
            .width(140.dp)
            .height(180.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = ChmabaSurface
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = 1.dp,
            pressedElevation = 4.dp
        )
    ) {
        Column(
            modifier = Modifier.fillMaxSize()
        ) {
            // Product image or color placeholder
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(100.dp)
                    .background(color, RoundedCornerShape(topStart = 12.dp, topEnd = 12.dp))
            ) {
                // TODO: Load actual image with Coil
            }
            
            // Product details
            Column(
                modifier = Modifier.padding(12.dp)
            ) {
                Text(
                    text = name,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Bold,
                    color = ChmabaGray800,
                    maxLines = 2
                )
                
                Spacer(modifier = Modifier.height(4.dp))
                
                Text(
                    text = price,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.ExtraBold,
                    color = ChmabaGray900,
                    fontSize = 14.sp
                )
                
                if (stock <= 10) {
                    Text(
                        text = "$stock left",
                        style = MaterialTheme.typography.labelSmall,
                        color = ChmabaOrange,
                        fontSize = 9.sp
                    )
                }
            }
        }
    }
}

/**
 * Stat Card for Dashboard
 */
@Composable
fun StatCard(
    label: String,
    value: String,
    detail: String,
    tone: StatTone = StatTone.Violet,
    modifier: Modifier = Modifier
) {
    val backgroundColor = when (tone) {
        StatTone.Violet -> ChmabaLavender
        StatTone.Green -> ChmabaLimeLight
        StatTone.Yellow -> Color(0xFFFFF6DF)
        StatTone.Red -> ChmabaPeach
    }

    Card(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = backgroundColor
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = ChmabaGray600
            )
            
            Text(
                text = value,
                style = MaterialTheme.typography.displayLarge,
                fontWeight = FontWeight.ExtraBold,
                modifier = Modifier.padding(vertical = 8.dp)
            )
            
            Text(
                text = detail,
                style = MaterialTheme.typography.labelSmall,
                color = ChmabaGray500
            )
        }
    }
}

enum class StatTone {
    Violet, Green, Yellow, Red
}
