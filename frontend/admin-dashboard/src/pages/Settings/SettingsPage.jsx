import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Banknote, CalendarOff, Info, Plus, QrCode, Save, ShieldCheck, Smartphone, Store, Trash2, Truck,
} from "lucide-react";
import Button from "../../components/common/Button";
import Input from "../../components/common/Input";
import Textarea from "../../components/common/Textarea";
import Modal from "../../components/common/Modal";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import ErrorState from "../../components/common/ErrorState";
import Skeleton from "../../components/common/Skeleton";
import { useStore } from "../../context/StoreContext";
import { useNotification } from "../../context/NotificationContext";
import { storeService } from "../../services/storeService";
import { settingsSchema, applyServerErrors, cleanPayload } from "../../validations";
import { formatMoney, formatDate, toDateInput } from "../../utils/format";
import SecurityTab from "../../components/settings/SecurityTab";

const TABS = [
  { key: "store", label: "Store profile", icon: Store },
  { key: "payments", label: "Payments", icon: Smartphone },
  { key: "delivery", label: "Delivery", icon: Truck },
  { key: "slabs", label: "Delivery slabs", icon: Banknote },
  { key: "holidays", label: "Holidays", icon: CalendarOff },
  { key: "security", label: "Security", icon: ShieldCheck },
];

/**
 * Store settings.
 *
 * The settings endpoint is a single row: everything the storefront reads -
 * UPI id and QR, COD switch, delivery charge, minimum order, tax, opening
 * state - is edited here and takes effect immediately (no deploy needed).
 */
