import { useState } from "react";
import { useCustomer } from "../../context/CustomerContext";
import { addressService } from "../../services/addressService";
import { useNotification } from "../../context/NotificationContext";
import Button from "../../components/common/Button";
import Input from "../../components/common/Input";
import Select from "../../components/common/Select";
import Modal from "../../components/common/Modal";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import EmptyState from "../../components/common/EmptyState";
import Skeleton from "../../components/common/Skeleton";
import { ADDRESS_LABELS } from "../../utils/constants";
import { validateAddress, isAddressValid } from "../../validations";

const BLANK = {
  label: "home",
  recipient_name: "",
  recipient_mobile: "",
  line1: "",
  line2: "",
  landmark: "",
  city: "Bengaluru",
  state: "Karnataka",
  pincode: "",
  delivery_instructions: "",
  is_default: false,
};

/** Address book: add, edit, delete and set default. */
export default function AddressesPage() {
  const { addresses, loading, refresh, profile } = useCustomer();
  const { notify } = useNotification();

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(BLANK);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [deleting, setDeleting] = useState(null);

  const set = (k) => (e) => {
    const value = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [k]: value }));
    // Clear the field's error as soon as it is edited.
    setFieldErrors((fe) => (fe[k] ? { ...fe, [k]: undefined } : fe));
  };

  const startAdd = () => {
    setEditing(null);
    setError(null);
    setFieldErrors({});
    setForm({
      ...BLANK,
      recipient_name: profile?.full_name || "",
      recipient_mobile: profile?.mobile_number || "",
    });
    setOpen(true);
  };

  const startEdit = (a) => {
    setEditing(a);
    setError(null);
    setFieldErrors({});
    setForm({ ...BLANK, ...a });
    setOpen(true);
  };

  const save = async () => {
    const problems = validateAddress(form);
    setFieldErrors(problems);
    if (!isAddressValid(problems)) return;

    setSaving(true);
    setError(null);
    try {
      const payload = { ...form };
      delete payload.id;
      delete payload.uid;
      delete payload.customer;
      delete payload.customer_name;
      delete payload.customer_mobile;
      delete payload.full_address;
      delete payload.label_display;
      if (editing) await addressService.update(editing.id, payload);
      else await addressService.create(payload);
      await refresh();
      notify.success(editing ? "Address updated" : "Address added");
      setOpen(false);
    } catch (e) {
      setError(e?.message || "Could not save that address");
    } finally {
      setSaving(false);
    }
  };

  const makeDefault = async (a) => {
    try {
      await addressService.setDefault(a.id);
      await refresh();
      notify.success("Default address updated");
    } catch (e) {
      notify.error(e?.message || "Could not set the default");
    }
  };

  const doDelete = async () => {
    try {
      await addressService.remove(deleting.id);
      await refresh();
      notify.info("Address removed");
    } catch (e) {
      notify.error(e?.message || "Could not remove that address");
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="container-page py-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Saved addresses</h1>
          <p className="mt-1 text-sm text-slate-600">Where your orders should arrive.</p>
        </div>
        <Button onClick={startAdd}>+ Add address</Button>
      </div>

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-2xl" />
          ))}
        </div>
      ) : !addresses.length ? (
        <EmptyState
          title="No addresses saved"
          description="Add one and it will be offered at checkout."
          action={<Button onClick={startAdd}>Add your first address</Button>}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {addresses.map((a) => (
            <article key={a.id} className="flex flex-col rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-sm font-bold text-slate-900">{a.recipient_name}</span>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-slate-600">
                  {a.label_display || a.label}
                </span>
                {a.is_default ? (
                  <span className="rounded bg-brand-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-brand-800">
                    Default
                  </span>
                ) : null}
              </div>
              <p className="mt-1.5 flex-1 text-sm leading-relaxed text-slate-600">{a.full_address}</p>
              <p className="mt-1 text-xs text-slate-500">{a.recipient_mobile}</p>
              {a.delivery_instructions ? (
                <p className="mt-1 text-[11px] italic text-slate-500">“{a.delivery_instructions}”</p>
              ) : null}

              <div className="mt-3 flex flex-wrap gap-1.5 border-t border-slate-100 pt-3">
                <Button size="sm" variant="secondary" onClick={() => startEdit(a)}>Edit</Button>
                {!a.is_default ? (
                  <Button size="sm" variant="ghost" onClick={() => makeDefault(a)}>Set default</Button>
                ) : null}
                <Button size="sm" variant="ghost" className="text-rose-600" onClick={() => setDeleting(a)}>
                  Delete
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Edit address" : "Add an address"}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)} disabled={saving}>Cancel</Button>
            <Button onClick={save} loading={saving}>Save address</Button>
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Select
            label="Label"
            options={ADDRESS_LABELS}
            value={form.label}
            onChange={set("label")}
          />
          <Input label="Full name" required value={form.recipient_name} onChange={set("recipient_name")} error={fieldErrors.recipient_name} />
          <Input label="Mobile" required value={form.recipient_mobile} onChange={set("recipient_mobile")} placeholder="+919876500000" error={fieldErrors.recipient_mobile} inputMode="tel" />
          <Input label="Pincode" required value={form.pincode} onChange={set("pincode")} inputMode="numeric" error={fieldErrors.pincode} />
          <Input label="Flat / house" required className="sm:col-span-2" value={form.line1} onChange={set("line1")} error={fieldErrors.line1} />
          <Input label="Street / area" className="sm:col-span-2" value={form.line2} onChange={set("line2")} />
          <Input label="Landmark" value={form.landmark} onChange={set("landmark")} />
          <Input label="City" required value={form.city} onChange={set("city")} error={fieldErrors.city} />
          <Input label="State" required value={form.state} onChange={set("state")} error={fieldErrors.state} />
          <Input label="Delivery instructions" className="sm:col-span-2" value={form.delivery_instructions} onChange={set("delivery_instructions")} placeholder="Ring the bell twice" />
          <label className="flex items-center gap-2 text-sm text-slate-700 sm:col-span-2">
            <input
              type="checkbox"
              checked={Boolean(form.is_default)}
              onChange={set("is_default")}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            Make this my default address
          </label>
          {error ? <p className="text-xs font-semibold text-rose-600 sm:col-span-2">{error}</p> : null}
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(deleting)}
        title="Delete this address?"
        description="It will be removed from your address book. Past orders keep their own copy."
        confirmLabel="Delete"
        onConfirm={doDelete}
        onClose={() => setDeleting(null)}
      />
    </div>
  );
}
