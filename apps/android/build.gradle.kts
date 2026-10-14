// AGP 8.5.1+ aligns uncompressed native libraries to 16 KB page size, which is
// required for Android 15+ on 16 KB devices. Older AGP produced an APK that made
// Android show a "not 16 KB compatible" compatibility dialog over the app.
plugins {
    id("com.android.application") version "8.5.1" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
}
