import { useCallback, useEffect, useState } from "react";
import { Package, Trash2 } from "lucide-react";
import { Modal, Button, IconButton } from "../components/ui";
import { api } from "../api";

// The gallery body. Rendered inline (Settings) and inside MediaLibraryModal
// (the product/variant picker). Passing `onPick` makes thumbnails selectable.
export function MediaLibraryGrid({ token, onPick, notify, maxHeightClass = "max-h-[420px]" }) {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setAssets(await api.mediaAssets(token));
      setError("");
    } catch (requestError) {
      setError(requestError.message || "Could not load the media library");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const asset = await api.uploadMediaAsset(token, file);
      setAssets((current) => (current.some((row) => row.id === asset.id) ? current : [asset, ...current]));
      notify?.("Image uploaded");
      if (onPick) onPick(asset.url);
    } catch (requestError) {
      setError(requestError.message || "Could not upload the image");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (asset) => {
    setBusy(true);
    setError("");
    try {
      await api.deleteMediaAsset(token, asset.id);
      setAssets((current) => current.filter((row) => row.id !== asset.id));
      notify?.("Image deleted");
    } catch (requestError) {
      setError(requestError.message || "Could not delete the image");
    } finally {
      setBusy(false);
    }
  };

  return <>
    <div className="flex items-center justify-between gap-3">
      <p className="text-xs text-[#92939d]">{loading ? "Loading…" : `${assets.length} image${assets.length === 1 ? "" : "s"}`}</p>
      <label className={`text-xs font-semibold ${busy ? "text-[#a1a2ab]" : "text-[#6957f5]"}`}><input type="file" accept="image/*" className="hidden" disabled={busy} onChange={(event) => upload(event.target.files?.[0])} /><span className="cursor-pointer">{busy ? "Working…" : "+ Upload image"}</span></label>
    </div>
    {error && <p className="mt-3 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-xs text-[#c2564b]">{error}</p>}
    <div className={`app-scrollbar mt-4 grid grid-cols-3 gap-3 overflow-y-auto sm:grid-cols-4 lg:grid-cols-6 ${maxHeightClass}`}>
      {loading ? <p className="col-span-full py-10 text-center text-xs text-[#92939d]">Loading…</p> : assets.length === 0 ? <div className="col-span-full py-10 text-center"><span className="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl bg-[#f3f2ff] text-[#8a7df0]"><Package size={18} /></span><p className="mt-3 text-xs font-bold text-[#565762]">No images yet</p><p className="mt-1 text-[11px] text-[#a1a2ab]">Upload one to reuse across products.</p></div> : assets.map((asset) => <div key={asset.id} className="group relative">
        <button type="button" onClick={() => onPick?.(asset.url)} className={`block w-full overflow-hidden rounded-xl border ${onPick ? "border-[#e9e9ef] transition hover:border-[#887bf3]" : "border-[#e9e9ef]"}`}>
          <img src={asset.url} alt={asset.original_filename || "Image"} className="aspect-square w-full bg-[#fafafd] object-cover" />
        </button>
        <div className="absolute right-1 top-1 opacity-0 transition group-hover:opacity-100"><IconButton label="Delete image" onClick={() => remove(asset)}><Trash2 size={13} /></IconButton></div>
      </div>)}
    </div>
  </>;
}

// Modal wrapper used by the product/variant forms as a picker.
export function MediaLibraryModal({ token, onPick, onClose, notify }) {
  return <Modal open onClose={onClose} title="Media library" description={onPick ? "Pick an image to use." : "Browse, upload, and remove images. Images used by a product can't be deleted."} width="max-w-[720px]">
    <MediaLibraryGrid token={token} onPick={onPick} notify={notify} />
    <div className="mt-5 flex justify-end"><Button variant="outline" onClick={onClose}>Close</Button></div>
  </Modal>;
}
