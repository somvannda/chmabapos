import { useState, useEffect } from "react";
import { AlertTriangle, ArrowRightLeft, Boxes, Check, CircleDollarSign, Edit3, Eye, Grid2X2, List, Package, Plus, RefreshCw, Search, Settings2, Tag, ToggleLeft, ToggleRight, Trash2, Truck } from "lucide-react";
import { Modal, Field, Dropdown, IconButton, Button, ProductMark, formatCurrencyAmount, Badge } from "../components/ui";
import { SmallStat, ConfirmDialog, MetricCard } from "./widgets";
import { SuppliersModal, PurchaseOrderModal } from "./purchasing";
import { MediaLibraryGrid } from "./media";
import { api } from "../api";
import { slugifySku, isParentSkuLocked } from "../lib/sku";

function ProductFormModal({ token, storeId, product, categories, modifierGroups = [], onCreate, onUpdate, onClose, notify, loading, onUploadImage }) {
  const isEdit = Boolean(product);
  const [form, setForm] = useState({
    name: product?.name || "",
    sku: product?.sku || "",
    categoryId: product?.category_id || "",
    price: product ? String(product.price) : "",
    costPrice: product?.cost_price != null ? String(product.cost_price) : "",
    taxRate: product?.tax_rate != null ? String(product.tax_rate) : "",
    stock: product?.on_hand != null ? String(product.on_hand) : "",
    reorderPoint: product?.reorder_point != null ? String(product.reorder_point) : "10",
    image: product?.image || "",
    description: product?.description || "",
    barcode: product?.barcode || "",
    brand: product?.brand || "",
    unit: product?.unit || "each",
    trackInventory: product?.track_inventory !== false,
    trackSerials: product?.track_serials === true,
    modifierGroupId: product?.modifier_group_id || "",
  });
  const [attributes, setAttributes] = useState(() => {
    const raw = product?.attributes && typeof product.attributes === "object" ? product.attributes : {};
    return Object.entries(raw).map(([key, value]) => ({ key, value: value == null ? "" : String(value) }));
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [imageFile, setImageFile] = useState(null);
  const [showLibrary, setShowLibrary] = useState(false);
  // A product with variants sells by its variants, so the parent SKU becomes a
  // base/grouping code: auto-derive it from the name until variants exist, then
  // lock it so it cannot drift.
  const skuLockedByVariants = Boolean(isEdit) && isParentSkuLocked((product?.variants || []).length);
  const [skuTouched, setSkuTouched] = useState(Boolean(product?.sku));

  const updateName = (value) => {
    setForm((current) => {
      if (skuTouched || skuLockedByVariants) return { ...current, name: value };
      return { ...current, name: value, sku: slugifySku(value) };
    });
  };

  const units = ["each", "kg", "g", "l", "ml", "pack", "box", "dozen"];
  const childrenByParent = categories.filter((item) => item.parent_id).reduce((acc, item) => { (acc[item.parent_id] = acc[item.parent_id] || []).push(item); return acc; }, {});
  const categoryOptions = [{ value: "", label: "Uncategorized" }, ...categories.filter((item) => !item.parent_id).flatMap((parent) => [{ value: String(parent.id), label: parent.name }, ...(childrenByParent[parent.id] || []).map((child) => ({ value: String(child.id), label: `— ${child.name}` }))])];

  const [suggestions, setSuggestions] = useState({ keys: [], values: {}, brands: [], names: [], skus: [] });
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const found = await api.attributeSuggestions(token);
        if (active) setSuggestions({ keys: found?.keys || [], values: found?.values || {}, brands: found?.brands || [], names: found?.names || [], skus: found?.skus || [] });
      } catch { /* suggestions are optional */ }
    })();
    return () => { active = false; };
  }, [token]);
  const allAttrValues = [...new Set(Object.values(suggestions.values).flat())].sort();
  const readImage = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => { setForm({ ...form, image: String(reader.result) }); setImageFile(file); };
    reader.readAsDataURL(file);
  };

  const updateAttribute = (index, patch) => setAttributes(attributes.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  const addAttribute = () => setAttributes([...attributes, { key: "", value: "" }]);
  const removeAttribute = (index) => setAttributes(attributes.filter((_, i) => i !== index));

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    const attributesObject = attributes.reduce((acc, row) => {
      const key = row.key.trim();
      if (key) acc[key] = row.value;
      return acc;
    }, {});
    // Images are uploaded after save via the dedicated endpoint; never send the
    // local base64 data URL (the image column only stores a short URL).
    const hasLocalImage = Boolean(imageFile) || String(form.image || "").startsWith("data:");
    const payload = {
      name: form.name.trim(),
      sku: form.sku.trim(),
      price: Number(form.price),
      cost_price: form.costPrice === "" ? null : Number(form.costPrice),
      tax_rate: form.taxRate === "" ? null : Number(form.taxRate),
      category_id: form.categoryId || null,
      image: hasLocalImage ? null : (form.image || null),
      description: form.description.trim() || null,
      barcode: form.barcode.trim() || null,
      brand: form.brand.trim() || null,
      unit: form.unit,
      track_inventory: form.trackInventory,
      track_serials: form.trackSerials,
      attributes: Object.keys(attributesObject).length ? attributesObject : null,
      modifier_group_id: form.modifierGroupId || null,
    };
    try {
      const saved = isEdit
        ? await onUpdate(product.id, { ...payload })
        : await onCreate({ ...payload, opening_stock: form.trackSerials ? 0 : (Number(form.stock) || 0), reorder_point: Number(form.reorderPoint) || 10 });
      if (saved) {
        if (imageFile) {
          const uploaded = await onUploadImage?.(saved.id, imageFile);
          if (uploaded) saved.image = uploaded.image;
        }
        notify(isEdit ? `${saved.name} updated` : `${saved.name} added`);
        onClose();
      }
    } catch (requestError) {
      setError(requestError.message || "Could not save product");
    } finally {
      setBusy(false);
    }
  };

  return <Modal open onClose={onClose} title={isEdit ? `Edit ${product.name}` : "Add product"} description={isEdit ? "Update product details and image." : "Add a new product to your catalog."} width="max-w-[820px]" dismissOnBackdrop={false}><form onSubmit={submit} className="space-y-3">
    <div className="grid gap-3 sm:grid-cols-2"><Field label="Name" required value={form.name} onChange={(event) => updateName(event.target.value)} list="chmaba-product-names" />{skuLockedByVariants ? <Field label="SKU" value={form.sku} disabled hint="Locked while this product has variants." /> : <Field label="SKU" required value={form.sku} onChange={(event) => { setSkuTouched(true); setForm({ ...form, sku: event.target.value }); }} list="chmaba-product-skus" />}</div>
    <div className="grid gap-3 sm:grid-cols-3"><Field label="Price" type="number" min="0" step="0.01" required value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} /><Field label="Cost price" type="number" min="0" step="0.01" value={form.costPrice} onChange={(event) => setForm({ ...form, costPrice: event.target.value })} /><Field label="Tax rate %" type="number" min="0" step="0.01" value={form.taxRate} onChange={(event) => setForm({ ...form, taxRate: event.target.value })} placeholder="Store default" /></div>
    <div className="grid gap-3 sm:grid-cols-2"><Field label="Barcode" value={form.barcode} onChange={(event) => setForm({ ...form, barcode: event.target.value })} placeholder="Scan or type" /><Field label="Brand" value={form.brand} onChange={(event) => setForm({ ...form, brand: event.target.value })} placeholder="e.g. Apple" list="chmaba-brands" /></div>
    <div className="grid gap-3 sm:grid-cols-3"><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Category</span><Dropdown value={form.categoryId} onChange={(v) => setForm({ ...form, categoryId: v })} options={categoryOptions} /></label><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Unit</span><Dropdown value={form.unit} onChange={(v) => setForm({ ...form, unit: v })} options={units.map((value) => ({ value, label: value }))} /></label><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Modifier group</span><Dropdown value={form.modifierGroupId} onChange={(v) => setForm({ ...form, modifierGroupId: v })} options={[{ value: "", label: "None" }, ...modifierGroups.map((group) => ({ value: String(group.id), label: group.name }))]} /></label></div>
    <div className="grid gap-3 sm:grid-cols-2">{!isEdit && !form.trackSerials ? <Field label="Opening stock" type="number" min="0" value={form.stock} onChange={(event) => setForm({ ...form, stock: event.target.value })} /> : !isEdit ? <div className="rounded-xl border border-[#e9e9ef] bg-[#fafafd] px-3 py-2.5 text-[11px] leading-4 text-[#92939d]">Serial-tracked products start at 0. Add units and their serials from <span className="font-semibold text-[#4f5059]">Inventory → Receive stock</span>.</div> : <Field label="In stock" value={form.stock} disabled />}<Field label="Reorder point" type="number" min="0" value={form.reorderPoint} onChange={(event) => setForm({ ...form, reorderPoint: event.target.value })} /></div>
    <label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Description</span><textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows={2} className="w-full rounded-xl border border-[#dfdfe8] px-3.5 py-2.5 text-sm outline-none focus:border-[#887bf3]" /></label>
    <div className="flex flex-wrap gap-4"><label className="flex items-center gap-2 text-xs font-semibold text-[#4f5059]"><input type="checkbox" checked={form.trackInventory} onChange={(event) => setForm({ ...form, trackInventory: event.target.checked })} /> Track inventory</label><label className="flex items-center gap-2 text-xs font-semibold text-[#4f5059]"><input type="checkbox" checked={form.trackSerials} onChange={(event) => setForm({ ...form, trackSerials: event.target.checked })} /> Track serials / IMEI</label></div>
    <div className="rounded-xl border border-[#e9e9ef] p-3"><div className="flex items-center justify-between"><span className="text-xs font-semibold text-[#4f5059]">Attributes</span><button type="button" onClick={addAttribute} className="text-xs font-semibold text-[#6957f5]">+ Add</button></div>{attributes.length === 0 ? <p className="mt-2 text-[11px] text-[#92939d]">Optional fields like model, color, warranty.</p> : <div className="mt-2 space-y-2">{attributes.map((row, index) => <div key={index} className="flex items-center gap-2"><input value={row.key} onChange={(event) => updateAttribute(index, { key: event.target.value })} placeholder="Key" list="chmaba-attr-keys" className="h-9 min-w-0 flex-1 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" /><input value={row.value} onChange={(event) => updateAttribute(index, { value: event.target.value })} placeholder="Value" list={`chmaba-attr-${index}`} className="h-9 min-w-0 flex-1 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" /><IconButton label="Remove attribute" onClick={() => removeAttribute(index)}><Trash2 size={15} /></IconButton></div>)}</div>}</div>
    <div className="flex items-center gap-3 rounded-xl border border-[#e9e9ef] p-3">{form.image ? <img src={form.image} alt="preview" className="h-12 w-12 rounded-lg object-cover" /> : <Package size={18} className="text-[#a1a2ab]" />}<label className="text-xs font-semibold text-[#6957f5]"><input type="file" accept="image/*" className="hidden" onChange={readImage} /><span className="cursor-pointer">Upload product image</span></label><button type="button" onClick={() => setShowLibrary((current) => !current)} className="text-xs font-semibold text-[#6957f5]">{showLibrary ? "Hide library" : "Choose from library"}</button>{form.image && <IconButton label="Remove image" onClick={() => setForm({ ...form, image: "" })}><Trash2 size={15} /></IconButton>}</div>
    {showLibrary && <div className="rounded-xl border border-[#e9e9ef] p-3"><MediaLibraryGrid token={token} notify={notify} maxHeightClass="max-h-[240px]" onPick={(url) => { setForm((current) => ({ ...current, image: url })); setShowLibrary(false); }} /></div>}
    {error && <p className="rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-xs text-[#c2564b]">{error}</p>}
    <div className="flex gap-2 pt-2"><Button variant="outline" className="flex-1" type="button" onClick={onClose}>Cancel</Button><Button className="flex-1" type="submit" disabled={busy || !form.name.trim() || !form.sku.trim() || !(Number(form.price) >= 0)}>{busy ? "Saving..." : isEdit ? "Save product" : "Add product"} <Check size={15} /></Button></div>
    <datalist id="chmaba-product-names">{suggestions.names.map((name) => <option key={name} value={name} />)}</datalist><datalist id="chmaba-product-skus">{suggestions.skus.map((sku) => <option key={sku} value={sku} />)}</datalist><datalist id="chmaba-brands">{suggestions.brands.map((brand) => <option key={brand} value={brand} />)}</datalist><datalist id="chmaba-attr-keys">{suggestions.keys.map((key) => <option key={key} value={key} />)}</datalist>{attributes.map((row, index) => <datalist key={`dl-${index}`} id={`chmaba-attr-${index}`}>{(suggestions.values[row.key] || allAttrValues).map((value) => <option key={value} value={value} />)}</datalist>)}
  </form></Modal>;
}

