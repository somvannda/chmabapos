// Images a merchant chooses come straight off a phone or a camera: several megabytes,
// and thousands of pixels on a side, for something the storefront paints at a few
// hundred. Re-encoding in the browser before upload keeps every request small and fast
// and comfortably inside the API's limit, so the size rule stops being something a
// merchant has to know about - and a normal photo of a shopfront just works.
//
// The pure helpers are separated out because they are the part worth testing under
// node --test; the canvas work below cannot run there.

/** Mirrors MAX_IMAGE_BYTES in chmabapos_api/app/media.py. */
export const MAX_UPLOAD_BYTES = 5_000_000;

/** Longest side kept after resizing, per surface: a cover is wide, a logo is small. */
export const MAX_EDGE = { logo: 512, cover: 1600 };

// A file already this small is left untouched, so a well-sized logo keeps its crisp
// pixels instead of being re-encoded for no gain.
const ALREADY_SMALL_BYTES = 1_000_000;

/** Scale so the longest side is at most `maxEdge`, never enlarging a smaller image. */
export function scaledDimensions(width, height, maxEdge) {
  const wide = Math.max(0, Math.round(Number(width) || 0));
  const tall = Math.max(0, Math.round(Number(height) || 0));
  const edge = Math.max(1, Math.round(Number(maxEdge) || 0));
  const longest = Math.max(wide, tall);
  if (!longest || longest <= edge) return { width: wide, height: tall };
  const factor = edge / longest;
  return { width: Math.max(1, Math.round(wide * factor)), height: Math.max(1, Math.round(tall * factor)) };
}

/** Whether the image is worth re-encoding: either too many pixels, or too many bytes. */
export function shouldShrink({ bytes = 0, width = 0, height = 0 } = {}, maxEdge, { byteThreshold = ALREADY_SMALL_BYTES } = {}) {
  if (Math.max(Number(width) || 0, Number(height) || 0) > (Number(maxEdge) || 0)) return true;
  return (Number(bytes) || 0) > byteThreshold;
}

// PNG and WebP keep their type so a logo's transparency survives; everything else
// becomes JPEG, which is an order of magnitude smaller at photo sizes. The caller
// skips GIF, whose animation re-encoding would destroy.
export function outputTypeFor(mime) {
  if (mime === "image/png") return "image/png";
  if (mime === "image/webp") return "image/webp";
  return "image/jpeg";
}

/** The API validates by filename suffix, so the name must describe the bytes we send. */
export function outputNameFor(name, type) {
  const stem = String(name || "image").replace(/\.[^./\\]+$/, "") || "image";
  const suffix = type === "image/png" ? "png" : type === "image/webp" ? "webp" : "jpg";
  return `${stem}.${suffix}`;
}

function toBlob(canvas, type, quality) {
  return new Promise((resolve) => canvas.toBlob(resolve, type, quality));
}

function loadImage(file) {
  if (typeof createImageBitmap === "function") return createImageBitmap(file);
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
    image.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Could not read the image")); };
    image.src = url;
  });
}

/**
 * A File ready to upload: the same picture, resized and re-encoded so it fits the API's
 * limit. Any failure - an unreadable file, a browser that cannot re-encode - returns the
 * original, so the upload still happens and the API's own message is what the merchant
 * sees, rather than a silent dead end.
 */
export async function shrinkForUpload(file, { surface = "cover", quality = 0.85 } = {}) {
  if (!file || !file.type || !file.type.startsWith("image/") || file.type === "image/gif") return file;
  const maxEdge = MAX_EDGE[surface] || MAX_EDGE.cover;
  try {
    const bitmap = await loadImage(file);
    const { width, height } = bitmap;
    if (!shouldShrink({ bytes: file.size, width, height }, maxEdge)) return file;
    const target = scaledDimensions(width, height, maxEdge);
    const canvas = document.createElement("canvas");
    canvas.width = target.width;
    canvas.height = target.height;
    const context = canvas.getContext("2d");
    if (!context) return file;
    let type = outputTypeFor(file.type);
    // JPEG has no alpha channel, so paint white first rather than letting a transparent
    // logo come out on black.
    if (type === "image/jpeg") { context.fillStyle = "#fff"; context.fillRect(0, 0, target.width, target.height); }
    context.drawImage(bitmap, 0, 0, target.width, target.height);
    if (typeof bitmap.close === "function") bitmap.close();
    let blob = await toBlob(canvas, type, quality);
    // A large PNG can still exceed the limit once resized; JPEG always gets there.
    if (blob && blob.size > MAX_UPLOAD_BYTES && type !== "image/jpeg") {
      type = "image/jpeg";
      blob = await toBlob(canvas, type, quality);
    }
    // Never make a file bigger than it started.
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], outputNameFor(file.name, type), { type });
  } catch {
    return file;
  }
}
