import { useState } from "react";
import { Link } from "react-router-dom";
import { useCustomer } from "../../context/CustomerContext";
import { customerService } from "../../services/customerService";
import { useNotification } from "../../context/NotificationContext";
import Input from "../../components/common/Input";
import Button from "../../components/common/Button";
import Skeleton from "../../components/common/Skeleton";
import { initials, formatDate } from "../../utils/format";
import { validateProfile, isProfileValid } from "../../validations";

/** Read-mostly profile: name and email are editable, the rest is identity. */
export default function ProfilePage() {
  const { profile, loading, refresh, customerId } = useCustomer();
  const { notify } = useNotification();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ full_name: "", email: "" });
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});

  const startEdit = () => {
    setFieldErrors({});
    setForm({ full_name: profile?.full_name || "", email: profile?.email || "" });
    setEditing(true);
  };

  const save = async () => {
    const problems = validateProfile(form);
    setFieldErrors(problems);
    if (!isProfileValid(problems)) return;

    setSaving(true);
    try {
      await customerService.update(customerId, form);
      await refresh();
      notify.success("Profile updated");
      setEditing(false);
    } catch (e) {
      notify.error(e?.message || "Could not save your profile");
    } finally {
      setSaving(false);
    }
  };

  if (loading && !profile) {
    return (
      <div className="container-page py-6">
        <Skeleton className="h-32 w-full rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="container-page py-6">
      <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">My profile</h1>
      <p className="mt-1 text-sm text-slate-600">Your details and account shortcuts.</p>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex items-center gap-3">
            <span className="grid h-14 w-14 place-items-center rounded-2xl bg-brand-600 text-lg font-bold text-white">
              {initials(profile?.full_name || "Guest")}
            </span>
            <div>
              <p className="text-lg font-extrabold text-slate-900">{profile?.full_name || "Guest"}</p>
              <p className="text-xs text-slate-500">{profile?.mobile_number || "No mobile on file"}</p>
            </div>
          </div>

          <dl className="mt-5 grid gap-3 sm:grid-cols-2">
            <Field label="Full name" value={profile?.full_name} />
            <Field label="Mobile number" value={profile?.mobile_number} />
            <Field label="Email" value={profile?.email || "—"} />
            <Field label="Member since" value={profile?.created_at ? formatDate(profile.created_at) : "—"} />
          </dl>

          {editing ? (
            <div className="mt-5 space-y-3 border-t border-slate-100 pt-4">
              <Input
                label="Full name"
                value={form.full_name}
                error={fieldErrors.full_name}
                onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
              />
              <Input
                label="Email"
                type="email"
                value={form.email}
                error={fieldErrors.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
              <div className="flex gap-2">
                <Button onClick={save} loading={saving}>Save changes</Button>
                <Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
              </div>
            </div>
          ) : (
            <Button variant="secondary" className="mt-5" onClick={startEdit}>
              Edit details
            </Button>
          )}
        </div>

        <aside className="space-y-2.5">
          {[
            ["/orders", "My orders", "Track and reorder"],
            ["/addresses", "Saved addresses", "Manage delivery locations"],
            ["/wishlist", "Wishlist", "Products you saved"],
            ["/help", "Help & contact", "Talk to the store"],
          ].map(([to, title, sub]) => (
            <Link
              key={to}
              to={to}
              className="block rounded-xl border border-slate-200 bg-white px-4 py-3 transition hover:border-brand-300"
            >
              <p className="text-sm font-bold text-slate-900">{title}</p>
              <p className="text-xs text-slate-500">{sub}</p>
            </Link>
          ))}
        </aside>
      </div>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <dt className="text-[11px] font-bold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{value || "—"}</dd>
    </div>
  );
}
