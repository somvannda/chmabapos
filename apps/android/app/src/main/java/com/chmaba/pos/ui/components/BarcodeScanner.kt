package com.chmaba.pos.ui.components

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

/**
 * Barcode scanning, delegated to the device's camera app.
 *
 * Returns a lambda that opens a full-screen scanner and calls [onScanned] with
 * the decoded value. This deliberately keeps **no native libraries** in the app:
 * CameraX shipped `libimage_processing_util_jni.so` / `libsurface_util_jni.so`
 * with 4 KB LOAD segments, and ML Kit shipped `libbarhopper_v3.so`, all of which
 * made Android show a "not 16 KB compatible" dialog over the whole app on 16 KB
 * devices. zxing-android-embedded is pure Java and borrows the system camera.
 */
@Composable
fun rememberBarcodeScannerLauncher(onScanned: (String) -> Unit): () -> Unit {
    val launcher = rememberLauncherForActivityResult(ScanContract()) { result ->
        val contents = result.contents
        if (!contents.isNullOrBlank()) onScanned(contents)
    }
    return remember(launcher) {
        {
            launcher.launch(
                ScanOptions()
                    .setDesiredBarcodeFormats(ScanOptions.ALL_CODE_TYPES)
                    .setPrompt("Scan a product barcode")
                    .setBeepEnabled(true)
                    .setOrientationLocked(false),
            )
        }
    }
}
