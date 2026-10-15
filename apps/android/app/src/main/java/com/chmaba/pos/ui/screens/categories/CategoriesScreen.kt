package com.chmaba.pos.ui.screens.categories

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chmaba.pos.ui.components.BadgeTone
import com.chmaba.pos.ui.components.ButtonSize
import com.chmaba.pos.ui.components.ButtonVariant
import com.chmaba.pos.ui.components.ChmabaBadge
import com.chmaba.pos.ui.components.ChmabaButton
import com.chmaba.pos.ui.components.ChmabaTextField
import com.chmaba.pos.ui.icons.ChmabaIcons
import com.chmaba.pos.ui.theme.ChmabaBlue
import com.chmaba.pos.ui.theme.ChmabaGray400
import com.chmaba.pos.ui.theme.ChmabaGray500
import com.chmaba.pos.ui.theme.ChmabaGray900
import com.chmaba.pos.ui.theme.ChmabaLavender
import com.chmaba.pos.ui.theme.ChmabaRed
import com.chmaba.pos.ui.theme.ChmabaSurface

private val CategoriesBg = Color(0xFFF7F7FA)
private val RowDivider = Color(0xFFF2F2F5)
private val LimeSoft = Color(0xFFEFF9E6)
private val GraySoft = Color(0xFFF1F1F5)

/**
 * A category or subcategory. Mirrors the web categories page: a parent/child
 * tree with product counts and an active flag. Placeholder data until the
 * categories endpoint is wired.
 */
data class Category(
    val name: String,
    val parent: String? = null,
    val productCount: Int,
    val isActive: Boolean = true,
    /** UUID; lets the product editor resolve a category name back to its id. */
    val id: String = "",
) {
    val isSubcategory: Boolean get() = parent != null
    val displayName: String get() = if (parent != null) "$parent › $name" else name
}

/**
 * Shared by Add and Rename: they differ only in the wording and the starting value,
 * so one form serves both rather than two near-identical dialogs.
 */
@Composable
private fun CategoryDialog(
    title: String,
    label: String,
    initial: String,
    saving: Boolean,
    error: String?,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit,
) {
    var name by remember { mutableStateOf(initial) }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = ChmabaSurface,
        title = {
            Text(title, color = ChmabaGray900, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
        },
        text = {
            Column {
                ChmabaTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = label,
                )
                if (error != null) {
                    Spacer(Modifier.height(10.dp))
                    Text(error, color = ChmabaRed, fontSize = 11.sp, lineHeight = 15.sp)
                }
            }
        },
        confirmButton = {
            ChmabaButton(
                onClick = { onSave(name) },
                text = if (saving) "Saving…" else "Save",
                enabled = name.isNotBlank() && !saving,
                variant = ButtonVariant.Primary,
                size = ButtonSize.Small,
            )
        },
        dismissButton = {
            ChmabaButton(
                onClick = onDismiss,
                text = "Cancel",
                variant = ButtonVariant.Ghost,
                size = ButtonSize.Small,
            )
        },
    )
}

@Composable
fun CategoriesScreen(
    modifier: Modifier = Modifier,
    viewModel: com.chmaba.pos.ui.screens.store.CategoriesViewModel =
        androidx.lifecycle.viewmodel.compose.viewModel(),
) {
    // Which dialog is open; each form owns its own field value.
    var adding by remember { mutableStateOf(false) }
    var renaming by remember { mutableStateOf<Category?>(null) }

    if (adding) {
        CategoryDialog(
            title = "Add category",
            label = "Name",
            initial = "",
            saving = viewModel.saving,
            error = viewModel.error,
            onDismiss = {
                viewModel.clearError()
                adding = false
            },
            onSave = { name -> viewModel.create(name) { adding = false } },
        )
    }

    renaming?.let { category ->
        CategoryDialog(
            title = "Rename category",
            label = "Name",
            initial = category.name,
            saving = viewModel.saving,
            error = viewModel.error,
            onDismiss = {
                viewModel.clearError()
                renaming = null
            },
            onSave = { name -> viewModel.rename(category.id, name) { renaming = null } },
        )
    }
    val categories = (viewModel.state as? com.chmaba.pos.data.store.LoadState.Ready)?.data.orEmpty()
    val parents = categories.filter { !it.isSubcategory }
    val subs = categories.filter { it.isSubcategory }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(CategoriesBg)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    "Categories",
                    color = ChmabaGray900,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = (-0.05).sp,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    "Organize products into categories and subcategories.",
                    color = ChmabaGray500,
                    fontSize = 12.5.sp,
                    lineHeight = 18.sp,
                )
            }
            ChmabaButton(
                onClick = { adding = true },
                text = "Add",
                variant = ButtonVariant.Primary,
                size = ButtonSize.Small,
                leadingIcon = {
                    Icon(ChmabaIcons.Plus, contentDescription = null, tint = Color.White, modifier = Modifier.size(14.dp))
                },
            )
        }

        Spacer(Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            MiniStat("Categories", categories.size.toString(), ChmabaLavender, Modifier.weight(1f))
            MiniStat("Top-level", parents.size.toString(), LimeSoft, Modifier.weight(1f))
            MiniStat("Subcategories", subs.size.toString(), GraySoft, Modifier.weight(1f))
        }

        Spacer(Modifier.height(14.dp))

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(16.dp))
                .background(ChmabaSurface),
        ) {
            com.chmaba.pos.ui.components.LoadStateNotice(
                state = viewModel.state,
                loadingMessage = "Loading categories…",
                failedTitle = "Could not load categories",
                onRetry = { viewModel.load() },
            )
            if (categories.isEmpty() && viewModel.state is com.chmaba.pos.data.store.LoadState.Ready) {
                Text(
                    "No categories yet.",
                    color = ChmabaGray400,
                    fontSize = 12.sp,
                    modifier = Modifier.padding(20.dp),
                )
            }
            categories.forEachIndexed { index, category ->
                if (index > 0) {
                    Box(Modifier.fillMaxWidth().height(1.dp).background(RowDivider))
                }
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { renaming = category }
                        .padding(horizontal = 16.dp, vertical = 13.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        modifier = Modifier
                            .size(34.dp)
                            .clip(RoundedCornerShape(11.dp))
                            .background(if (category.isSubcategory) GraySoft else ChmabaLavender),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(
                            imageVector = if (category.isSubcategory) ChmabaIcons.CornerDownRight else ChmabaIcons.Tag,
                            contentDescription = null,
                            tint = if (category.isSubcategory) ChmabaGray500 else ChmabaBlue,
                            modifier = Modifier.size(17.dp),
                        )
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            category.displayName,
                            color = ChmabaGray900,
                            fontSize = 12.5.sp,
                            fontWeight = FontWeight.Bold,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            // CategoryRead carries no product count, so none is shown.
                            if (category.isSubcategory) "Subcategory" else "Category",
                            color = ChmabaGray400,
                            fontSize = 10.sp,
                        )
                    }
                    ChmabaBadge(
                        text = if (category.isActive) "Active" else "Inactive",
                        tone = if (category.isActive) BadgeTone.Green else BadgeTone.Neutral,
                    )
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun MiniStat(label: String, value: String, background: Color, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(background)
            .padding(11.dp),
    ) {
        Text(
            label.uppercase(),
            color = ChmabaGray500,
            fontSize = 8.sp,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.6.sp,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            value,
            color = ChmabaGray900,
            fontSize = 18.sp,
            fontWeight = FontWeight.ExtraBold,
            letterSpacing = (-0.05).sp,
        )
    }
}
