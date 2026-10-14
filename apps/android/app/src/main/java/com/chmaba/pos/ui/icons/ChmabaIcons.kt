package com.chmaba.pos.ui.icons

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp

/**
 * Icon set with Lucide parity.
 *
 * The web app (apps/web) draws every icon from Lucide — 24x24, stroke width 2,
 * round caps and joins. Material Symbols look noticeably different (heavier,
 * different geometry), so Android uses the *same path data* as the web to keep
 * the two products visually identical.
 *
 * Paths are the exact strings already used by the prototype (see
 * apps/android/prototype/icons.js) so the prototype and the app cannot drift.
 */
private fun lucide(name: String, vararg paths: String): ImageVector {
    val builder = ImageVector.Builder(
        name = name,
        defaultWidth = 24.dp,
        defaultHeight = 24.dp,
        viewportWidth = 24f,
        viewportHeight = 24f,
    )
    paths.forEach { d ->
        builder.addPath(
            pathData = addPathNodes(d),
            fill = null,
            stroke = SolidColor(Color.Black),
            strokeLineWidth = 2f,
            strokeLineCap = StrokeCap.Round,
            strokeLineJoin = StrokeJoin.Round,
        )
    }
    return builder.build()
}

object ChmabaIcons {
    // --- navigation ---
    val Home = lucide("home", "M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z")
    val Cart = lucide(
        "cart",
        "M10.4 20a1.4 1.4 0 1 1-2.8 0 1.4 1.4 0 0 1 2.8 0z",
        "M20.4 20a1.4 1.4 0 1 1-2.8 0 1.4 1.4 0 0 1 2.8 0z",
        "M2 3h2.2l2.4 12.2a2 2 0 0 0 2 1.6h9.6a2 2 0 0 0 2-1.6L21 7H5.6",
    )
    val Receipt = lucide(
        "receipt",
        "M5 2h14v20l-3-2-2 2-2-2-2 2-3-2z",
        "M9 7h6M9 11h6M9 15h4",
    )
    val More = lucide(
        "more",
        "M13.4 12a1.4 1.4 0 1 1-2.8 0 1.4 1.4 0 0 1 2.8 0z",
        "M20.4 12a1.4 1.4 0 1 1-2.8 0 1.4 1.4 0 0 1 2.8 0z",
        "M6.4 12a1.4 1.4 0 1 1-2.8 0 1.4 1.4 0 0 1 2.8 0z",
    )
    val Menu = lucide("menu", "M4 6h16M4 12h16M4 18h16")
    val Sliders = lucide(
        "sliders",
        "M3 6h9M16 6h5M3 12h5M12 12h9M3 18h13M20 18h1",
        "M16 6a2 2 0 1 1-4 0 2 2 0 0 1 4 0z",
        "M11 12a2 2 0 1 1-4 0 2 2 0 0 1 4 0z",
        "M20 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0z",
    )

    // --- search / capture ---
    val Search = lucide(
        "search",
        "M18 11a7 7 0 1 1-14 0 7 7 0 0 1 14 0z",
        "M20.5 20.5 16.7 16.7",
    )
    val Scan = lucide(
        "scan",
        "M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2M7 12h10",
    )
    val Camera = lucide(
        "camera",
        "M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z",
        "M15 13a3 3 0 1 1-6 0 3 3 0 0 1 6 0z",
    )

    // --- actions ---
    val Plus = lucide("plus", "M12 5v14M5 12h14")
    val Minus = lucide("minus", "M5 12h14")
    val Close = lucide("close", "M6 6l12 12M18 6 6 18")
    val Check = lucide("check", "M20 6 9 17l-5-5")
    val ChevronRight = lucide("chevronRight", "M9 6l6 6-6 6")
    val ChevronLeft = lucide("chevronLeft", "M15 6l-6 6 6 6")
    val ChevronDown = lucide("chevronDown", "M6 9l6 6 6-6")
    val ArrowRight = lucide("arrowRight", "M5 12h14M13 6l6 6-6 6")
    val ArrowUpRight = lucide("arrowUpRight", "M7 17 17 7M9 7h8v8")
    val Refresh = lucide("refresh", "M21 12a9 9 0 1 1-2.6-6.4", "M21 4v5h-5")
    val Download = lucide("download", "M12 3v12M7 10l5 5 5-5M4 21h16")
    val Upload = lucide("upload", "M12 21V9M7 14l5-5 5 5M4 3h16")
    val Pencil = lucide("pencil", "M12 20h9", "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z")
    val Trash = lucide("trash", "M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14")
    val Copy = lucide("copy", "M11 9h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H11a2 2 0 0 1-2-2V11a2 2 0 0 1 2-2z", "M5 15V5a2 2 0 0 1 2-2h10")
    val Share = lucide("share", "M12 3v12M8 7l4-4 4 4", "M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5")
    val Undo = lucide("undo", "M3 12a9 9 0 1 0 3-6.7", "M3 4v5h5")
    val Filter = lucide("filter", "M3 5h18l-7 8v6l-4-2v-4z")
    val Percent = lucide("percent", "M19 5 5 19", "M9 6.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z", "M20 17.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z")

