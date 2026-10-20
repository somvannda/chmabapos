import { useEffect, useRef, useState } from "react";
import { Copy, Download, ExternalLink } from "lucide-react";
import { QRCodeCanvas } from "qrcode.react";

import { Button, Modal } from "../components/ui";
import { STORE_QR_POWERED_BY, STORE_QR_SCAN_LINE, storeQrFileName } from "../lib/storeQr";

// The card is drawn once on a canvas, and that same canvas is both the modal
// preview and the downloaded PNG. The merchant therefore always saves exactly
// what they see, including every font size and logo placement.
const CARD_WIDTH = 1080;
const CARD_HEIGHT = 1646;
const FONT = 'Inter, "Niradei", "Noto Sans Khmer Web", ui-sans-serif, system-ui, sans-serif';

function roundRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function drawCover(ctx, image, x, y, width, height) {
  const scale = Math.max(width / image.width, height / image.height);
  const sourceWidth = width / scale;
  const sourceHeight = height / scale;
  const sourceX = (image.width - sourceWidth) / 2;
  const sourceY = (image.height - sourceHeight) / 2;
  ctx.drawImage(image, sourceX, sourceY, sourceWidth, sourceHeight, x, y, width, height);
}

function drawLogoBox(ctx, image, initial, x, y, size, radius) {
  ctx.save();
  roundRect(ctx, x, y, size, size, radius);
  ctx.clip();
  if (image) {
    drawCover(ctx, image, x, y, size, size);
  } else {
    ctx.fillStyle = "#F0EFFF";
    ctx.fillRect(x, y, size, size);
    ctx.fillStyle = "#6957F5";
    ctx.font = `800 ${Math.round(size * 0.42)}px ${FONT}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(initial, x + size / 2, y + size / 2 + size * 0.02);
  }
  ctx.restore();
  ctx.save();
  roundRect(ctx, x, y, size, size, radius);
  ctx.strokeStyle = "#ECECF3";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();
}

function fitFontSize(ctx, text, maxWidth, startSize, minSize, weight) {
  let size = startSize;
  while (size > minSize) {
    ctx.font = `${weight} ${size}px ${FONT}`;
    if (ctx.measureText(text).width <= maxWidth) return size;
    size -= 2;
  }
  return minSize;
}

function truncateToWidth(ctx, text, maxWidth) {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let value = text;
  while (value.length > 1 && ctx.measureText(`${value}…`).width > maxWidth) {
    value = value.slice(0, -1);
  }
  return `${value}…`;
}

function drawCard(ctx, { name, tagline, link, initial, qr, logo }) {
  ctx.clearRect(0, 0, CARD_WIDTH, CARD_HEIGHT);
  ctx.fillStyle = "#F6F5FC";
  ctx.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);

  // White card with the violet edge, matching the modal card the merchant sees.
  ctx.save();
  roundRect(ctx, 48, 48, 984, 1550, 64);
  ctx.clip();
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(48, 48, 984, 1550);
  ctx.fillStyle = "#6957F5";
  ctx.fillRect(48, 48, 984, 20);
  ctx.restore();

  ctx.save();
  roundRect(ctx, 48, 48, 984, 1550, 64);
  ctx.strokeStyle = "#ECECF3";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();

  drawLogoBox(ctx, logo, initial, 415, 110, 250, 56);

  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  const nameSize = fitFontSize(ctx, name, 880, 62, 32, 800);
  ctx.font = `800 ${nameSize}px ${FONT}`;
  ctx.fillStyle = "#202128";
  ctx.fillText(name, 540, 440);

  if (tagline) {
    ctx.font = `500 38px ${FONT}`;
    ctx.fillStyle = "#898A95";
    ctx.fillText(truncateToWidth(ctx, tagline, 840), 540, 492);
  }

  // The quiet zone comes from qrcode.react's margin, and level "H" leaves room
  // for the logo in the middle without hurting scanability.
  ctx.drawImage(qr, 160, 566, 760, 760);

  ctx.save();
  roundRect(ctx, 435, 841, 210, 210, 48);
  ctx.fillStyle = "#FFFFFF";
  ctx.fill();
  ctx.restore();
  drawLogoBox(ctx, logo, initial, 452, 858, 175, 40);

  ctx.textAlign = "center";
  ctx.font = `800 42px ${FONT}`;
  ctx.fillStyle = "#4F5059";
  ctx.fillText(STORE_QR_SCAN_LINE, 540, 1400);

  // Deliberately quieter than the scan line: the credit must be present but
  // must not compete with the store's own name and QR.
  ctx.font = `600 24px ${FONT}`;
  ctx.fillStyle = "#6957F5";
  ctx.fillText(STORE_QR_POWERED_BY, 540, 1450);

  ctx.font = `500 22px ${FONT}`;
  ctx.fillStyle = "#A1A2AB";
  ctx.fillText(truncateToWidth(ctx, link, 840), 540, 1495);
}

function loadImage(src) {
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => resolve(null);
    image.src = src;
  });
}

export function StoreQrModal({ store, link = "", onClose, notify }) {
  const brand = store?.storefront || {};
  const name = store?.name || "Store";
  const tagline = (brand.tagline || "").trim();
  const initial = Array.from(name.trim())[0]?.toUpperCase() || "S";
  const previewRef = useRef(null);
  const qrRef = useRef(null);
  const logoImageRef = useRef(null);
  const [logoSrc, setLogoSrc] = useState("");
  const [logoState, setLogoState] = useState(brand.logo ? "loading" : "none");
  const [saving, setSaving] = useState(false);

  // A logo URL can live on another origin, and drawing that straight onto a
  // canvas would taint it so `toBlob` fails. Convert it to a data URL first;
  // when that fails the card simply keeps the store initial instead.
  useEffect(() => {
    let active = true;
    const raw = brand.logo || "";
    logoImageRef.current = null;
    if (!raw) {
      setLogoSrc("");
      setLogoState("none");
      return () => { active = false; };
    }
    setLogoState("loading");
    (async () => {
      try {
        let source = raw;
        if (!/^data:/i.test(raw)) {
          const response = await fetch(raw);
          if (!response.ok) throw new Error("logo");
          const blob = await response.blob();
          source = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ""));
            reader.onerror = () => reject(reader.error || new Error("logo"));
            reader.readAsDataURL(blob);
          });
        }
        const image = await loadImage(source);
        if (!image) throw new Error("logo");
        if (active) {
          logoImageRef.current = image;
          setLogoSrc(source);
          setLogoState("ready");
        }
      } catch {
        if (active) {
          logoImageRef.current = null;
          setLogoSrc("");
          setLogoState("none");
        }
      }
    })();
    return () => { active = false; };
  }, [brand.logo]);

  // Paint the same canvas the download exports. A frame lets qrcode.react draw
  // its off-screen canvas first, so the preview never captures an empty code.
  // The Khmer face is loaded explicitly too: canvas text does not wait for the
  // page's `font-display: swap` the way HTML text does, and a Khmer store name
  // would otherwise fall back to the OS font.
  useEffect(() => {
    let frame = 0;
    let cancelled = false;
    const paint = () => {
      const canvas = previewRef.current;
      const qr = qrRef.current;
      if (!canvas || !qr) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      drawCard(ctx, { name, tagline, link, initial, qr, logo: logoImageRef.current });
    };
    const start = async () => {
      try {
        if (document.fonts?.load) await document.fonts.load('800 62px "Niradei"', name);
        if (document.fonts?.ready) await document.fonts.ready;
      } catch {
        // The card still renders with the system fallback.
      }
      if (!cancelled) frame = window.requestAnimationFrame(paint);
    };
    start();
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frame);
    };
  }, [name, tagline, link, initial, logoSrc, logoState]);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(link);
      notify?.("Store link copied");
    } catch {
      notify?.("Could not copy the store link");
    }
  };

  const download = async () => {
    const canvas = previewRef.current;
    if (!canvas || !link) return;
    setSaving(true);
    try {
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("Could not create the QR image");
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = storeQrFileName(name);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1500);
      notify?.("QR code saved");
    } catch (error) {
      notify?.(error.message || "Could not save the QR code");
    } finally {
      setSaving(false);
    }
  };

  if (!link) return null;

  const logoNote = brand.logo
    ? logoState === "none"
      ? "Your logo could not be loaded, so the code uses your store initial."
      : "Your logo sits in the middle of the code and on the card."
    : "Add a logo on the Store page and it will appear here next time.";

  return (
    <Modal
      open
      onClose={onClose}
      title="Store QR code"
      description="Customers scan this code to open your store page."
      width="max-w-[720px]"
    >
      <div className="grid gap-5 sm:grid-cols-[300px_minmax(0,1fr)] sm:items-center sm:gap-6">
        <div className="flex justify-center">
          <div className="w-full max-w-[220px] overflow-hidden rounded-[22px] shadow-[0_18px_50px_rgba(20,21,28,.10)] sm:max-w-[300px]">
            <canvas
              ref={previewRef}
              width={CARD_WIDTH}
              height={CARD_HEIGHT}
              role="img"
              aria-label={`QR code poster for ${name}`}
              className="block h-auto w-full"
            />
          </div>
        </div>

        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]">This QR opens</p>
          <p className="mt-1 break-all rounded-xl border border-[#e9e9ef] bg-[#fafafd] px-3 py-2.5 text-[11px] font-semibold leading-5 text-[#4f5059]">
            {link}
          </p>
          <div className="mt-4 grid gap-2">
            <Button onClick={download} disabled={saving || logoState === "loading"} className="w-full">
              {saving ? "Saving..." : <><Download size={15} /> Save image</>}
            </Button>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="outline" onClick={copyLink} className="w-full">
                <Copy size={15} /> Copy link
              </Button>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => window.open(link, "_blank", "noopener,noreferrer")}
              >
                <ExternalLink size={14} /> Open page
              </Button>
            </div>
          </div>
          <p className="mt-4 pr-16 text-[10px] leading-4 text-[#92939d] sm:pr-0">
            Save the image, then print it for the counter or share it in a message.
          </p>
          <p className="mt-1 pr-16 text-[10px] leading-4 text-[#92939d] sm:pr-0">{logoNote}</p>
        </div>
      </div>
      <div aria-hidden="true" className="pointer-events-none fixed -left-[10000px] top-0 h-px w-px overflow-hidden">
        <QRCodeCanvas
          ref={qrRef}
          value={link}
          size={760}
          level="H"
          marginSize={2}
          bgColor="#FFFFFF"
          fgColor="#17181C"
        />
      </div>
    </Modal>
  );
}
