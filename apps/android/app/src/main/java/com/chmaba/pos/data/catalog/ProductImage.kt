package com.chmaba.pos.data.catalog

import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * The multipart part `POST /products/{id}/image` expects.
 *
 * The endpoint takes a single `file: UploadFile = File(...)` field, so the part must be named
 * "file" and carry a filename and a content type - FastAPI reads both. Kept as a named function
 * because the part's headers are the whole contract here and are worth a test: nothing else in the
 * app builds one.
 *
 * The bytes are passed in rather than read here: reading them needs an Android ContentResolver, and
 * this stays a plain JVM function so a unit test can hold it.
 */
fun productImagePart(filename: String, mimeType: String, bytes: ByteArray): MultipartBody.Part {
    val safeName = filename.ifBlank { "photo.jpg" }
    val type = mimeType.ifBlank { "image/jpeg" }
    return MultipartBody.Part.createFormData(
        "file",
        safeName,
        bytes.toRequestBody(type.toMediaTypeOrNull()),
    )
}
