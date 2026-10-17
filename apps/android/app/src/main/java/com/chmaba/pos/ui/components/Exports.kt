package com.chmaba.pos.ui.components

import android.content.Intent
import androidx.core.content.FileProvider

/**
 * Writes a CSV into the app's own cache and hands it to the system share sheet.
 *
 * A share sheet needs no storage permission and lets the reader put the file wherever they
 * want - mail, Drive, Files - which writing to a fixed Downloads folder would not. The file
 * lives under cache/exports, cleared by the system rather than kept.
 *
 * Shared by the inventory and report exports so both behave the same way.
 */
fun shareCsv(context: android.content.Context, fileName: String, csv: String, subject: String) {
    val dir = java.io.File(context.cacheDir, "exports").apply { mkdirs() }
    val file = java.io.File(dir, fileName)
    file.writeText(csv)
    val uri = FileProvider.getUriForFile(context, context.packageName + ".fileprovider", file)
    val send = Intent(Intent.ACTION_SEND).apply {
        type = "text/csv"
        putExtra(Intent.EXTRA_STREAM, uri)
        putExtra(Intent.EXTRA_SUBJECT, subject)
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    context.startActivity(Intent.createChooser(send, subject))
}

/**
 * Hands text to the system share sheet.
 *
 * A receipt is the caller: the app cannot drive a printer, which would be a transport it does not
 * have, but a receipt does not need one - the reader can send it to a customer's phone, mail it, or
 * print it from whatever they share it to.
 */
fun shareText(context: android.content.Context, subject: String, text: String) {
    val send = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_SUBJECT, subject)
        putExtra(Intent.EXTRA_TEXT, text)
    }
    context.startActivity(Intent.createChooser(send, subject))
}
