package com.chmaba.pos.data.catalog

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The part the product image endpoint receives.
 *
 * Nothing else in the app builds a multipart body, so this pins the contract: the field must be
 * called "file" - FastAPI's `file: UploadFile = File(...)` reads that name - and it must carry both
 * a filename and a content type, because the server stores the image under one and serves it with
 * the other.
 */
class ProductImageTest {

    @Test
    fun thePartIsNamedFileAsTheEndpointExpects() {
        val part = productImagePart("latte.jpg", "image/jpeg", byteArrayOf(1, 2, 3))

        val disposition = part.headers?.get("Content-Disposition").orEmpty()
        assertTrue(disposition, disposition.contains("name=\"file\""))
        assertTrue(disposition, disposition.contains("filename=\"latte.jpg\""))
    }

    @Test
    fun theContentTypeTravelsWithIt() {
        val part = productImagePart("latte.png", "image/png", byteArrayOf(1))

        assertEquals("image/png", part.body.contentType().toString())
    }

    @Test
    fun aMissingNameOrTypeStillProducesSomethingTheServerWillTake() {
        // The picker can hand back a display name with no extension and a null type.
        val part = productImagePart("", "", byteArrayOf(9))

        val disposition = part.headers?.get("Content-Disposition").orEmpty()
        assertTrue(disposition, disposition.contains("filename=\"photo.jpg\""))
        assertEquals("image/jpeg", part.body.contentType().toString())
    }

    @Test
    fun theBytesAreTheBytes() {
        val bytes = byteArrayOf(10, 20, 30, 40)
        val part = productImagePart("x.jpg", "image/jpeg", bytes)

        val buffer = okio.Buffer()
        part.body.writeTo(buffer)
        assertEquals(4L, buffer.size)
        assertTrue(buffer.readByteArray().contentEquals(bytes))
    }
}
