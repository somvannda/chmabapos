import { useEffect, useRef, useState } from "react";
import { Copy, Download, ExternalLink } from "lucide-react";
import { QRCodeCanvas } from "qrcode.react";

import { Button, Modal } from "../components/ui";
import { STORE_QR_POWERED_BY, STORE_QR_SCAN_LINE, storeQrFileName } from "../lib/storeQr";

// The saved poster is drawn at 1080x1350 so it stays crisp on a phone screen
// and in print. The on-screen preview is the same card in HTML, sized down; the
// QR pixels come from the canvas qrcode.react already renders, so what the
// merchant sees and what they save are the same code.
const CARD_WIDTH = 1080;
const CARD_HEIGHT = 1350;
const FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

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

  // The card, with a violet edge along the top and a soft halo behind the logo.
  ctx.save();
  roundRect(ctx, 40, 40, 1000, 1270, 56);
  ctx.clip();
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(40, 40, 1000, 1270);
  ctx.fillStyle = "#6957F5";
  ctx.fillRect(40, 40, 1000, 18);
  ctx.fillStyle = "#F6F5FC";
  ctx.beginPath();
  ctx.arc(540, 190, 150, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  ctx.save();
  roundRect(ctx, 40, 40, 1000, 1270, 56);
  ctx.strokeStyle = "#ECECF3";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();

  drawLogoBox(ctx, logo, initial, 460, 108, 160, 40);

  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  const nameSize = fitFontSize(ctx, name, 840, 58, 32, 800);
  ctx.font = `800 ${nameSize}px ${FONT}`;
  ctx.fillStyle = "#202128";
  ctx.fillText(name, 540, 352);

  if (tagline) {
    ctx.font = `500 28px ${FONT}`;
    ctx.fillStyle = "#898A95";
    ctx.fillText(truncateToWidth(ctx, tagline, 800), 540, 402);
  }

  // The quiet zone comes from qrcode.react's margin, and level "H" leaves room
  // for the logo in the middle without hurting scanability.
  ctx.drawImage(qr, 200, 444, 680, 680);

  ctx.save();
  roundRect(ctx, 450, 694, 180, 180, 44);
  ctx.fillStyle = "#FFFFFF";
  ctx.fill();
  ctx.restore();
  drawLogoBox(ctx, logo, initial, 464, 708, 152, 34);

  ctx.textAlign = "center";
  ctx.font = `800 34px ${FONT}`;
  ctx.fillStyle = "#4F5059";
  ctx.fillText(STORE_QR_SCAN_LINE, 540, 1192);

  ctx.font = `800 30px ${FONT}`;
  ctx.fillStyle = "#6957F5";
  ctx.fillText(STORE_QR_POWERED_BY, 540, 1250);

  ctx.font = `500 20px ${FONT}`;
  ctx.fillStyle = "#A1A2AB";
  ctx.fillText(truncateToWidth(ctx, link, 880), 540, 1292);
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
  const qrRef = useRef(null);
  const [logoSrc, setLogoSrc] = useState("");
  const [logoState, setLogoState] = useState(brand.logo ? "loading" : "none");
  const [saving, setSaving] = useState(false);

  // A logo URL can live on another origin, and drawing that straight onto a
  // canvas would taint it so `toBlob` fails. Convert it to a data URL first;
  // when that fails the card simply keeps the store initial instead.
  useEffect(() => {
    let active = true;
    const raw = brand.logo || "";
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
          setLogoSrc(source);
          setLogoState("ready");
        }
      } catch {
        if (active) {
          setLogoSrc("");
          setLogoState("none");
        }
      }
    })();
    return () => { active = false; };
  }, [brand.logo]);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(link);
      notify?.("Store link copied");
    } catch {
      notify?.("Could not copy the store link");
    }
  };

  const download = async () => {
    const qr = qrRef.current;
    if (!qr || !link) return;
    setSaving(true);
    try {
      const logo = logoSrc ? await loadImage(logoSrc) : null;
      const canvas = document.createElement("canvas");
      canvas.width = CARD_WIDTH;
      canvas.height = CARD_HEIGHT;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Could not draw the QR code");
      drawCard(ctx, { name, tagline, link, initial, qr, logo });
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
      <div className="grid gap-5 sm:grid-cols-[248px_minmax(0,1fr)] sm:items-center sm:gap-6">
        <div className="flex justify-center">
          <div className="w-full max-w-[248px] overflow-hidden rounded-[22px] border border-[#ececf3] bg-white shadow-[0_18px_50px_rgba(20,21,28,.10)]">
            <div className="h-1.5 w-full bg-[#6957f5]" />
            <div className="px-4 pb-4 pt-5 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center overflow-hidden rounded-2xl border border-[#eeeeF2] bg-[#f6f5ff]">
                {logoSrc ? (
                  <img src={logoSrc} alt="" className="h-full w-full object-cover" />
                ) : (
                  <span className="text-xl font-black text-[#6957f5]">{initial}</span>
                )}
              </div>
              <p className="mt-2.5 truncate text-sm font-extrabold tracking-[-.02em] text-[#202128]">{name}</p>
              {tagline && <p className="mt-0.5 truncate text-[10px] leading-4 text-[#92939d]">{tagline}</p>}
              <div className="relative mx-auto mt-3 w-[184px]">
                <QRCodeCanvas
                  ref={qrRef}
                  value={link}
                  size={720}
                  level="H"
                  marginSize={2}
                  bgColor="#FFFFFF"
                  fgColor="#17181C"
                  className="block rounded-lg"
                  style={{ width: "100%", height: "auto" }}
                />
                <span className="absolute left-1/2 top-1/2 flex h-[46px] w-[46px] -translate-x-1/2 -translate-y-1/2 items-center justify-center overflow-hidden rounded-xl border-[3px] border-white bg-[#f0efff] shadow-sm">
                  {logoSrc ? (
                    <img src={logoSrc} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <span className="text-sm font-black text-[#6957f5]">{initial}</span>
                  )}
                </span>
              </div>
              <p className="mt-3 text-[11px] font-bold text-[#4f5059]">{STORE_QR_SCAN_LINE}</p>
              <p className="mt-0.5 text-[9px] font-bold tracking-wide text-[#6957f5]">{STORE_QR_POWERED_BY}</p>
            </div>
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
          <p className="mt-4 text-[10px] leading-4 text-[#92939d]">
            Save the image, then print it for the counter or share it in a message.
          </p>
          <p className="mt-1 text-[10px] leading-4 text-[#92939d]">{logoNote}</p>
        </div>
      </div>
    </Modal>
  );
}
