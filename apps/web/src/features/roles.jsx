import { useEffect, useState } from "react";
import { ShieldCheck, Plus, Pencil, Trash2, Check } from "lucide-react";
import { Button, Badge, Modal, Field } from "../components/ui";
import { api } from "../api";

// Role and permission editor. Lists the company's roles (built-in + custom) and
// lets an owner with the team.manage permission create/edit custom roles. The
// permission catalog is grouped exactly as the API returns it.
export function RolesCard({ token, notify, onRolesChanged }) {
  const [roles, setRoles] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [roleRows, permissionRows] = await Promise.all([api.roles(token), api.permissions(token)]);
      setRoles(Array.isArray(roleRows) ? roleRows : []);
      setCatalog(Array.isArray(permissionRows) ? permissionRows : []);
    } catch (error) {
      notify(error.message || "Could not load roles");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { if (token) load(); }, [token]);

  const groups = catalog.reduce((acc, row) => {
    (acc[row.group] = acc[row.group] || []).push(row);
    return acc;
  }, {});

  const openNew = () => setEditing({ id: null, name: "", permissions: [] });
  const openEdit = (role) => setEditing({ id: role.id, name: role.name, permissions: [...role.permissions], is_system: role.is_system, key: role.key });
  const toggle = (key) => setEditing((current) => ({
    ...current,
    permissions: current.permissions.includes(key) ? current.permissions.filter((value) => value !== key) : [...current.permissions, key],
  }));
  const save = async () => {
    if (!editing || !editing.name.trim()) return;
    setBusy(true);
    try {
      const body = { name: editing.name.trim(), permissions: editing.permissions };
      if (editing.id) await api.updateRole(token, editing.id, body);
      else await api.createRole(token, body);
      notify("Role saved");
      setEditing(null);
      await load();
      onRolesChanged?.();
    } catch (error) {
      notify(error.message || "Could not save the role");
    } finally {
      setBusy(false);
    }
  };
  const remove = async (role) => {
    if (typeof window !== "undefined" && !window.confirm(`Delete the ${role.name} role?`)) return;
    try {
      await api.deleteRole(token, role.id);
      notify("Role deleted");
      await load();
      onRolesChanged?.();
    } catch (error) {
      notify(error.message || "Could not delete the role");
    }
  };

  return (
    <div className="mt-5 rounded-2xl border border-[#e9e9ef] bg-white p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-extrabold">Roles & permissions</h3>
          <p className="mt-1 text-[11px] text-[#999aa4]">Choose exactly what each role can do. Built-in roles are always available.</p>
        </div>
        <Button size="sm" onClick={openNew}><Plus size={15} /> New role</Button>
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {roles.map((role) => (
          <div key={role.id} className="rounded-xl border border-[#eef0f4] p-3">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <ShieldCheck size={15} className="text-[#6957f5]" />
                <span className="text-xs font-extrabold text-[#303139]">{role.name}</span>
              </div>
              {role.is_system ? <Badge tone="neutral">Built-in</Badge> : <Badge tone="violet">Custom</Badge>}
            </div>
            <p className="mt-1.5 text-[10px] text-[#999aa4]">{role.permissions.length} permission{role.permissions.length === 1 ? "" : "s"}</p>
            <div className="mt-3 flex gap-2">
              <Button variant="outline" size="xs" disabled={role.key === "owner"} onClick={() => openEdit(role)}><Pencil size={12} /> Edit</Button>
              {!role.is_system && <Button variant="ghost" size="xs" onClick={() => remove(role)}><Trash2 size={12} /> Delete</Button>}
            </div>
          </div>
        ))}
        {loading && roles.length === 0 && <p className="text-xs text-[#999aa4]">Loading roles...</p>}
      </div>

      <Modal open={Boolean(editing)} title={editing?.id ? `Edit ${editing?.name}` : "New role"} description="Tick the permissions this role grants." onClose={() => setEditing(null)} width="max-w-[680px]">
        {editing && (
          <div className="space-y-5 p-5">
            <Field label="Role name" required placeholder="e.g. Floor lead" value={editing.name} onChange={(event) => setEditing({ ...editing, name: event.target.value })} />
            <div className="app-scrollbar max-h-[46vh] space-y-4 overflow-y-auto pr-1">
              {Object.entries(groups).map(([group, rows]) => (
                <div key={group}>
                  <p className="text-[10px] font-bold uppercase tracking-[.1em] text-[#92939d]">{group}</p>
                  <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                    {rows.map((row) => (
                      <label key={row.key} className="flex items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-[#fafafd]">
                        <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[#6957f5]" checked={editing.permissions.includes(row.key)} onChange={() => toggle(row.key)} />
                        <span className="text-xs text-[#4f5059]">{row.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex justify-end gap-2 border-t border-[#eeeeF2] pt-4">
              <Button variant="outline" onClick={() => setEditing(null)}>Cancel</Button>
              <Button onClick={save} disabled={busy || !editing.name.trim()}><Check size={14} /> {busy ? "Saving..." : "Save role"}</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