export default function SettingsPage() {
  const { settings, loading, refresh, bumpDataVersion } = useStore();
  const { notify } = useNotification();
  // The account menu links here with ?tab=security.
  const [tab, setTab] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get("tab");
    return TABS.some((t) => t.key === requested) ? requested : "store";
  });
  const [error, setError] = useState(null);

  useEffect(() => { refresh(); }, [refresh]);

  if (loading && !settings) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-96" rounded="rounded-xl" />
      </div>
    );
  }

  if (!settings && !loading) {
    return <ErrorState error={error} onRetry={refresh} title="Could not load store settings" />;
  }

  return (
    <div className="space-y-3">
      <div>
        <h1 className="page-title">Settings</h1>
        <p className="mt-0.5 text-xs text-slate-500">
          Everything the storefront and checkout read at runtime.
        </p>
      </div>

      <div className="flex gap-1.5 overflow-x-auto pb-1 no-scrollbar" role="tablist" aria-label="Settings sections">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${tab === key ? "bg-brand-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"}`}>
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />{label}
          </button>
        ))}
      </div>

      {tab === "store" && <StoreTab settings={settings} onError={setError} />}
      {tab === "payments" && <PaymentsTab settings={settings} onError={setError} />}
      {tab === "delivery" && <DeliveryTab settings={settings} onError={setError} />}
      {tab === "slabs" && <SlabsTab />}
      {tab === "holidays" && <HolidaysTab />}
      {tab === "security" && <SecurityTab />}
    </div>
  );
}

/** Shared save logic for all settings forms. */
function useSettingsSave(settings, onError) {
  const { notify } = useNotification();
  const { refresh, bumpDataVersion } = useStore();
  const [saving, setSaving] = useState(false);

  const save = async (values, setFormError) => {
    setSaving(true);
    onError?.(null);
    try {
      const payload = cleanPayload(values);
      const file = document.getElementById("upi-qr-image")?.files?.[0];
      if (file) payload.upi_qr_image = file;
      await storeService.update(payload);
      await refresh();
      bumpDataVersion();
      notify.success("Settings saved");
      return true;
    } catch (e) {
      if (setFormError && e.details) applyServerErrors(e.details, setFormError);
      onError?.(e);
      notify.error(e.message || "Could not save settings.");
      return false;
    } finally {
      setSaving(false);
    }
  };

  return { save, saving };
}

function StoreTab({ settings, onError }) {
  const { save, saving } = useSettingsSave(settings, onError);
  const {
    register, handleSubmit, setError, formState: { errors },
  } = useForm({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      store_name: settings.store_name || "",
      tagline: settings.tagline || "",
      contact_phone: settings.contact_phone || "",
      contact_email: settings.contact_email || "",
      address: settings.address || "",
      maintenance_message: settings.maintenance_message || "",
      is_store_open: settings.is_store_open ?? true,
    },
  });

  return (
    <form onSubmit={handleSubmit((v) => save(v, setError))} className="card max-w-2xl space-y-3 p-4" noValidate>
      <h2 className="text-sm font-bold text-slate-900">Store profile</h2>
      <Input label="Store name" required {...register("store_name")} error={errors.store_name?.message} />
      <Input label="Tagline" {...register("tagline")} error={errors.tagline?.message} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="Contact phone" required inputMode="numeric" {...register("contact_phone")} error={errors.contact_phone?.message} />
        <Input label="Contact email" type="email" {...register("contact_email")} error={errors.contact_email?.message} />
      </div>
      <Textarea label="Store address" rows={2} {...register("address")} error={errors.address?.message} />

      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
          <input type="checkbox" {...register("is_store_open")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          Store is open for orders
        </label>
        <p className="mt-1 text-[11px] text-slate-500">
          When off, customers can browse but checkout is blocked and your message below is shown.
        </p>
        <Textarea label="Maintenance message" rows={2} className="mt-2" {...register("maintenance_message")} error={errors.maintenance_message?.message}
          placeholder="e.g. Closed for Diwali — back tomorrow at 8 AM" />
      </div>

      <div className="flex justify-end border-t border-slate-200 pt-3">
        <Button type="submit" loading={saving} leftIcon={<Save className="h-4 w-4" />}>Save store profile</Button>
      </div>
    </form>
  );
}

function PaymentsTab({ settings, onError }) {
  const { save, saving } = useSettingsSave(settings, onError);
  const { notify } = useNotification();
  const { refresh, bumpDataVersion } = useStore();
  const {
    register, handleSubmit, setError, getValues, reset, formState: { errors },
  } = useForm({
    resolver: zodResolver(settingsSchema.partial ? settingsSchema : settingsSchema),
    defaultValues: {
      store_name: settings.store_name || "",
      contact_phone: settings.contact_phone || "",
      upi_id: settings.upi_id || "",
      upi_payee_name: settings.upi_payee_name || "",
      cod_instructions: settings.cod_instructions || "",
      cod_enabled: settings.cod_enabled ?? true,
      upi_enabled: settings.upi_enabled ?? true,
    },
  });

  const qrPreview = settings.upi_qr_image_url;
  const [generating, setGenerating] = useState(false);

  /**
   * Regenerate the QR from the UPI ID saved on the server. Useful right after
   * changing the VPA: the uploaded PNG would otherwise still point at the old
   * one. Saves the current form first so the QR matches what is in the fields.
   */
  const generateQr = async () => {
    setGenerating(true);
    try {
      const values = getValues();
      await storeService.update(cleanPayload(values));
      await storeService.generateUpiQr();
      await refresh();
      bumpDataVersion();
      reset(values);
      notify.success("QR code generated from the UPI ID");
    } catch (err) {
      notify.error(err.message || "Could not generate the QR code.");
    } finally {
      setGenerating(false);
    }
  };

  const onSubmit = async (values, e) => {
    const file = document.getElementById("upi-qr-image")?.files?.[0];
    if (!file) {
      const ok = await save(values, setError);
      if (ok) notify.info("Settings updated");
      return;
    }
    // Multipart path for a new QR image.
    try {
      await storeService.update({ ...cleanPayload(values), upi_qr_image: file });
      const input = document.getElementById("upi-qr-image");
      if (input) input.value = "";
      await refresh();
      bumpDataVersion();
      notify.success("UPI settings and QR saved");
    } catch (err) {
      notify.error(err.message || "Could not upload the QR image.");
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="card max-w-2xl space-y-3 p-4" noValidate>
      <h2 className="text-sm font-bold text-slate-900">Payment methods</h2>

      <div className="grid gap-2 sm:grid-cols-2">
        <label className="flex items-start gap-2 rounded-lg border border-slate-200 p-3">
          <input type="checkbox" {...register("upi_enabled")} className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          <span>
            <span className="block text-sm font-semibold text-slate-900">UPI</span>
            <span className="block text-[11px] text-slate-500">Customers scan your QR and upload proof</span>
          </span>
        </label>
        <label className="flex items-start gap-2 rounded-lg border border-slate-200 p-3">
          <input type="checkbox" {...register("cod_enabled")} className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          <span>
            <span className="block text-sm font-semibold text-slate-900">Cash on delivery</span>
            <span className="block text-[11px] text-slate-500">Collected by the delivery partner</span>
          </span>
        </label>
      </div>

      <Input label="UPI ID (VPA)" placeholder="store@bank" {...register("upi_id")} error={errors.upi_id?.message} />
      <Input label="Payee name" placeholder="Name shown in the UPI app" {...register("upi_payee_name")} error={errors.upi_payee_name?.message} />
      <Textarea label="COD instructions" rows={2} {...register("cod_instructions")} error={errors.cod_instructions?.message}
        hint="Shown to the customer when they pick cash on delivery" />

      <div>
        <span className="mb-1 block text-xs font-semibold text-slate-600">UPI QR image</span>
        <div className="flex items-center gap-3">
          <label htmlFor="upi-qr-image" className="grid h-24 w-24 cursor-pointer place-items-center overflow-hidden rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 text-[10px] text-slate-400 hover:border-brand-400">
            {qrPreview ? <img src={qrPreview} alt="Current UPI QR" className="h-full w-full object-contain p-1" /> : "Choose QR"}
          </label>
          <input id="upi-qr-image" type="file" accept="image/*" className="sr-only" />
          <div className="min-w-0">
            <p className="text-[11px] text-slate-500">
              Export the QR from your UPI app (GPay / PhonePe / Paytm) and upload the PNG,
              or let the server draw one from the UPI ID above.
            </p>
            <Button type="button" variant="secondary" size="xs" className="mt-2"
              loading={generating} onClick={generateQr} leftIcon={<QrCode className="h-3.5 w-3.5" />}>
              Generate QR from UPI ID
            </Button>
          </div>
        </div>
      </div>

      {(!settings.upi_qr_image_url || !settings.upi_id) && (
        <p className="flex items-start gap-1.5 rounded-lg bg-amber-50 p-2.5 text-[11px] text-amber-900">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          UPI checkout is incomplete until both a UPI ID and a QR image are set. Customers will see a placeholder QR.
        </p>
      )}

      <div className="flex justify-end border-t border-slate-200 pt-3">
        <Button type="submit" loading={saving} leftIcon={<Save className="h-4 w-4" />}>Save payment settings</Button>
      </div>
    </form>
  );
}

function DeliveryTab({ settings, onError }) {
  const { save, saving } = useSettingsSave(settings, onError);
  const {
    register, handleSubmit, setError, formState: { errors },
  } = useForm({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      store_name: settings.store_name || "",
      contact_phone: settings.contact_phone || "",
      delivery_charge: settings.delivery_charge ?? 0,
      free_delivery_threshold: settings.free_delivery_threshold ?? 0,
      minimum_order_value: settings.minimum_order_value ?? 0,
      packaging_charge: settings.packaging_charge ?? 0,
      default_tax_percent: settings.default_tax_percent ?? 0,
      delivery_eta_minutes: settings.delivery_eta_minutes ?? 30,
      max_items_per_order: settings.max_items_per_order ?? 50,
      max_delivery_distance_km: settings.max_delivery_distance_km ?? 10,
      apply_tax_on_delivery: settings.apply_tax_on_delivery ?? false,
    },
  });

  return (
    <form onSubmit={handleSubmit((v) => save(v, setError))} className="card max-w-2xl space-y-3 p-4" noValidate>
      <h2 className="text-sm font-bold text-slate-900">Delivery & pricing</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <Input label="Delivery charge (₹)" type="number" step="0.01" min="0" {...register("delivery_charge")} error={errors.delivery_charge?.message} />
        <Input label="Free above (₹)" type="number" step="0.01" min="0" {...register("free_delivery_threshold")} error={errors.free_delivery_threshold?.message} />
        <Input label="Minimum order (₹)" type="number" step="0.01" min="0" {...register("minimum_order_value")} error={errors.minimum_order_value?.message} />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Input label="Packaging (₹)" type="number" step="0.01" min="0" {...register("packaging_charge")} error={errors.packaging_charge?.message} />
        <Input label="Default GST %" type="number" step="0.01" min="0" max="100" {...register("default_tax_percent")} error={errors.default_tax_percent?.message} />
        <Input label="ETA (minutes)" type="number" min="0" {...register("delivery_eta_minutes")} error={errors.delivery_eta_minutes?.message} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="Max items per order" type="number" min="1" {...register("max_items_per_order")} error={errors.max_items_per_order?.message} />
        <Input label="Max delivery distance (km)" type="number" step="0.1" min="0" {...register("max_delivery_distance_km")} error={errors.max_delivery_distance_km?.message} />
      </div>
      <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
        <input type="checkbox" {...register("apply_tax_on_delivery")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
        Apply tax to the delivery charge
      </label>
      <p className="rounded-lg bg-slate-50 p-2.5 text-[11px] text-slate-600">
        Current: delivery {formatMoney(settings.delivery_charge)}, free above {formatMoney(settings.free_delivery_threshold)},
        minimum order {formatMoney(settings.minimum_order_value)}.
      </p>
      <div className="flex justify-end border-t border-slate-200 pt-3">
        <Button type="submit" loading={saving} leftIcon={<Save className="h-4 w-4" />}>Save delivery settings</Button>
      </div>
    </form>
  );
}

function SlabsTab() {
  const { notify } = useNotification();
  const { bumpDataVersion } = useStore();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", min_order_value: "", max_order_value: "", delivery_charge: "", is_free: false, display_order: 0 });
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const load = () => {
    setLoading(true);
    storeService.deliverySlabs({ page_size: 100, ordering: "min_order_value" })
      .then((p) => setRows(p.results))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const submit = async () => {
    if (!form.name.trim() || form.min_order_value === "") {
      notify.error("Name and minimum order value are required.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        min_order_value: form.min_order_value,
        delivery_charge: form.delivery_charge || 0,
        is_free: form.is_free,
        display_order: Number(form.display_order) || 0,
      };
      if (form.max_order_value !== "") payload.max_order_value = form.max_order_value;
      await storeService.createSlab(payload);
      notify.success("Delivery slab added");
      setOpen(false);
      setForm({ name: "", min_order_value: "", max_order_value: "", delivery_charge: "", is_free: false, display_order: 0 });
      load();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not add the slab.");
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await storeService.deleteSlab(deleteTarget.id);
      notify.success("Slab removed");
      setDeleteTarget(null);
      load();
    } catch (e) {
      notify.error(e.message || "Could not remove the slab.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="card max-w-2xl p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-slate-900">Delivery charge slabs</h2>
          <p className="text-[11px] text-slate-500">Order-value bands with their own delivery fee. Takes priority over the flat charge.</p>
        </div>
        <Button size="sm" onClick={() => setOpen(true)} leftIcon={<Plus className="h-3.5 w-3.5" />}>Add slab</Button>
      </div>

      {loading ? (
        <div className="space-y-2">{[0, 1].map((i) => <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />)}</div>
      ) : !rows.length ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">
          No slabs — the flat delivery charge from the Delivery tab applies to every order.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {rows.map((slab) => (
            <li key={slab.id} className="flex items-center gap-2 py-2">
              <div className="flex-1">
                <p className="text-sm font-semibold text-slate-900">{slab.name}</p>
                <p className="text-[11px] text-slate-500">
                  {formatMoney(slab.min_order_value)} {slab.max_order_value ? `– ${formatMoney(slab.max_order_value)}` : "and above"}
                  {!slab.is_active && " · inactive"}
                </p>
              </div>
              <span className={`text-sm font-bold ${slab.is_free ? "text-emerald-600" : "text-slate-800"}`}>
                {slab.is_free ? "FREE" : formatMoney(slab.delivery_charge)}
              </span>
              <button type="button" onClick={() => setDeleteTarget(slab)} aria-label={`Delete ${slab.name}`}
                className="rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600">
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Add a delivery slab" size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setOpen(false)} disabled={saving}>Cancel</Button>
            <Button size="sm" onClick={submit} loading={saving}>Add slab</Button>
          </div>
        }>
        <div className="space-y-2.5">
          <Input label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Small basket" />
          <div className="grid grid-cols-2 gap-2">
            <Input label="Min order (₹)" required type="number" step="0.01" value={form.min_order_value} onChange={(e) => setForm({ ...form, min_order_value: e.target.value })} />
            <Input label="Max order (₹)" type="number" step="0.01" value={form.max_order_value} onChange={(e) => setForm({ ...form, max_order_value: e.target.value })} hint="Blank = no upper limit" />
          </div>
          <Input label="Delivery charge (₹)" type="number" step="0.01" value={form.delivery_charge} onChange={(e) => setForm({ ...form, delivery_charge: e.target.value })} />
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <input type="checkbox" checked={form.is_free} onChange={(e) => setForm({ ...form, is_free: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
            Free delivery in this band
          </label>
        </div>
      </Modal>

      <ConfirmDialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} onConfirm={confirmDelete}
        loading={deleting} title="Delete slab?" description={`"${deleteTarget?.name}" will stop applying to new orders.`} confirmLabel="Delete" />
    </div>
  );
}

function HolidaysTab() {
  const { notify } = useNotification();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", date: "", is_closed: true, note: "" });
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const load = () => {
    setLoading(true);
    storeService.holidays({ page_size: 100, ordering: "date" })
      .then((p) => setRows(p.results))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const submit = async () => {
    if (!form.name.trim() || !form.date) {
      notify.error("Name and date are required.");
      return;
    }
    setSaving(true);
    try {
      await storeService.createHoliday({ ...form, name: form.name.trim() });
      notify.success("Holiday added");
      setOpen(false);
      setForm({ name: "", date: "", is_closed: true, note: "" });
      load();
    } catch (e) {
      notify.error(e.message || "Could not add the holiday.");
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await storeService.deleteHoliday(deleteTarget.id);
      notify.success("Holiday removed");
      setDeleteTarget(null);
      load();
    } catch (e) {
      notify.error(e.message || "Could not remove the holiday.");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="card max-w-2xl p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-slate-900">Store holidays</h2>
          <p className="text-[11px] text-slate-500">Days the store is closed or running reduced hours.</p>
        </div>
        <Button size="sm" onClick={() => setOpen(true)} leftIcon={<Plus className="h-3.5 w-3.5" />}>Add holiday</Button>
      </div>

      {loading ? (
        <div className="space-y-2">{[0, 1].map((i) => <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />)}</div>
      ) : !rows.length ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">
          No holidays configured — the store follows its normal hours every day.
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {rows.map((h) => (
            <li key={h.id} className="flex items-center gap-2 py-2">
              <div className="flex-1">
                <p className="text-sm font-semibold text-slate-900">{h.name}</p>
                <p className="text-[11px] text-slate-500">{formatDate(h.date)}{h.note ? ` · ${h.note}` : ""}</p>
              </div>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${h.is_closed ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-800"}`}>
                {h.is_closed ? "CLOSED" : "LIMITED"}
              </span>
              <button type="button" onClick={() => setDeleteTarget(h)} aria-label={`Delete ${h.name}`}
                className="rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600">
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="Add a holiday" size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setOpen(false)} disabled={saving}>Cancel</Button>
            <Button size="sm" onClick={submit} loading={saving}>Add holiday</Button>
          </div>
        }>
        <div className="space-y-2.5">
          <Input label="Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Diwali" />
          <Input label="Date" required type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <input type="checkbox" checked={form.is_closed} onChange={(e) => setForm({ ...form, is_closed: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
            Fully closed this day
          </label>
          <Textarea label="Note (optional)" rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
        </div>
      </Modal>

      <ConfirmDialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)} onConfirm={confirmDelete}
        loading={deleting} title="Remove holiday?" description={`"${deleteTarget?.name}" will no longer block orders.`} confirmLabel="Remove" />
    </div>
  );
}