    // --- people ---
    val User = lucide("user", "M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0z", "M4 21a8 8 0 0 1 16 0")
    val UserPlus = lucide(
        "userPlus",
        "M13 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0z",
        "M2 21a7 7 0 0 1 12-4.9",
        "M19 8v6M16 11h6",
    )
    val Users = lucide(
        "users",
        "M13 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0z",
        "M2 21a7 7 0 0 1 14 0",
        "M17 4a4 4 0 0 1 0 8M22 21a6 6 0 0 0-4.5-5.8",
    )

    // --- commerce ---
    val Qr = lucide(
        "qr",
        "M4 3h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z",
        "M15 3h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z",
        "M4 14h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1z",
        "M14 14h3v3h-3zM19 14h2M14 19h2M19 19h2",
    )
    val Banknote = lucide(
        "banknote",
        "M4 6h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z",
        "M14.4 12a2.4 2.4 0 1 1-4.8 0 2.4 2.4 0 0 1 4.8 0z",
        "M6 12h.01M18 12h.01",
    )
    val Printer = lucide(
        "printer",
        "M6 9V3h12v6",
        "M6 18H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-1",
        "M9 14h6a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-5a1 1 0 0 1 1-1z",
    )
    val CreditCard = lucide("creditCard", "M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z", "M2 10h20")
    val Dollar = lucide(
        "dollar",
        "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
        "M12 7v10",
        "M15 9.5A3 3 0 0 0 12 8c-1.7 0-3 .9-3 2s1.3 1.7 3 2 3 .9 3 2-1.3 2-3 2a3 3 0 0 1-3-1.5",
    )
    val Tag = lucide("tag", "M20.6 13.4 12 22l-9-9V4h9z", "M8.8 7.5a1.3 1.3 0 1 1-2.6 0 1.3 1.3 0 0 1 2.6 0z")
    val Truck = lucide(
        "truck",
        "M3 7h11v9H3z",
        "M14 10h4l3 3v3h-7z",
        "M8.7 18a1.7 1.7 0 1 1-3.4 0 1.7 1.7 0 0 1 3.4 0z",
        "M19.2 18a1.7 1.7 0 1 1-3.4 0 1.7 1.7 0 0 1 3.4 0z",
    )
    val Store = lucide("store", "M3 9l1.6-5h14.8L21 9", "M4 9v11h16V9", "M9 20v-6h6v6")
    val Package = lucide("package", "M21 8 12 3 3 8v8l9 5 9-5z", "M3 8l9 5 9-5M12 13v8")
    val Archive = lucide("archive", "M4 4h16a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z", "M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8", "M10 12h4")
    val Boxes = lucide("boxes", "M3 8.5 7.5 6 12 8.5V14l-4.5 2.5L3 14z", "M12 8.5 16.5 6 21 8.5V14l-4.5 2.5L12 14z")
    val BarChart = lucide("barChart", "M3 21h18", "M7 21v-8M12 21V6M17 21v-12")
    val Wallet = lucide("wallet", "M5 6h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z", "M16 12h4", "M3 8l9-4 9 4")
    val Layers = lucide("layers", "M12 3l9 5-9 5-9-5z", "M3 13l9 5 9-5")
    val Coffee = lucide(
        "coffee",
        "M4 8h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5z",
        "M17 9h1.5a2.5 2.5 0 0 1 0 5H17",
        "M6 3v2M10 3v2M14 3v2",
    )
    val Utensils = lucide(
        "utensils",
        "M5 3v7a2 2 0 0 0 4 0V3",
        "M7 10v11",
        "M16.5 3c-1.4 1.7-2 3.2-2 4.8 0 1.4.8 2.4 2 2.4s2-1 2-2.4c0-1.6-.6-3.1-2-4.8z",
        "M16.5 10.2V21",
    )
    val Smartphone = lucide(
        "smartphone",
        "M8 2h8a2.5 2.5 0 0 1 2.5 2.5v15A2.5 2.5 0 0 1 16 22H8a2.5 2.5 0 0 1-2.5-2.5v-15A2.5 2.5 0 0 1 8 2z",
        "M11 18h2",
    )
    val Phone = lucide("phone", "M6 3h3l2 5-2.5 1.5a12 12 0 0 0 5 5L15 12l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 4 5a2 2 0 0 1 2-2z")
    val Monitor = lucide("monitor", "M4 4h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z", "M8 20h8M12 16v4")
    val Calendar = lucide("calendar", "M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z", "M8 3v4M16 3v4M3 11h18")
    val Image = lucide(
        "image",
        "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z",
        "M10 8.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z",
        "M21 15l-5-5L5 21",
    )
    val Clock = lucide("clock", "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z", "M12 7v5l3 2")