function LiveCatalogView({ products, categories, setProducts, setCategories, notify, token, onCreateProduct, onUpdateProduct, onCreateCategory, onDeleteProduct, onSetVariants, onAddSerials, onLoadSerials, onUpdateSerial, onLoadTickets, onCreateTicket, onLoadModifierGroups, onCreateModifierGroup, onUpdateModifierGroup, onDeleteModifierGroup, onAddBatches, onLoadBatches, onUploadImage, onUploadVariantImage, loading, error, baseCurrency = "USD", storeDefaultReorder = 10 }) {  const [query, setQuery] = useState("");
const [category, setCategory] = useState("all");
const [formOpen, setFormOpen] = useState(false);
const [editProduct, setEditProduct] = useState(null);
const [viewProduct, setViewProduct] = useState(null);
const [variantsProduct, setVariantsProduct] = useState(null);
const [serialsProduct, setSerialsProduct] = useState(null);
const [batchesProduct, setBatchesProduct] = useState(null);
const [modifiersOpen, setModifiersOpen] = useState(false);
const [modifierGroups, setModifierGroups] = useState([]);
useEffect(() => { (async () => { const rows = await onLoadModifierGroups?.(); setModifierGroups(Array.isArray(rows) ? rows : []); })(); }, [modifiersOpen]);
const [deleteTarget, setDeleteTarget] = useState(null);
const [toggleTarget, setToggleTarget] = useState(null);  const childrenByParent = categories.filter((item) => item.parent_id).reduce((acc, item) => { (acc[item.parent_id] = acc[item.parent_id] || []).push(item); return acc; }, {});  const categoryOptions = [{ value: "all", label: "All products" }, ...categories.filter((item) => !item.parent_id).flatMap((parent) => [{ value: String(parent.id), label: parent.name }, ...(childrenByParent[parent.id] || []).map((child) => ({ value: String(child.id), label: `— ${child.name}` }))])];  const categoryIncludes = (id) => (childrenByParent[id] ? [id, ...childrenByParent[id].map((child) => String(child.id))] : [String(id)]);  const categoryById = categories.reduce((acc, item) => { acc[String(item.id)] = item; return acc; }, {});  const categoryLabel = (categoryId) => { const cat = categoryById[String(categoryId)]; if (!cat) return ""; const parent = cat.parent_id ? categoryById[String(cat.parent_id)] : null; return parent ? `${parent.name} › ${cat.name}` : cat.name; };  const filtered = products.filter((product) => (category === "all" || categoryIncludes(category).includes(String(product.categoryId))) && `${product.name} ${product.sku}`.toLowerCase().includes(query.toLowerCase()));  const activeCount = products.filter((p) => p.is_active !== false).length;  const lowCount = products.filter((p) => p.stock <= (p.reorder_point || 10)).length;  const performToggle = async () => { const item = toggleTarget; if (!item) return; setToggleTarget(null); const updated = await onUpdateProduct(item.id, { is_active: item.activate }); if (updated) notify(item.activate ? `${updated.name} activated` : `${updated.name} deactivated`); };const performDelete = async () => { const target = deleteTarget; if (!target) return; setDeleteTarget(null); await onDeleteProduct?.(target.id); };  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Products</h2><p className="mt-1 text-sm text-[#898a95]">Live products from your Chmaba workspace.</p></div><div className="flex items-center gap-2"><Button onClick={() => { setEditProduct(null); setFormOpen(true); }}><Plus size={16} /> Add product</Button><Button variant="outline" onClick={() => setModifiersOpen(true)}><Settings2 size={16} /> Modifier groups</Button></div></div>{error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}<div className="mt-7 grid gap-3 sm:grid-cols-3"><SmallStat label="Total products" value={products.length} detail="In your catalog" icon={Package} tone="violet" /><SmallStat label="Active" value={activeCount} detail="Available for sale" icon={Tag} tone="green" /><SmallStat label="Low stock" value={lowCount} detail="At or below reorder point" icon={AlertTriangle} tone="yellow" /></div><div className="mt-5 rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-6"><div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"><div className="relative min-w-0 flex-1 xl:max-w-[380px]"><Search size={15} className="absolute left-3.5 top-3 text-[#a1a2ab]" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by name or SKU..." className="h-10 w-full rounded-xl border border-[#e3e3ea] bg-[#fcfcfd] pl-10 pr-3 text-xs outline-none focus:border-[#887bf3]" /></div><div className="flex items-center gap-1 overflow-x-auto rounded-xl bg-[#f6f6f9] p-1">{categoryOptions.map((option) => <button key={option.value} onClick={() => setCategory(option.value)} className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-[11px] font-bold ${category === option.value ? "bg-white text-[#4d4e57] shadow-sm" : "text-[#92939d]"}`}>{option.label}</button>)}</div></div><div className="app-scrollbar mt-5 overflow-x-auto"><table className="mobile-table w-full border-collapse text-left"><thead><tr className="border-y border-[#f0f0f3] text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]"><th className="py-3 pl-2 font-bold">Product</th><th className="px-4 py-3 font-bold">SKU</th><th className="px-4 py-3 font-bold">Category</th><th className="px-4 py-3 font-bold">Price</th><th className="px-4 py-3 font-bold">Stock</th><th className="px-4 py-3 font-bold">Status</th><th className="w-36 px-2 py-3 text-right font-bold">Actions</th></tr></thead><tbody>{filtered.length === 0 ? <tr><td colSpan="7" className="py-14 text-center text-sm text-[#92939d]">No products found.</td></tr> : filtered.map((product) => <tr key={product.id} className={`border-b border-[#f2f2f5] last:border-0 ${product.is_active === false ? "opacity-60" : ""}`}><td className="py-3.5 pl-2"><div className="flex items-center gap-3">{product.image ? <img src={product.image} alt={product.name} className="h-9 w-9 rounded-lg object-cover" /> : <ProductMark product={product} size="sm" />}<p className="text-xs font-extrabold text-[#34353d]">{product.name}</p></div></td><td className="px-4 py-3.5 text-xs text-[#777883]">{product.sku}</td><td className="px-4 py-3.5 text-xs text-[#777883]">{categoryLabel(product.categoryId) || "—"}</td><td className="px-4 py-3.5 text-xs font-extrabold">{formatCurrencyAmount(product.price, baseCurrency)}</td><td className="px-4 py-3.5"><Badge tone={product.stock <= (product.reorder_point || 10) ? "yellow" : "green"}>{product.stock} in stock</Badge></td><td className="px-4 py-3.5"><Badge tone={product.is_active === false ? "neutral" : "green"}>{product.is_active === false ? "Inactive" : "Active"}</Badge></td><td className="px-2 py-3.5"><div className="flex items-center justify-end gap-1"><IconButton label="View product" onClick={() => setViewProduct(product)}><Eye size={15} /></IconButton><IconButton label="Manage variants" onClick={() => setVariantsProduct(product)}><Boxes size={15} /></IconButton><IconButton label="Manage serials" onClick={() => setSerialsProduct(product)}><List size={15} /></IconButton><IconButton label="Manage batches" onClick={() => setBatchesProduct(product)}><Truck size={15} /></IconButton><IconButton label={product.is_active === false ? "Activate" : "Deactivate"} onClick={() => setToggleTarget({ id: product.id, name: product.name, activate: product.is_active === false })}>{product.is_active === false ? <ToggleLeft size={15} /> : <ToggleRight size={15} />}</IconButton><IconButton label="Edit product" onClick={() => { setEditProduct(product); setFormOpen(true); }}><Edit3 size={15} /></IconButton><IconButton label="Delete product" onClick={() => setDeleteTarget(product)}><Trash2 size={15} /></IconButton></div></td></tr>)}</tbody></table></div></div>{formOpen && <ProductFormModal categories={categories} product={editProduct} modifierGroups={modifierGroups} onCreate={onCreateProduct} onUpdate={onUpdateProduct} onClose={() => setFormOpen(false)} notify={notify} loading={loading} onUploadImage={onUploadImage} token={token} />}{modifiersOpen && <ModifiersModal groups={modifierGroups} onLoad={onLoadModifierGroups} onCreate={onCreateModifierGroup} onUpdate={onUpdateModifierGroup} onDelete={onDeleteModifierGroup} onClose={() => setModifiersOpen(false)} notify={notify} />}{batchesProduct && <BatchesModal product={batchesProduct} onLoad={onLoadBatches} onAdd={onAddBatches} onClose={() => setBatchesProduct(null)} notify={notify} />}{serialsProduct && <SerialsModal product={serialsProduct} onLoad={onLoadSerials} onAdd={onAddSerials} onUpdate={onUpdateSerial} onLoadTickets={onLoadTickets} onCreateTicket={onCreateTicket} onClose={() => setSerialsProduct(null)} notify={notify} />}{variantsProduct && <VariantsModal product={variantsProduct} token={token} onSave={onSetVariants} onUploadImage={onUploadVariantImage} onClose={() => setVariantsProduct(null)} notify={notify} />}{viewProduct && <Modal open onClose={() => setViewProduct(null)} title={viewProduct.name} description={`${viewProduct.sku} · ${viewProduct.category || "Uncategorized"}`} width="max-w-[480px]"><div className="flex items-start gap-4">{viewProduct.image ? <img src={viewProduct.image} alt={viewProduct.name} className="h-24 w-24 rounded-xl object-cover" /> : <ProductMark product={viewProduct} size="lg" />}<div className="min-w-0 flex-1 space-y-2 text-xs"><div className="flex justify-between"><span className="text-[#92939d]">Price</span><span className="font-extrabold">{formatCurrencyAmount(viewProduct.price, baseCurrency)}</span></div>{viewProduct.cost_price != null && <div className="flex justify-between"><span className="text-[#92939d]">Cost price</span><span className="font-extrabold">{formatCurrencyAmount(viewProduct.cost_price, baseCurrency)}</span></div>}<div className="flex justify-between"><span className="text-[#92939d]">In stock</span><span className="font-extrabold">{viewProduct.stock}</span></div><div className="flex justify-between"><span className="text-[#92939d]">Reorder point</span><span className="font-extrabold">{viewProduct.reorder_point ?? 10}</span></div><div className="flex justify-between"><span className="text-[#92939d]">Status</span><Badge tone={viewProduct.is_active === false ? "neutral" : "green"}>{viewProduct.is_active === false ? "Inactive" : "Active"}</Badge></div></div></div><dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 rounded-xl bg-[#fafafd] p-3 text-xs">{viewProduct.barcode && <div><dt className="text-[#92939d]">Barcode</dt><dd className="font-semibold text-[#4d4e57]">{viewProduct.barcode}</dd></div>}{viewProduct.brand && <div><dt className="text-[#92939d]">Brand</dt><dd className="font-semibold text-[#4d4e57]">{viewProduct.brand}</dd></div>}<div><dt className="text-[#92939d]">Unit</dt><dd className="font-semibold text-[#4d4e57]">{viewProduct.unit || "each"}</dd></div><div><dt className="text-[#92939d]">Tracks serials</dt><dd className="font-semibold text-[#4d4e57]">{viewProduct.track_serials ? "Yes" : "No"}</dd></div>{viewProduct.attributes && Object.entries(viewProduct.attributes).map(([key, value]) => <div key={key}><dt className="text-[#92939d]">{key}</dt><dd className="font-semibold text-[#4d4e57]">{String(value)}</dd></div>)}</dl>{viewProduct.description ? <p className="mt-4 rounded-xl bg-[#fafafd] p-3 text-xs leading-5 text-[#656670]">{viewProduct.description}</p> : null}<div className="mt-5 flex justify-end"><Button onClick={() => setViewProduct(null)}>Close</Button></div></Modal>}{toggleTarget && <ConfirmDialog open title={toggleTarget.activate ? `Activate ${toggleTarget.name}?` : `Deactivate ${toggleTarget.name}?`} message={toggleTarget.activate ? "The product can be sold again." : "Deactivated products are hidden from new sales and POS."} confirmLabel={toggleTarget.activate ? "Activate" : "Deactivate"} onConfirm={performToggle} onCancel={() => setToggleTarget(null)} />}{deleteTarget && <ConfirmDialog open title={`Delete ${deleteTarget.name}?`} message="This permanently deletes the product and its stock." confirmLabel="Delete product" onConfirm={performDelete} onCancel={() => setDeleteTarget(null)} />}</div>;}

function LiveInventoryView({ inventory, onAdjust, onRestock, notify, loading, error, baseCurrency = "USD", token, storeId, onSync, stores = [], onTransfer }) {  const [filter, setFilter] = useState("All stock");
const [adjustProduct, setAdjustProduct] = useState(null);
const [adjustValue, setAdjustValue] = useState(0);
const [adjustVariant, setAdjustVariant] = useState("");
const [restockProduct, setRestockProduct] = useState(null);
const [restockQty, setRestockQty] = useState(1);
const [restockVariant, setRestockVariant] = useState("");
const [restockSerials, setRestockSerials] = useState("");
const [restockUnitCost, setRestockUnitCost] = useState("");
const [supplier, setSupplier] = useState("");
const [reference, setReference] = useState("");
const [suppliersOpen, setSuppliersOpen] = useState(false);
const [suppliers, setSuppliers] = useState([]);
useEffect(() => { let active = true; (async () => { try { const rows = await api.suppliers(token); if (active) setSuppliers(rows); } catch { /* suppliers are optional */ } })(); return () => { active = false; }; }, [token]);
const [transferProduct, setTransferProduct] = useState(null);
const [transferTo, setTransferTo] = useState("");
const [transferQty, setTransferQty] = useState(1);
const [transferVariant, setTransferVariant] = useState("");
const [serialLookupOpen, setSerialLookupOpen] = useState(false);
const [purchasesOpen, setPurchasesOpen] = useState(false);  const filtered = inventory.filter((product) => filter === "All stock" || (filter === "Low stock" ? stateOf(product) !== "healthy" : stateOf(product) === "healthy"));  const saveAdjustment = async () => { const result = await onAdjust(adjustProduct.product_id, { quantity: Number(adjustValue), reason: "manual_adjustment", variant_id: adjustVariant || null }); if (result) { setAdjustProduct(null); setAdjustVariant(""); } };const saveRestock = async () => { const tracked = Boolean(restockProduct?.track_serials); const serialNumbers = tracked ? restockSerials.split(/[\n,]+/).map((value) => value.trim()).filter(Boolean) : []; if (restockProduct?.variants?.length && !restockVariant) { notify("Choose a variant to receive into"); return; } if (tracked && serialNumbers.length !== Number(restockQty)) { notify(`Enter ${restockQty} serial number(s)`); return; } const result = await onRestock(restockProduct.product_id, { quantity: Number(restockQty), supplier: supplier.trim() || null, reference: reference.trim() || null, variant_id: restockVariant || null, serial_numbers: serialNumbers.length ? serialNumbers : null, unit_cost: restockUnitCost !== "" ? Number(restockUnitCost) : null });     if (result) { setRestockProduct(null); setRestockQty(1); setSupplier(""); setReference(""); setRestockVariant(""); setRestockSerials(""); setRestockUnitCost(""); } };const saveTransfer = async () => { if (!transferProduct || !transferTo) return; const result = await onTransfer({ to_store_id: transferTo, items: [{ product_id: transferProduct.product_id, variant_id: transferVariant || null, quantity: Number(transferQty) }] }); if (result) { setTransferProduct(null); setTransferTo(""); setTransferQty(1); setTransferVariant(""); } };const addSupplier = async () => { const name = supplier.trim(); if (!name) return; try { const created = await api.createSupplier(token, { name }); setSuppliers((current) => [...current.filter((row) => row.id !== created.id), created].sort((a, b) => a.name.localeCompare(b.name))); setSupplier(created.name); notify("Supplier added"); } catch (error) { notify(error.message || "Could not add supplier"); } };const restockStock = restockProduct?.variants?.length ? (restockProduct.variants.find((variant) => variant.variant_id === restockVariant)?.on_hand ?? 0) : restockProduct?.on_hand;const stockOf = (item) => item?.variants?.length ? item.variants.reduce((sum, variant) => sum + (Number(variant.on_hand) || 0), 0) : (Number(item?.on_hand) || 0);const stateOf = (item) => { const quantity = stockOf(item); return quantity === 0 ? "out" : quantity <= (item.reorder_point || 10) ? "low" : "healthy"; };const lowStock = inventory.filter((item) => stateOf(item) !== "healthy").length;  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Inventory health</h2><p className="mt-1 text-sm text-[#898a95]">Live stock balances for your selected store.</p></div><Button variant="outline" onClick={() => setSerialLookupOpen(true)}><Search size={15} /> Find a serial</Button><Button variant="outline" onClick={() => notify("Inventory is up to date") }><RefreshCw size={15} /> Sync inventory</Button></div>{error && <p className="mt-5 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2.5 text-xs text-[#c2564b]">{error}</p>}<div className="mt-7 grid gap-3 sm:grid-cols-3"><MetricCard label="Inventory value" value={formatCurrencyAmount(inventory.reduce((sum, item) => sum + Number(item.price) * stockOf(item), 0), baseCurrency)} change="Live" direction="up" tone="violet" icon={CircleDollarSign} detail="Current stock at store" /><MetricCard label="Total units" value={inventory.reduce((sum, item) => sum + stockOf(item), 0).toLocaleString()} change="Live" direction="up" tone="lime" icon={Boxes} detail="Across active products" /><MetricCard label="Needs attention" value={lowStock} change="View items" direction="alert" tone="yellow" icon={AlertTriangle} detail="Low or out of stock" /></div><div className="mt-5 rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-6"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><h3 className="text-sm font-extrabold">Stock levels</h3><p className="mt-1 text-[11px] text-[#999aa4]">Store inventory ledger · live data</p></div><div className="flex rounded-lg bg-[#f5f5f8] p-1">{["All stock", "Low stock"].map((item) => <button key={item} onClick={() => setFilter(item)} className={`rounded-md px-3 py-1.5 text-[10px] font-bold ${filter === item ? "bg-white text-[#4d4e57] shadow-sm" : "text-[#9697a0]"}`}>{item}</button>)}</div></div><div className="app-scrollbar mt-5 overflow-x-auto"><table className="mobile-table w-full border-collapse text-left"><thead><tr className="border-y border-[#f0f0f3] text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]"><th className="py-3 pl-2 font-bold">Product</th><th className="px-4 py-3 font-bold">On hand</th><th className="px-4 py-3 font-bold">Reorder point</th><th className="px-4 py-3 font-bold">Stock value</th><th className="px-4 py-3 font-bold">Status</th><th className="px-4 py-3 text-right font-bold">Action</th></tr></thead><tbody>{filtered.map((product) => <tr key={product.product_id} className="border-b border-[#f2f2f5] last:border-0"><td className="py-3.5 pl-2"><div className="flex items-center gap-3">{product.image ? <img src={product.image} alt={product.product_name} className="h-8 w-8 shrink-0 rounded-lg object-cover" /> : <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#ded9fb] text-[9px] font-extrabold text-[#5144c7]">{product.product_name.slice(0, 2).toUpperCase()}</div>}<div><p className="text-xs font-bold">{product.product_name}</p><p className="mt-0.5 text-[10px] text-[#a1a2ab]">{product.sku}</p></div></div></td><td className="px-4 py-3.5"><div className="flex items-center gap-3"><span className={`w-8 text-xs font-extrabold ${stateOf(product) === "healthy" ? "text-[#36373f]" : "text-[#bd8624]"}`}>{stockOf(product)}</span><div className="h-1.5 w-20 overflow-hidden rounded-full bg-[#eff0f3]"><div className={`h-full rounded-full ${stateOf(product) === "healthy" ? "bg-[#8cc762]" : "bg-[#e1b350]"}`} style={{ width: `${Math.min(stockOf(product) / Math.max(product.reorder_point * 5, 1) * 100, 100)}%` }} /></div></div></td><td className="px-4 py-3.5 text-xs text-[#777883]">{product.reorder_point}</td><td className="px-4 py-3.5 text-xs font-bold">{formatCurrencyAmount(Number(product.price) * stockOf(product), baseCurrency)}</td><td className="px-4 py-3.5"><Badge tone={stateOf(product) === "healthy" ? "green" : stateOf(product) === "out" ? "red" : "yellow"} dot>{stateOf(product) === "healthy" ? "Healthy" : stateOf(product) === "out" ? "Out of stock" : "Low stock"}</Badge></td><td className="px-4 py-3.5 text-right"><div className="flex items-center justify-end gap-1.5">{stores.length > 0 && stockOf(product) > 0 && <IconButton label="Transfer to another store" onClick={() => { setTransferProduct(product); setTransferTo(stores[0].id); setTransferQty(1); setTransferVariant(product.variants?.[0]?.variant_id || ""); }}><ArrowRightLeft size={15} /></IconButton>}<IconButton label="Receive stock" onClick={() => { setRestockProduct(product); setRestockVariant(product.variants?.[0]?.variant_id || ""); }}><Truck size={15} /></IconButton><IconButton label="Adjust stock" onClick={() => { setAdjustProduct(product); setAdjustValue(product.on_hand); setAdjustVariant(product.variants?.[0]?.variant_id || ""); }}><Settings2 size={15} /></IconButton></div></td></tr>)}</tbody></table></div></div><Modal open={Boolean(adjustProduct)} onClose={() => setAdjustProduct(null)} title="Adjust stock" description={adjustProduct ? `Update ${adjustProduct.product_name} balance.` : ""} dismissOnBackdrop={false}><div className="flex items-center gap-3 rounded-xl bg-[#f7f7fa] p-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ded9fb] text-[10px] font-extrabold text-[#5144c7]">{adjustProduct?.product_name.slice(0, 2).toUpperCase()}</div><div><p className="text-xs font-bold">{adjustProduct?.product_name}</p><p className="mt-0.5 text-[10px] text-[#92939d]">Current stock: {adjustProduct?.on_hand} units</p></div></div>{adjustProduct?.variants?.length > 0 && <label className="mt-4 block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Variant</span><Dropdown value={adjustVariant} onChange={(v) => { setAdjustVariant(v); const match = adjustProduct.variants.find((item) => item.variant_id === v); if (match) setAdjustValue(match.on_hand); }} options={adjustProduct.variants.map((variant) => ({ value: String(variant.variant_id), label: `${variant.name} (${variant.on_hand})` }))} /></label>}<label className="mt-5 block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">New quantity</span><input type="number" min="0" value={adjustValue} onChange={(event) => setAdjustValue(event.target.value)} className="h-11 w-full rounded-xl border border-[#dfdfe8] px-3.5 text-sm outline-none focus:border-[#887bf3]" /></label><div className="mt-5 flex gap-2"><Button variant="outline" className="flex-1" onClick={() => setAdjustProduct(null)}>Cancel</Button><Button className="flex-1" onClick={saveAdjustment} disabled={loading}>{loading ? "Saving..." : "Save adjustment"} <Check size={15} /></Button></div></Modal><Modal open={Boolean(restockProduct)} onClose={() => setRestockProduct(null)} title="Receive stock" description={restockProduct ? `Restock ${restockProduct.product_name}.` : ""} width="max-w-[560px]" dismissOnBackdrop={false}><div className="flex items-center gap-3 rounded-xl bg-[#f7f7fa] p-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#eaf4ff] text-[#3579b8]"><Truck size={16} /></div><div className="min-w-0 flex-1"><p className="text-xs font-bold">{restockProduct?.product_name}</p><p className="mt-0.5 text-[10px] text-[#92939d]">Current stock: {restockStock ?? 0} units</p></div></div>{restockProduct?.variants?.length > 0 && <label className="mt-4 block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Variant</span><Dropdown value={restockVariant} onChange={(v) => setRestockVariant(v)} options={restockProduct.variants.map((variant) => ({ value: String(variant.variant_id), label: `${variant.name} (${variant.on_hand})` }))} /></label>}<div className="mt-5 space-y-4"><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Quantity to receive</span><input type="number" min="1" value={restockQty} onChange={(event) => setRestockQty(event.target.value)} className="h-11 w-full rounded-xl border border-[#dfdfe8] px-3.5 text-sm outline-none focus:border-[#887bf3]" /></label><div className="grid gap-4 sm:grid-cols-2"><Field label="Supplier" value={supplier} onChange={(event) => setSupplier(event.target.value)} placeholder="e.g. Bean Brothers" list="chmaba-suppliers" /><Field label="Reference" value={reference} onChange={(event) => setReference(event.target.value)} placeholder="PO or invoice #" /></div><datalist id="chmaba-suppliers">{suppliers.map((row) => <option key={row.id} value={row.name} />)}</datalist>{supplier.trim() && !suppliers.some((row) => row.name.toLowerCase() === supplier.trim().toLowerCase()) && <button type="button" onClick={addSupplier} className="mt-1.5 text-xs font-semibold text-[#6957f5]">+ Add "{supplier.trim()}" as a new supplier</button>}{restockProduct?.track_serials && <label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Serial numbers (one per unit)</span><textarea value={restockSerials} onChange={(event) => setRestockSerials(event.target.value)} rows={3} placeholder="Scan or type one serial per unit" className="w-full rounded-xl border border-[#dfdfe8] px-3.5 py-2.5 text-sm outline-none focus:border-[#887bf3]" /></label>}<label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Unit cost (optional)</span><input value={restockUnitCost} onChange={(event) => setRestockUnitCost(event.target.value)} type="number" min="0" step="0.01" placeholder="Cost per unit" className="h-11 w-full rounded-xl border border-[#dfdfe8] px-3.5 text-sm outline-none focus:border-[#887bf3]" /></label></div><div className="mt-5 flex gap-2"><Button variant="outline" className="flex-1" onClick={() => setRestockProduct(null)}>Cancel</Button><Button className="flex-1" onClick={saveRestock} disabled={loading || !(Number(restockQty) > 0)}>{loading ? "Saving..." : "Receive stock"} <Check size={15} /></Button></div></Modal>{serialLookupOpen && <SerialLookupModal token={token} storeId={storeId} onClose={() => setSerialLookupOpen(false)} />}<Modal open={Boolean(transferProduct)} onClose={() => setTransferProduct(null)} title="Transfer stock" description={transferProduct ? `Move ${transferProduct.product_name} to another store.` : ""} width="max-w-[560px]" dismissOnBackdrop={false}><div className="flex items-center gap-3 rounded-xl bg-[#f7f7fa] p-3"><div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#efe9ff] text-[#6957f5]"><ArrowRightLeft size={16} /></div><div className="min-w-0 flex-1"><p className="text-xs font-bold">{transferProduct?.product_name}</p><p className="mt-0.5 text-[10px] text-[#92939d]">Current stock: {transferProduct?.on_hand} units</p></div></div><div className="mt-5 space-y-4">{transferProduct?.variants?.length > 0 && <label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Variant</span><Dropdown value={transferVariant} onChange={setTransferVariant} options={transferProduct.variants.map((variant) => ({ value: String(variant.variant_id), label: `${variant.name} (${variant.on_hand})` }))} /></label>}<label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Destination store</span><Dropdown value={transferTo} onChange={setTransferTo} options={stores.map((store) => ({ value: store.id, label: store.name }))} /></label><label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Quantity to transfer</span><input type="number" min="1" max={(transferVariant ? transferProduct?.variants?.find((variant) => variant.variant_id === transferVariant)?.on_hand : transferProduct?.on_hand) || 1} value={transferQty} onChange={(event) => setTransferQty(event.target.value)} className="h-11 w-full rounded-xl border border-[#dfdfe8] px-3.5 text-sm outline-none focus:border-[#887bf3]" /></label></div><div className="mt-5 flex gap-2"><Button variant="outline" className="flex-1" onClick={() => setTransferProduct(null)}>Cancel</Button><Button className="flex-1" onClick={saveTransfer} disabled={loading || !transferTo || !(Number(transferQty) > 0)}>{loading ? "Saving..." : "Transfer stock"} <ArrowRightLeft size={14} /></Button></div></Modal>{suppliersOpen && <SuppliersModal onClose={() => setSuppliersOpen(false)} token={token} notify={notify} />}{purchasesOpen && <PurchaseOrderModal onClose={() => setPurchasesOpen(false)} token={token} storeId={storeId} notify={notify} onChanged={onSync} />}</div>;}

function LiveCategoriesView({ token, notify }) {  const [categories, setCategories] = useState([]);
const [modal, setModal] = useState({ open: false, category: null });
const [deleteTarget, setDeleteTarget] = useState(null);
const [toggleTarget, setToggleTarget] = useState(null);  const load = async () => { try { setCategories(await api.categories(token)); } catch { /* ignore */ } };  useEffect(() => { load(); }, [token]);  const parents = categories.filter((category) => !category.parent_id);  const childrenOf = (parentId) => categories.filter((category) => category.parent_id === parentId);  const parentName = (parentId) => categories.find((category) => category.id === parentId)?.name || "—";  const performDelete = async () => { const target = deleteTarget; setDeleteTarget(null); try { await api.deleteCategory(token, target.id); notify("Category deleted"); await load(); } catch (error) { notify(error.message || "Could not delete category"); } };const performToggle = async () => { const item = toggleTarget; if (!item) return; setToggleTarget(null); try { await api.updateCategory(token, item.id, { is_active: item.activate }); notify(item.activate ? "Category activated" : "Category deactivated"); await load(); } catch (error) { notify(error.message || "Could not update category"); } };const allRows = [...parents.map((parent) => ({ ...parent, kind: "Category" })), ...categories.filter((category) => category.parent_id).map((child) => ({ ...child, kind: "Subcategory" }))];  return <div className="mx-auto max-w-[1460px] p-5 lg:p-8"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><h2 className="text-2xl font-extrabold tracking-[-.05em]">Categories</h2><p className="mt-1 text-sm text-[#898a95]">Organize products into categories and subcategories.</p></div><Button onClick={() => setModal({ open: true, category: null })}><Plus size={16} /> Add category</Button></div><div className="mt-7 grid gap-3 sm:grid-cols-3"><SmallStat label="Categories" value={categories.length} detail="Total categories & subcategories" icon={Tag} tone="violet" /><SmallStat label="Top-level" value={parents.length} detail="Main categories" icon={Grid2X2} tone="green" /><SmallStat label="Subcategories" value={categories.filter((category) => category.parent_id).length} detail="Under a parent" icon={List} tone="yellow" /></div><div className="mt-5 rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-6"><div className="app-scrollbar overflow-x-auto"><table className="mobile-table w-full border-collapse text-left"><thead><tr className="border-y border-[#f0f0f3] text-[10px] font-bold uppercase tracking-wide text-[#a1a2ab]"><th className="py-3 pl-2 font-bold">Name</th><th className="px-4 py-3 font-bold">Type</th><th className="px-4 py-3 font-bold">Parent</th><th className="px-4 py-3 font-bold">Subcategories</th><th className="px-4 py-3 font-bold">Status</th><th className="w-32 px-2 py-3 text-right font-bold">Actions</th></tr></thead><tbody>{allRows.length === 0 ? <tr><td colSpan="6" className="py-14 text-center text-sm text-[#92939d]">No categories yet. Add your first above.</td></tr> : allRows.map((category) => <tr key={category.id} className={`border-b border-[#f2f2f5] last:border-0 ${category.is_active === false ? "opacity-60" : ""}`}><td className="py-3.5 pl-2 text-xs font-extrabold text-[#34353d]">{category.name}</td><td className="px-4 py-3.5"><Badge tone={category.kind === "Category" ? "violet" : "blue"}>{category.kind}</Badge></td><td className="px-4 py-3.5 text-xs text-[#777883]">{category.kind === "Subcategory" ? parentName(category.parent_id) : "—"}</td><td className="px-4 py-3.5 text-xs text-[#777883]">{category.kind === "Category" ? childrenOf(category.id).length : "—"}</td><td className="px-4 py-3.5"><Badge tone={category.is_active === false ? "neutral" : "green"}>{category.is_active === false ? "Inactive" : "Active"}</Badge></td><td className="px-2 py-3.5"><div className="flex items-center justify-end gap-1"><IconButton label={category.is_active === false ? "Activate" : "Deactivate"} onClick={() => setToggleTarget({ id: category.id, name: category.name, activate: category.is_active === false })}>{category.is_active === false ? <ToggleLeft size={15} /> : <ToggleRight size={15} />}</IconButton><IconButton label="Rename category" onClick={() => setModal({ open: true, category })}><Edit3 size={15} /></IconButton><IconButton label="Delete category" onClick={() => setDeleteTarget(category)}><Trash2 size={15} /></IconButton></div></td></tr>)}</tbody></table></div></div>{modal.open && <CategoryFormModal token={token} category={modal.category} parentOptions={parents} onClose={() => setModal({ open: false, category: null })} onSaved={async () => { setModal({ open: false, category: null }); await load(); }} notify={notify} />}{toggleTarget && <ConfirmDialog open title={toggleTarget.activate ? `Activate ${toggleTarget.name}?` : `Deactivate ${toggleTarget.name}?`} message={toggleTarget.activate ? "This category can be used on products again." : "Deactivated categories stay for history but can't be assigned to new products."} confirmLabel={toggleTarget.activate ? "Activate" : "Deactivate"} onConfirm={performToggle} onCancel={() => setToggleTarget(null)} />}{deleteTarget && <ConfirmDialog open title={`Delete ${deleteTarget.name}?`} message="Products in this category become uncategorized, and subcategories become top-level." confirmLabel="Delete category" onConfirm={performDelete} onCancel={() => setDeleteTarget(null)} />}</div>;}

function CategoryFormModal({ token, category, parentOptions, onClose, onSaved, notify }) {  const [name, setName] = useState(category?.name || "");
const [parentId, setParentId] = useState(category?.parent_id || "");
const [busy, setBusy] = useState(false);
const [error, setError] = useState("");  const submit = async () => { if (!name.trim()) return; setBusy(true); setError(""); try { if (category) { await api.updateCategory(token, category.id, { name: name.trim() }); notify("Category updated"); } else { await api.createCategory(token, { name: name.trim(), parent_id: parentId || null }); notify("Category added"); } onSaved(); } catch (requestError) { setError(requestError.message || "Could not save category"); } finally { setBusy(false); } };  return <Modal open onClose={onClose} title={category ? "Rename category" : "Add category"} description={category ? "Give this category a new name." : "Create a top-level or sub-category."} width="max-w-[520px]" dismissOnBackdrop={false}><div className="space-y-3"><Field label="Name" required value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Coffee" />{!category && <label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Parent category (optional)</span><Dropdown value={parentId} onChange={(v) => setParentId(v)} options={[{ value: "", label: "Top-level" }, ...parentOptions.map((parent) => ({ value: String(parent.id), label: parent.name }))]} /></label>}{error && <p className="rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-xs text-[#c2564b]">{error}</p>}</div><div className="mt-5 flex gap-2"><Button variant="outline" className="flex-1" onClick={onClose}>Cancel</Button><Button className="flex-1" onClick={submit} disabled={busy || !name.trim()}>{busy ? "Saving..." : category ? "Save changes" : "Add category"} <Check size={15} /></Button></div></Modal>;}

function VariantsModal({ product, token, onSave, onUploadImage, onClose, notify }) {
  const existing = Array.isArray(product?.variants) ? product.variants : [];
  const [suggestions, setSuggestions] = useState({ keys: [], values: {}, variant_names: [], variant_skus: [] });
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const found = await api.attributeSuggestions(token);
        if (active) setSuggestions({ keys: found?.keys || [], values: found?.values || {}, variant_names: found?.variant_names || [], variant_skus: found?.variant_skus || [] });
      } catch { /* suggestions are optional */ }
    })();
    return () => { active = false; };
  }, [token]);
  const allAttrValues = [...new Set(Object.values(suggestions.values).flat())].sort();
  const attrsToRows = (attributes) => {
    const raw = attributes && typeof attributes === "object" ? attributes : {};
    return Object.entries(raw).map(([key, value]) => ({ key, value: value == null ? "" : String(value) }));
  };
  const [rows, setRows] = useState(() => existing.map((variant) => ({
    id: variant.id,
    sku: variant.sku,
    name: variant.name,
    image: variant.image || "",
    imageFile: null,
    price: variant.price != null ? String(variant.price) : "",
    costPrice: variant.cost_price != null ? String(variant.cost_price) : "",
    barcode: variant.barcode || "",
    openingStock: "",
    reorderPoint: variant.reorder_point != null ? String(variant.reorder_point) : "10",
    attributes: attrsToRows(variant.attributes),
    isNew: false,
  })));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [libraryRow, setLibraryRow] = useState(null);
  const update = (index, patch) => setRows(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  const add = () => setRows([...rows, { sku: "", name: "", image: "", imageFile: null, price: "", costPrice: "", barcode: "", openingStock: "", reorderPoint: "10", attributes: [], isNew: true }]);
  const remove = (index) => setRows(rows.filter((_, i) => i !== index));
  const readImage = (index, file) => { if (!file) return; const reader = new FileReader(); reader.onload = () => update(index, { image: String(reader.result), imageFile: file }); reader.readAsDataURL(file); };
  const updateAttribute = (rowIndex, attrIndex, patch) => setRows(rows.map((row, i) => (i === rowIndex ? { ...row, attributes: row.attributes.map((attr, j) => (j === attrIndex ? { ...attr, ...patch } : attr)) } : row)));
  const addAttribute = (rowIndex) => setRows(rows.map((row, i) => (i === rowIndex ? { ...row, attributes: [...row.attributes, { key: "", value: "" }] } : row)));
  const removeAttribute = (rowIndex, attrIndex) => setRows(rows.map((row, i) => (i === rowIndex ? { ...row, attributes: row.attributes.filter((_, j) => j !== attrIndex) } : row)));
  const submit = async () => {
    setBusy(true);
    setError("");
    const variants = rows.map((row) => {
      const attributes = row.attributes.reduce((acc, attr) => {
        const key = attr.key.trim();
        if (key) acc[key] = attr.value;
        return acc;
      }, {});
      return {
        id: row.id,
        sku: row.sku.trim(),
        name: row.name.trim(),
        image: (Boolean(row.imageFile) || String(row.image || "").startsWith("data:")) ? null : (row.image || null),
        barcode: row.barcode.trim() || null,
        price: row.price === "" ? null : Number(row.price),
        cost_price: row.costPrice === "" ? null : Number(row.costPrice),
        attributes: Object.keys(attributes).length ? attributes : null,
        opening_stock: product?.track_serials ? 0 : (Number(row.openingStock) || 0),
        reorder_point: Number(row.reorderPoint) || 10,
      };
    });
    if (variants.some((variant) => !variant.sku || !variant.name)) {
      setError("Each variant needs a SKU and a name");
      setBusy(false);
      return;
    }
    const seenSkus = new Set();
    const duplicateSku = variants.find((variant) => {
      if (seenSkus.has(variant.sku)) return true;
      seenSkus.add(variant.sku);
      return false;
    });
    if (duplicateSku) {
      setError(`Duplicate variant SKU: ${duplicateSku.sku}`);
      setBusy(false);
      return;
    }
    try {
      const saved = await onSave?.(product.id, { variants });
      if (saved) {
        // Local files upload after save, once each variant has an id.
        for (const row of rows.filter((item) => item.imageFile)) {
          const variantId = row.id || saved.variants?.find((item) => item.sku === row.sku.trim())?.id;
          if (variantId) await onUploadImage?.(product.id, variantId, row.imageFile);
        }
        onClose();
      }
    } catch (requestError) {
      setError(requestError.message || "Could not save variants");
    } finally {
      setBusy(false);
    }
  };
  return <Modal open onClose={onClose} title={`Variants · ${product.name}`} description="Sell one product in several combinations (e.g. color or storage), each with its own stock." width="max-w-[820px]" dismissOnBackdrop={false}><div className="space-y-3">
    {rows.length === 0 ? <p className="text-xs text-[#92939d]">No variants yet. Add one below.</p> : rows.map((row, index) => <div key={index} className="rounded-xl border border-[#e9e9ef] p-3">
      <div className="flex items-center justify-between"><span className="text-[11px] font-bold text-[#4f5059]">Variant {index + 1}</span><IconButton label="Remove variant" onClick={() => remove(index)}><Trash2 size={15} /></IconButton></div>
      <div className="mt-2 flex items-center gap-3 rounded-lg border border-[#ececf2] p-2">
        {row.image ? <img src={row.image} alt="" className="h-10 w-10 rounded-lg object-cover" /> : product?.image ? <img src={product.image} alt="" className="h-10 w-10 rounded-lg object-cover opacity-50" /> : <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#fafafd] text-[#a1a2ab]"><Package size={15} /></span>}
        <label className="text-[11px] font-semibold text-[#6957f5]"><input type="file" accept="image/*" className="hidden" onChange={(event) => readImage(index, event.target.files?.[0])} /><span className="cursor-pointer">{row.image ? "Replace image" : "Add image"}</span></label><button type="button" onClick={() => setLibraryRow((current) => (current === index ? null : index))} className="text-[11px] font-semibold text-[#6957f5]">{libraryRow === index ? "Hide" : "Choose"}</button>
        {!row.image && product?.image && <span className="text-[10px] text-[#92939d]">Uses product image</span>}
        {row.image && <IconButton label="Remove variant image" onClick={() => update(index, { image: "", imageFile: null })}><Trash2 size={13} /></IconButton>}
      </div>
      {libraryRow === index && <div className="mt-2 rounded-lg border border-[#e9e9ef] p-3"><MediaLibraryGrid token={token} notify={notify} maxHeightClass="max-h-[220px]" onPick={(url) => { setRows((current) => current.map((item, i) => (i === index ? { ...item, image: url, imageFile: null } : item))); setLibraryRow(null); }} /></div>}
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <input value={row.name} onChange={(event) => update(index, { name: event.target.value })} placeholder="Name (e.g. 256GB · Midnight)" list="chmaba-variant-names" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" />
        <input value={row.sku} onChange={(event) => update(index, { sku: event.target.value })} placeholder="SKU" list="chmaba-variant-skus" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" />
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        <input value={row.price} onChange={(event) => update(index, { price: event.target.value })} placeholder="Price override" type="number" min="0" step="0.01" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" />
        <input value={row.costPrice} onChange={(event) => update(index, { costPrice: event.target.value })} placeholder="Cost price" type="number" min="0" step="0.01" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" />
        <input value={row.reorderPoint} onChange={(event) => update(index, { reorderPoint: event.target.value })} placeholder="Reorder point" type="number" min="0" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" />
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <input value={row.barcode} onChange={(event) => update(index, { barcode: event.target.value })} placeholder="Barcode" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" />
        {!row.isNew ? <div className="flex h-10 items-center rounded-lg bg-[#fafafd] px-3 text-[11px] text-[#92939d]">In stock: {product?.variants?.find((item) => item.id === row.id)?.on_hand ?? 0}</div> : product?.track_serials ? <div className="flex h-10 items-center rounded-lg bg-[#fafafd] px-3 text-[11px] text-[#92939d]">Starts at 0 — add serials via Receive stock</div> : <input value={row.openingStock} onChange={(event) => update(index, { openingStock: event.target.value })} placeholder="Opening stock" type="number" min="0" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" />}
      </div>
      <div className="mt-2 rounded-lg bg-[#fafafd] p-2">
        <div className="flex items-center justify-between"><span className="text-[10px] font-bold text-[#4f5059]">Attributes (e.g. Color, Storage, RAM)</span><button type="button" onClick={() => addAttribute(index)} className="text-[10px] font-semibold text-[#6957f5]">+ Add</button></div>
        {row.attributes.length === 0 ? <p className="mt-1 text-[10px] text-[#92939d]">Optional labeled details, shown separately on receipts.</p> : <div className="mt-1 space-y-1">{row.attributes.map((attr, attrIndex) => <div key={attrIndex} className="flex items-center gap-1">
          <input value={attr.key} onChange={(event) => updateAttribute(index, attrIndex, { key: event.target.value })} placeholder="Key" list="chmaba-vattr-keys" className="h-8 min-w-0 flex-1 rounded-md border border-[#e7e7ed] px-2 text-[11px] outline-none focus:border-[#887bf3]" />
          <input value={attr.value} onChange={(event) => updateAttribute(index, attrIndex, { value: event.target.value })} placeholder="Value" list={`chmaba-vattr-${index}`} className="h-8 min-w-0 flex-1 rounded-md border border-[#e7e7ed] px-2 text-[11px] outline-none focus:border-[#887bf3]" />
          <IconButton label="Remove attribute" onClick={() => removeAttribute(index, attrIndex)}><Trash2 size={13} /></IconButton>
        </div>)}</div>}
      </div>
    </div>)}
    <button type="button" onClick={add} className="text-xs font-semibold text-[#6957f5]">+ Add variant</button>
    {error && <p className="rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-xs text-[#c2564b]">{error}</p>}
  </div><div className="mt-5 flex gap-2"><Button variant="outline" className="flex-1" onClick={onClose}>Cancel</Button><Button className="flex-1" onClick={submit} disabled={busy}>{busy ? "Saving..." : "Save variants"} <Check size={15} /></Button></div><datalist id="chmaba-variant-names">{suggestions.variant_names.map((name) => <option key={name} value={name} />)}</datalist><datalist id="chmaba-variant-skus">{suggestions.variant_skus.map((sku) => <option key={sku} value={sku} />)}</datalist><datalist id="chmaba-vattr-keys">{suggestions.keys.map((key) => <option key={key} value={key} />)}</datalist>{rows.map((row, index) => <datalist key={`vdl-${index}`} id={`chmaba-vattr-${index}`}>{allAttrValues.map((value) => <option key={value} value={value} />)}</datalist>)}</Modal>;
}

function SerialsModal({ product, onLoad, onAdd, onUpdate, onLoadTickets, onCreateTicket, onClose, notify }) {
  const variants = Array.isArray(product?.variants) ? product.variants : [];
  const [serials, setSerials] = useState([]);
  const [text, setText] = useState("");
  const [variantId, setVariantId] = useState("");
  const [warranty, setWarranty] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    (async () => {
      const rows = await onLoad?.(product.id);
      if (active) { setSerials(Array.isArray(rows) ? rows : []); setLoading(false); }
    })();
    return () => { active = false; };
  }, [product.id]);
  const add = async () => {
    const numbers = text.split(/[\n,]+/).map((value) => value.trim()).filter(Boolean);
    if (numbers.length === 0) return;
    setBusy(true);
    setError("");
    const warrantyMonths = warranty === "" ? null : Number(warranty);
    try {
      const created = await onAdd?.(product.id, { serials: numbers.map((serial_number) => ({ serial_number, variant_id: variantId || null, warranty_months: warrantyMonths })) });
      if (created) { setSerials((current) => [...created, ...current]); setText(""); notify(`${created.length} serial(s) added`); }
    } catch (requestError) {
      setError(requestError.message || "Could not add serials");
    } finally {
      setBusy(false);
    }
  };
  const variantName = (id) => variants.find((variant) => variant.id === id)?.name;
  const [openTickets, setOpenTickets] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [ticketsLoading, setTicketsLoading] = useState(false);
  const [ticketForm, setTicketForm] = useState({ summary: "" });
  const changeStatus = async (serial, status) => { if (!status || status === serial.status) return; setBusy(true); setError(""); try { const updated = await onUpdate?.(serial.id, { status }); if (updated) setSerials((current) => current.map((row) => (row.id === serial.id ? { ...row, ...updated } : row))); } catch (requestError) { setError(requestError.message || "Could not update serial"); } finally { setBusy(false); } };
  const viewTickets = async (serial) => { if (openTickets === serial.id) { setOpenTickets(null); return; } setOpenTickets(serial.id); setTicketsLoading(true); try { setTickets((await onLoadTickets?.(serial.id)) || []); } catch { setTickets([]); } finally { setTicketsLoading(false); } };
  const addTicket = async (serial) => { const summary = ticketForm.summary.trim(); if (!summary) return; setBusy(true); try { const created = await onCreateTicket?.(serial.id, { ticket_type: "repair", summary }); if (created) { setTickets((current) => [created, ...current]); setTicketForm({ summary: "" }); } } catch (requestError) { setError(requestError.message || "Could not create ticket"); } finally { setBusy(false); } };
  return <Modal open onClose={onClose} title={`Serials · ${product.name}`} description="Track individual units by serial number or IMEI." width="max-w-[520px]" dismissOnBackdrop={false}><div className="space-y-3">
    {variants.length > 0 && <label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Variant (color / storage)</span><Dropdown value={variantId} onChange={setVariantId} options={[{ value: "", label: "No specific variant" }, ...variants.map((variant) => ({ value: String(variant.id), label: variant.name }))]} /></label>}
    <label className="block"><span className="mb-1.5 block text-xs font-semibold text-[#4f5059]">Warranty months (optional)</span><input value={warranty} onChange={(event) => setWarranty(event.target.value)} type="number" min="0" placeholder="e.g. 12" className="h-10 w-full rounded-xl border border-[#dfdfe8] px-3 text-sm outline-none focus:border-[#887bf3]" /></label>
    <textarea value={text} onChange={(event) => setText(event.target.value)} rows={3} placeholder="One serial or IMEI per line" className="w-full rounded-xl border border-[#dfdfe8] px-3.5 py-2.5 text-sm outline-none focus:border-[#887bf3]" />
    <div className="flex justify-end"><Button onClick={add} disabled={busy || !text.trim()}>{busy ? "Adding..." : "Add serials"} <Check size={15} /></Button></div>
    {error && <p className="rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-xs text-[#c2564b]">{error}</p>}
    <div className="max-h-72 space-y-1 overflow-y-auto">{loading ? <p className="text-xs text-[#92939d]">Loading...</p> : serials.length === 0 ? <p className="text-xs text-[#92939d]">No serials tracked yet.</p> : serials.map((serial) => <div key={serial.id} className="rounded-lg bg-[#fafafd] px-3 py-2 text-xs"><div className="flex items-center justify-between gap-2"><span className="min-w-0"><span className="font-semibold text-[#4d4e57]">{serial.serial_number}</span>{variantName(serial.variant_id) && <span className="ml-2 text-[10px] text-[#92939d]">{variantName(serial.variant_id)}</span>}{serial.warranty_until && <span className="ml-2 text-[10px] font-semibold text-[#9e7628]">Warranty to {new Date(serial.warranty_until).toLocaleDateString()}</span>}</span><span className="flex shrink-0 items-center gap-1"><Dropdown value={serial.status} onChange={(value) => changeStatus(serial, value)} triggerClass="h-7 rounded-lg border border-[#e1e1e8] bg-white px-2 text-[10px] font-bold text-[#292a31]" options={[{ value: "in_stock", label: "In stock" }, { value: "sold", label: "Sold", disabled: true }, { value: "returned", label: "Returned" }, { value: "defective", label: "Defective" }]} /><button type="button" onClick={() => viewTickets(serial)} className="rounded-md px-2 py-1 text-[10px] font-bold text-[#6957f5] hover:bg-[#f0eefe]">{openTickets === serial.id ? "Hide service" : "Service"}</button></span></div>{openTickets === serial.id && <div className="mt-2 space-y-2 border-t border-[#ececf1] pt-2">{ticketsLoading ? <p className="text-[10px] text-[#92939d]">Loading tickets...</p> : tickets.length === 0 ? <p className="text-[10px] text-[#92939d]">No service tickets yet.</p> : <div className="space-y-1">{tickets.map((ticket) => <div key={ticket.id} className="flex items-center justify-between rounded-md bg-white px-2 py-1 text-[10px]"><span className="min-w-0 truncate font-semibold text-[#4d4e57]">{ticket.summary}</span><span className="ml-2 shrink-0 text-[#92939d]">{ticket.ticket_type} / {ticket.status}</span></div>)}</div>}<div className="flex gap-1"><input value={ticketForm.summary} onChange={(event) => setTicketForm({ summary: event.target.value })} placeholder="New ticket summary" className="h-8 min-w-0 flex-1 rounded-md border border-[#dfdfe8] px-2 text-[11px] outline-none focus:border-[#887bf3]" /><Button onClick={() => addTicket(serial)} disabled={busy || !ticketForm.summary.trim()}>Add</Button></div></div>}</div>)}</div>
  </div><div className="mt-5 flex justify-end"><Button variant="outline" onClick={onClose}>Close</Button></div></Modal>;
}

function SerialLookupModal({ token, storeId, onClose }) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [ticketsLoading, setTicketsLoading] = useState(false);
  const [ticketForm, setTicketForm] = useState({ ticket_type: "repair", summary: "", cost: "" });
  const [ticketBusy, setTicketBusy] = useState(false);
  const [ticketError, setTicketError] = useState("");
  const search = async () => {
    setLoading(true);
    setError("");
    setOpenId(null);
    try {
      const term = query.trim();
      setRows(await api.serialLookup(token, term ? { query: term } : {}));
    } catch (requestError) {
      setError(requestError.message || "Could not search serials");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { search(); }, []);
  const loadTickets = async (serialId) => {
    setTicketsLoading(true);
    setTicketError("");
    try {
      setTickets(await api.serialTickets(token, serialId));
    } catch (requestError) {
      setTicketError(requestError.message || "Could not load service history");
    } finally {
      setTicketsLoading(false);
    }
  };
  const toggleOpen = (serialId) => {
    if (openId === serialId) { setOpenId(null); return; }
    setOpenId(serialId);
    setTickets([]);
    setTicketForm({ ticket_type: "repair", summary: "", cost: "" });
    loadTickets(serialId);
  };
  const addTicket = async () => {
    if (!ticketForm.summary.trim()) return;
    setTicketBusy(true);
    setTicketError("");
    try {
      await api.createSerialTicket(token, storeId, openId, { ticket_type: ticketForm.ticket_type, summary: ticketForm.summary.trim(), cost: ticketForm.cost === "" ? null : Number(ticketForm.cost) });
      setTicketForm({ ticket_type: "repair", summary: "", cost: "" });
      await loadTickets(openId);
    } catch (requestError) {
      setTicketError(requestError.message || "Could not add ticket");
    } finally {
      setTicketBusy(false);
    }
  };
  const resolveTicket = async (ticketId) => {
    try {
      await api.updateSerialTicket(token, storeId, ticketId, { status: "resolved" });
      await loadTickets(openId);
    } catch (requestError) {
      setTicketError(requestError.message || "Could not update ticket");
    }
  };
  const tone = { in_stock: "green", sold: "blue", returned: "yellow", defective: "red" };
  return <Modal open onClose={onClose} title="Find a serial" description="Search by serial number or IMEI to see the unit, its sale, warranty and service history." width="max-w-[620px]">
    <div className="flex gap-2">
      <input autoFocus value={query} onChange={(event) => { setQuery(event.target.value); setError(""); }} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); search(); } }} placeholder="Serial or IMEI" className="h-11 min-w-0 flex-1 rounded-xl border border-[#dfdfe8] px-3.5 text-sm outline-none focus:border-[#887bf3]" />
      <Button onClick={search} disabled={loading}>{loading ? "Searching..." : "Search"}</Button>
    </div>
    {error && <p className="mt-3 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-xs text-[#c2564b]">{error}</p>}
    <div className="mt-4 max-h-80 space-y-2 overflow-y-auto">
      {rows.length === 0 ? <p className="text-xs text-[#92939d]">{loading ? "Loading..." : "No serials found."}</p> : rows.map((row) => <div key={row.id} className="rounded-xl border border-[#ececf1] p-3 text-xs">
        <div className="flex items-center justify-between gap-3"><span className="font-bold text-[#34353d]">{row.serial_number}</span><Badge tone={tone[row.status] || "yellow"}>{row.status.replace("_", " ")}</Badge></div>
        <p className="mt-1 text-[#6b6c76]">{row.product_name}{row.variant_name ? ` · ${row.variant_name}` : ""}</p>
        {row.imei && <p className="text-[#92939d]">IMEI: {row.imei}</p>}
        {row.order_number && <p className="text-[#92939d]">Sold on {row.order_number}{row.customer_name ? ` · ${row.customer_name}` : ""}</p>}
        {row.warranty_until && <p className="text-[#92939d]">Warranty until {new Date(row.warranty_until).toLocaleDateString()}</p>}
        <button type="button" onClick={() => toggleOpen(row.id)} className="mt-2 text-[11px] font-semibold text-[#6957f5]">{openId === row.id ? "Hide service history" : "Service history"}</button>
        {openId === row.id && <div className="mt-2 border-t border-[#f0f0f3] pt-2">
          {ticketsLoading ? <p className="text-[#92939d]">Loading...</p> : tickets.length === 0 ? <p className="text-[#92939d]">No service history yet.</p> : <div className="space-y-1">{tickets.map((ticket) => <div key={ticket.id} className="flex items-center justify-between gap-2 rounded-lg bg-[#fafafd] px-2 py-1.5"><span className="min-w-0"><span className="font-semibold text-[#4d4e57]">{ticket.summary}</span> <span className="text-[#92939d]">{ticket.ticket_type} · {ticket.status}{ticket.cost != null ? ` · ${ticket.cost}` : ""}</span></span>{ticket.status !== "resolved" && <button type="button" onClick={() => resolveTicket(ticket.id)} className="shrink-0 text-[10px] font-semibold text-[#3579b8]">Resolve</button>}</div>)}</div>}
          <div className="mt-2 space-y-1">
            <div className="flex gap-1">
              <select value={ticketForm.ticket_type} onChange={(event) => setTicketForm({ ...ticketForm, ticket_type: event.target.value })} className="h-8 rounded-md border border-[#e7e7ed] px-2 text-[11px] text-[#4f5059]"><option value="repair">Repair</option><option value="warranty">Warranty</option><option value="inspection">Inspection</option></select>
              <input value={ticketForm.cost} onChange={(event) => setTicketForm({ ...ticketForm, cost: event.target.value })} placeholder="Cost" type="number" min="0" step="0.01" className="h-8 w-20 rounded-md border border-[#e7e7ed] px-2 text-[11px] outline-none focus:border-[#887bf3]" />
            </div>
            <input value={ticketForm.summary} onChange={(event) => setTicketForm({ ...ticketForm, summary: event.target.value })} placeholder="What needs doing?" className="h-8 w-full rounded-md border border-[#e7e7ed] px-2 text-[11px] outline-none focus:border-[#887bf3]" />
            <div className="flex justify-end"><Button size="xs" onClick={addTicket} disabled={ticketBusy || !ticketForm.summary.trim()}>{ticketBusy ? "Adding..." : "Add ticket"}</Button></div>
          </div>
          {ticketError && <p className="mt-1 text-[10px] text-[#c2564b]">{ticketError}</p>}
        </div>}
      </div>)}
    </div>
    <div className="mt-5 flex justify-end"><Button variant="outline" onClick={onClose}>Close</Button></div>
  </Modal>;
}