    // --- account / security ---
    val Lock = lucide(
        "lock",
        "M6 10h12a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z",
        "M8 10V7a4 4 0 0 1 8 0v3",
        "M13.5 15.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z",
    )
    val Key = lucide("key", "M12 15a4 4 0 1 1-8 0 4 4 0 0 1 8 0z", "M11 12l8-8", "M17 4l3 3M14.5 6.5l2 2")
    val Mail = lucide(
        "mail",
        "M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z",
        "M3 7l9 6 9-6",
    )
    val Shield = lucide("shield", "M12 3l8 3v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z", "M9 12l2 2 4-4")
    val Eye = lucide("eye", "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z", "M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0z")
    val EyeOff = lucide(
        "eyeOff",
        "M3 3l18 18",
        "M10.6 6.3A9.7 9.7 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1",
        "M6.6 6.7A17 17 0 0 0 2 12s3.5 7 10 7a9.6 9.6 0 0 0 4.4-1",
        "M9.9 9.9a3 3 0 0 0 4.2 4.2",
    )

    // --- misc / status ---
    val Sparkles = lucide("sparkles", "M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8z", "M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z")
    val Bell = lucide("bell", "M6 9a6 6 0 1 1 12 0c0 5 2 6 2 6H4s2-1 2-6", "M10 20a2 2 0 0 0 4 0")
    val Message = lucide("message", "M21 11.5a8.4 8.4 0 0 1-12 7.5L3 21l2-5.4A8.4 8.4 0 1 1 21 11.5z")
    val Moon = lucide("moon", "M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z")
    val Alert = lucide("alert", "M12 3l9 16H3z", "M12 9v5M12 17h.01")
    val Party = lucide("party", "M3 21l6-14 8 8z", "M14 4l1 1M19 9l1 1M14.5 9.5 16 8M18 6l1.5-1.5M20 11l2-.5M11 3l.5-2")
    val Gift = lucide("gift", "M4 8h16a1 1 0 0 1 1 1v3H3V9a1 1 0 0 1 1-1z", "M5 12v8h14v-8M12 8v12", "M12 8S10 4 7.5 4a2 2 0 0 0 0 4M12 8s2-4 4.5-4a2 2 0 0 1 0 4")
    val CornerDownRight = lucide("cornerDownRight", "M15 10l5 5-5 5", "M4 4v7a4 4 0 0 0 4 4h12")
    val ArrowLeftRight = lucide("arrowLeftRight", "M8 7l-4 4 4 4M16 17l4-4-4-4M4 11h16")
    val Signal = lucide("signal", "M4 20v-4M9 20v-8M14 20v-12M19 20V4")
    val Wifi = lucide("wifi", "M2 8.5a15 15 0 0 1 20 0", "M5.5 12.5a10 10 0 0 1 13 0", "M9 16.5a5 5 0 0 1 6 0")
    val Battery = lucide("battery", "M4 8h13a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2z", "M21 11v2")
}