function ModifiersModal({ groups, onLoad, onCreate, onUpdate, onDelete, onClose, notify }) {
  const [rows, setRows] = useState(Array.isArray(groups) ? groups : []);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    (async () => { const loaded = await onLoad?.(); if (active && Array.isArray(loaded)) setRows(loaded); })();
    return () => { active = false; };
  }, []);
  const startNew = () => setForm({ id: null, name: "", modifiers: [{ name: "", price_delta: "0.00" }] });
  const startEdit = (group) => setForm({ id: group.id, name: group.name, modifiers: (group.modifiers || []).map((modifier) => ({ name: modifier.name, price_delta: String(modifier.price_delta) })) });
  const updateModifier = (index, patch) => setForm((current) => ({ ...current, modifiers: current.modifiers.map((row, i) => (i === index ? { ...row, ...patch } : row)) }));
  const addModifier = () => setForm((current) => ({ ...current, modifiers: [...current.modifiers, { name: "", price_delta: "0.00" }] }));
  const removeModifier = (index) => setForm((current) => ({ ...current, modifiers: current.modifiers.filter((_, i) => i !== index) }));
  const save = async () => {
    if (!form?.name.trim()) return;
    setBusy(true);
    const body = { name: form.name.trim(), min_select: 0, max_select: 1, is_required: false, modifiers: form.modifiers.filter((row) => row.name.trim()).map((row) => ({ name: row.name.trim(), price_delta: Number(row.price_delta) || 0 })) };
    const saved = form.id ? await onUpdate?.(form.id, body) : await onCreate?.(body);
    setBusy(false);
    if (saved) { setRows((current) => (form.id ? current.map((row) => (row.id === saved.id ? saved : row)) : [...current, saved])); setForm(null); }
  };
  const remove = async (group) => { const ok = await onDelete?.(group.id); if (ok) setRows((current) => current.filter((row) => row.id !== group.id)); };
  return <Modal open onClose={onClose} title="Modifier groups" description="Add-ons like milk or extra shots." width="max-w-[640px]" dismissOnBackdrop={false}>{form ? <div className="space-y-3"><Field label="Group name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="e.g. Milk" /><div className="space-y-2">{form.modifiers.map((row, index) => <div key={index} className="grid grid-cols-[1fr_90px_auto] gap-2"><input value={row.name} onChange={(event) => updateModifier(index, { name: event.target.value })} placeholder="Option" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" /><input value={row.price_delta} onChange={(event) => updateModifier(index, { price_delta: event.target.value })} placeholder="+0.00" type="number" step="0.01" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" /><IconButton label="Remove option" onClick={() => removeModifier(index)}><Trash2 size={15} /></IconButton></div>)}<button type="button" onClick={addModifier} className="text-xs font-semibold text-[#6957f5]">+ Add option</button></div><div className="flex gap-2"><Button variant="outline" className="flex-1" onClick={() => setForm(null)}>Cancel</Button><Button className="flex-1" onClick={save} disabled={busy || !form.name.trim()}>{busy ? "Saving..." : "Save group"}</Button></div></div> : <div className="space-y-2">{rows.length === 0 ? <p className="text-xs text-[#92939d]">No modifier groups yet.</p> : rows.map((group) => <div key={group.id} className="flex items-center justify-between rounded-lg bg-[#fafafd] px-3 py-2 text-xs"><span className="font-semibold text-[#4d4e57]">{group.name} <span className="font-normal text-[#92939d]">({(group.modifiers || []).length})</span></span><span className="flex items-center gap-1"><IconButton label="Edit group" onClick={() => startEdit(group)}><Edit3 size={15} /></IconButton><IconButton label="Delete group" onClick={() => remove(group)}><Trash2 size={15} /></IconButton></span></div>)}<button type="button" onClick={startNew} className="text-xs font-semibold text-[#6957f5]">+ Add group</button></div>}</Modal>;
}

function BatchesModal({ product, onLoad, onAdd, onClose, notify }) {
  const [batches, setBatches] = useState([]);
  const [code, setCode] = useState("");
  const [expiry, setExpiry] = useState("");
  const [qty, setQty] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { let active = true; (async () => { const rows = await onLoad?.(product.id); if (active) setBatches(Array.isArray(rows) ? rows : []); })(); return () => { active = false; }; }, [product.id]);
  const add = async () => {
    setBusy(true); setError("");
    try {
      const created = await onAdd?.(product.id, { batches: [{ batch_code: code.trim() || null, expiry_date: expiry || null, quantity_on_hand: Number(qty) || 0 }] });
      if (created) { setBatches((current) => [...created, ...current]); setCode(""); setExpiry(""); setQty(""); notify(`${created.length} batch(es) added`); }
    } catch (requestError) { setError(requestError.message || "Could not add batch"); } finally { setBusy(false); }
  };
  return <Modal open onClose={onClose} title={`Batches · ${product.name}`} description="Track stock by batch and expiry date." width="max-w-[560px]" dismissOnBackdrop={false}><div className="grid grid-cols-[1fr_130px_90px] gap-2"><input value={code} onChange={(event) => setCode(event.target.value)} placeholder="Batch code" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" /><input value={expiry} onChange={(event) => setExpiry(event.target.value)} type="date" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" /><input value={qty} onChange={(event) => setQty(event.target.value)} placeholder="Qty" type="number" min="0" className="h-10 min-w-0 rounded-lg border border-[#dfdfe8] px-3 text-xs outline-none focus:border-[#887bf3]" /></div><div className="mt-2 flex justify-end"><Button onClick={add} disabled={busy || !qty}>{busy ? "Adding..." : "Add batch"} <Check size={15} /></Button></div>{error && <p className="mt-3 rounded-xl border border-[#ffd7d2] bg-[#fff5f3] px-3 py-2 text-xs text-[#c2564b]">{error}</p>}<div className="mt-4 max-h-56 space-y-1 overflow-y-auto">{batches.length === 0 ? <p className="text-xs text-[#92939d]">No batches tracked yet.</p> : batches.map((batch) => <div key={batch.id} className="flex items-center justify-between rounded-lg bg-[#fafafd] px-3 py-2 text-xs"><span className="font-semibold text-[#4d4e57]">{batch.batch_code || "—"}</span><span className="text-[#92939d]">{batch.expiry_date || "no expiry"} · {batch.quantity_on_hand} left</span></div>)}</div><div className="mt-5 flex justify-end"><Button variant="outline" onClick={onClose}>Close</Button></div></Modal>;
}

export {
  ProductFormModal,
  VariantsModal,
  SerialsModal,
  SerialLookupModal,
  ModifiersModal,
  BatchesModal,
  LiveCatalogView,
  LiveInventoryView,
  LiveCategoriesView,
  CategoryFormModal,
};
