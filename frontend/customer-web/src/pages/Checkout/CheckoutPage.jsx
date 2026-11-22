import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { orderService } from "../../services/orderService";
import { authService } from "../../services/authService";
import { addressService } from "../../services/addressService";
import { useAuth } from "../../context/AuthContext";
import { useCart } from "../../context/CartContext";
import { useCustomer } from "../../context/CustomerContext";
import { useNotification } from "../../context/NotificationContext";
import Button from "../../components/common/Button";
import Input from "../../components/common/Input";
import Textarea from "../../components/common/Textarea";
import EmptyState from "../../components/common/EmptyState";
import ErrorState from "../../components/common/ErrorState";
import Skeleton from "../../components/common/Skeleton";
import { formatMoney } from "../../utils/format";

/**
 * Checkout.
 *
 * Round 27: this page is behind RequireAuth, so it always runs for a signed-in
 * customer. Two shapes, one page:
 *
 *   returning customer - their saved addresses are listed and preselected, and
 *                        their name and mobile are already known
 *   brand new customer - the address form is open, with the verified mobile
 *                        prefilled and read-only (it is already proven)
 *
 * Cash on delivery only - UPI was retired from this build.
 */

const EMPTY = {
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
  is_default: true,
};

export default function CheckoutPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { profile, refresh: refreshProfile } = useCustomer();
  const { refresh: refreshCart, cart } = useCart();
  const { notify } = useNotification();

  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [addresses, setAddresses] = useState(null);
  const [selectedAddress, setSelectedAddress] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [fieldErrors, setFieldErrors] = useState({});

  const [notes, setNotes] = useState("");
  const [coupon, setCoupon] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const seeded = useRef(false);

  const set = (key) => (event) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  const loadPreview = useCallback(async (code) => {
    setLoading(true);
    setError(null);
    try {
      const data = await orderService.preview(code ? { coupon_code: code } : {});
      setPreview(data);
      return data;
    } catch (e) {
      setError(e);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Re-price whenever the basket changes, not just on mount: the guest basket is
  // merged into the account during OTP verification, so the first render after
  // login can still be the pre-merge cart.
  const cartSignature = cart
    ? `${cart.item_count ?? 0}:${cart.subtotal ?? "0"}`
    : "none";

  useEffect(() => {
    loadPreview();
  }, [cartSignature, loadPreview]);

  // Saved addresses for a returning customer.
  useEffect(() => {
    let alive = true;
    addressService
      .listMine()
      .then((list) => {
        if (!alive) return;
        setAddresses(list);
        const preferred = list.find((a) => a.is_default) ?? list[0] ?? null;
        setSelectedAddress(preferred?.id ?? null);
        setFormOpen(list.length === 0);
      })
      .catch(() => {
        if (!alive) return;
        setAddresses([]);
        setFormOpen(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  /*
   * Prefill the form with what the account already knows.
   *
   * The mobile is the number just verified, so it arrives filled in. The name
   * needs more care: a brand-new customer has no name yet and the API reports
   * `display_name` as their mobile number, which must not be carried into the
   * "Full name" field - that is how it ended up reading "+919666000200" earlier.
   */
  useEffect(() => {
    if (seeded.current) return;
    seeded.current = true;
    const mobile = user?.mobile_number || "";
    const digits = mobile.replace(/\D/g, "");
    const candidate = (profile?.full_name || user?.display_name || "").trim();
    const looksLikeMobile = /^[+]?\d[\d\s-]{7,}$/.test(candidate) &&
      candidate.replace(/\D/g, "").endsWith(digits.slice(-10));

    setForm((current) => ({
      ...current,
      recipient_name: current.recipient_name || (looksLikeMobile ? "" : candidate),
      recipient_mobile: current.recipient_mobile || mobile,
    }));
  }, [user, profile]);

  const applyCoupon = async () => {
    const code = coupon.trim().toUpperCase();
    if (!code) return;
    const data = await loadPreview(code);
    if (data?.applied_promotion) notify.success(`Coupon ${code} applied`);
    else notify.error(`Coupon ${code} could not be applied`);
  };

  const validate = () => {
    const problems = {};
    if (!form.recipient_name.trim()) problems.recipient_name = "Enter the recipient's name";
    const digits = form.recipient_mobile.replace(/\D/g, "").replace(/^91(?=\d{10}$)/, "");
    if (!/^[6-9]\d{9}$/.test(digits)) {
      problems.recipient_mobile = "Enter a valid 10-digit mobile number";
    }
    if (!form.line1.trim()) problems.line1 = "Enter your house or building";
    if (!form.city.trim()) problems.city = "Enter your city";
    if (!form.state.trim()) problems.state = "Enter your state";
    if (!/^\d{6}$/.test(form.pincode.trim())) problems.pincode = "Enter a 6-digit PIN code";
    setFieldErrors(problems);
    return Object.keys(problems).length === 0;
  };

  const saveAddress = async () => {
    if (!validate()) return null;
    try {
      const created = await addressService.createMine({
        ...form,
        recipient_name: form.recipient_name.trim(),
        pincode: form.pincode.trim(),
      });
      const list = await addressService.listMine();
      setAddresses(list);
      setSelectedAddress(created.id);
      setFormOpen(false);
      notify.success("Address saved");
      return created;
    } catch (e) {
      notify.error(e?.message || "Could not save that address");
      return null;
    }
  };

  const placeOrder = async () => {
    let addressId = selectedAddress;

    // A new customer has no saved address yet: save the form first, then order.
    if (!addressId) {
      const created = await saveAddress();
      if (!created) {
        notify.error("Add a delivery address before placing the order");
        return;
      }
      addressId = created.id;
    }

    setSubmitting(true);
    try {
      const order = await orderService.checkoutOrder({
        address: addressId,
        payment_method: "cod",
        customer_notes: notes || undefined,
        coupon_code: preview?.coupon_code || undefined,
      });
      /*
       * A first-time customer typed their name on this form and nowhere else.
       * Persist it so the next sign-in greets them by name and the field is
       * prefilled instead of blank. Best effort: a failure here must never cost
       * them the order they just placed.
       */
      if (!name && form.recipient_name.trim()) {
        authService
          .updateProfile({ display_name: form.recipient_name.trim() })
          .then(() => refreshProfile?.())
          .catch(() => {});
      }

      await refreshCart();
      notify.success(`Order ${order.order_number} placed`);
      navigate(`/orders/${order.id}`, { replace: true, state: { order } });
    } catch (e) {
      notify.error(e?.message || "Could not place the order");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading && !preview) {
    return (
      <div className="container-page py-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Checkout</h1>
        <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_360px]">
          <Skeleton className="h-72 w-full rounded-2xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container-page py-8">
        <ErrorState error={error} onRetry={() => loadPreview()} title="Checkout could not start" />
      </div>
    );
  }

  if (!preview || preview.item_count === 0) {
    return (
      <div className="container-page py-8">
        <EmptyState
          title="Nothing to check out"
          description="Your cart is empty. Add something first."
          action={<Button as={Link} to="/products" size="lg">Browse products</Button>}
        />
      </div>
    );
  }

  const blocked = preview.store_open === false || preview.minimum_order_met === false;
  const hasSavedAddresses = Boolean(addresses?.length);

  return (
    <div className="container-page py-6">
      <div className="mb-4">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Checkout</h1>
        <p className="mt-1 text-sm text-slate-600">
          {preview.item_count} item{preview.item_count === 1 ? "" : "s"} ·{" "}
          {preview.total_quantity} unit{preview.total_quantity === 1 ? "" : "s"}
        </p>
      </div>

      {preview.issues?.length ? (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="text-xs font-bold uppercase tracking-wide text-amber-800">Before you continue</p>
          <ul className="mt-1 list-inside list-disc text-sm text-amber-900">
            {preview.issues.map((issue, i) => (
              <li key={i}>{issue.message || issue}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          {/* Address */}
          <section className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900">Delivery address</h2>
              {hasSavedAddresses ? (
                <Button variant="ghost" size="sm" onClick={() => setFormOpen((v) => !v)}>
                  {formOpen ? "Cancel" : "+ Add new"}
                </Button>
              ) : null}
            </div>

            {hasSavedAddresses && !formOpen ? (
              <ul className="mt-3 space-y-2">
                {addresses.map((a) => (
                  <li key={a.id}>
                    <label
                      className={`flex cursor-pointer gap-3 rounded-xl border p-3 transition ${
                        selectedAddress === a.id
                          ? "border-brand-500 bg-brand-50/60 ring-1 ring-brand-500"
                          : "border-slate-200 hover:border-slate-300"
                      }`}
                    >
                      <input
                        type="radio"
                        name="address"
                        checked={selectedAddress === a.id}
                        onChange={() => setSelectedAddress(a.id)}
                        className="mt-0.5 h-4 w-4 text-brand-600 focus:ring-brand-500"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-1.5">
                          <span className="text-sm font-bold text-slate-900">{a.recipient_name}</span>
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-slate-600">
                            {a.label_display || a.label}
                          </span>
                          {a.is_default ? (
                            <span className="rounded bg-brand-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-brand-800">
                              Default
                            </span>
                          ) : null}
                        </span>
                        <span className="mt-0.5 block text-xs leading-relaxed text-slate-600">
                          {a.full_address}
                        </span>
                        <span className="mt-0.5 block text-xs text-slate-500">{a.recipient_mobile}</span>
                      </span>
                    </label>
                  </li>
                ))}
                <li>
                  <Link
                    to="/addresses"
                    className="block px-1 pt-1 text-xs font-semibold text-brand-700 hover:underline"
                  >
                    Manage saved addresses
                  </Link>
                </li>
              </ul>
            ) : null}

            {formOpen || !hasSavedAddresses ? (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {!hasSavedAddresses ? (
                  <p className="sm:col-span-2 rounded-lg bg-brand-50 px-3 py-2 text-xs font-medium text-brand-900">
                    One last step — tell us where to deliver. We&apos;ll save it for next time.
                  </p>
                ) : null}
                <Input
                  label="Full name"
                  required
                  name="recipient_name"
                  autoComplete="name"
                  value={form.recipient_name}
                  onChange={set("recipient_name")}
                  error={fieldErrors.recipient_name}
                />
                <Input
                  label="Mobile number"
                  required
                  name="recipient_mobile"
                  value={form.recipient_mobile}
                  onChange={set("recipient_mobile")}
                  error={fieldErrors.recipient_mobile}
                  hint="Verified — change it only if the rider should call another number."
                  inputMode="tel"
                />
                <div className="sm:col-span-2">
                  <Input
                    label="House / flat / building"
                    required
                    name="line1"
                    autoComplete="address-line1"
                    value={form.line1}
                    onChange={set("line1")}
                    error={fieldErrors.line1}
                    placeholder="12, MG Road"
                  />
                </div>
                <Input label="Street / area" name="line2" autoComplete="address-line2"
                  value={form.line2} onChange={set("line2")} placeholder="Near the park" />
                <Input label="Landmark" name="landmark" value={form.landmark}
                  onChange={set("landmark")} placeholder="Opposite the mall" />
                <Input label="City" required name="city" autoComplete="address-level2"
                  value={form.city} onChange={set("city")} error={fieldErrors.city} />
                <Input label="State" required name="state" autoComplete="address-level1"
                  value={form.state} onChange={set("state")} error={fieldErrors.state} />
                <Input label="PIN code" required name="pincode" inputMode="numeric"
                  autoComplete="postal-code" maxLength={6} value={form.pincode}
                  onChange={set("pincode")} error={fieldErrors.pincode} placeholder="560001" />

                {formOpen && hasSavedAddresses ? (
                  <div className="sm:col-span-2 flex justify-end gap-2">
                    <Button variant="secondary" onClick={() => setFormOpen(false)}>Cancel</Button>
                    <Button onClick={saveAddress}>Save address</Button>
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>

          {/* Payment */}
          <section className="rounded-2xl border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-bold text-slate-900">Payment method</h2>
            <div className="mt-3 flex items-start gap-3 rounded-xl border border-brand-500 bg-brand-50/60 p-3 ring-1 ring-brand-500">
              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-600 text-white">
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="2" y="6" width="20" height="12" rx="2" />
                  <circle cx="12" cy="12" r="2" />
                </svg>
              </span>
              <div>
                <p className="text-sm font-bold text-slate-900">Cash on delivery</p>
                <p className="mt-0.5 text-xs leading-relaxed text-slate-600">
                  Pay the delivery partner when your order arrives. Keep{" "}
                  <span className="font-bold">{formatMoney(preview.grand_total)}</span> ready.
                </p>
              </div>
            </div>
          </section>

          {/* Notes */}
          <section className="rounded-2xl border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-bold text-slate-900">Delivery notes</h2>
            <Textarea
              className="mt-2"
              name="notes"
              rows={2}
              maxLength={255}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ring the bell twice, leave at the door…"
              hint="Optional. The rider will see this."
            />
          </section>
        </div>

        {/* Bill */}
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-bold text-slate-900">Bill details</h2>

            <div className="mt-3 flex gap-2">
              <Input
                aria-label="Coupon code"
                placeholder="Coupon code"
                value={coupon}
                onChange={(e) => setCoupon(e.target.value.toUpperCase())}
                className="flex-1"
              />
              <Button variant="secondary" onClick={applyCoupon}>Apply</Button>
            </div>

            <dl className="mt-3 space-y-2 text-sm">
              <Row label="MRP total" value={formatMoney(preview.mrp_total)} muted />
              <Row label="Product savings" value={`− ${formatMoney(preview.product_savings)}`} positive />
              <Row label="Item subtotal" value={formatMoney(preview.discounted_subtotal)} />
              {Number(preview.discount_amount) > 0 ? (
                <Row label={`Coupon ${preview.coupon_code}`} value={`− ${formatMoney(preview.discount_amount)}`} positive />
              ) : null}
              <Row
                label="Delivery"
                value={preview.is_free_delivery ? "FREE" : formatMoney(preview.delivery_charge)}
                positive={preview.is_free_delivery}
              />
              <Row label="Packaging" value={formatMoney(preview.packaging_charge)} />
              <Row label={`Taxes (${preview.tax_percent}%)`} value={formatMoney(preview.tax_amount)} />
              <div className="h-px bg-slate-200" />
              <Row label="To pay" value={formatMoney(preview.grand_total)} bold />
            </dl>

            {!preview.is_free_delivery && Number(preview.amount_to_free_delivery) > 0 ? (
              <p className="mt-2 rounded-lg bg-amber-50 px-2.5 py-2 text-[11px] font-semibold text-amber-800">
                Add {formatMoney(preview.amount_to_free_delivery)} more for free delivery
              </p>
            ) : null}

            <Button
              size="lg"
              fullWidth
              className="mt-4"
              onClick={placeOrder}
              loading={submitting}
              disabled={blocked}
            >
              Place order · {formatMoney(preview.grand_total)}
            </Button>

            {blocked ? (
              <p className="mt-2 text-center text-[11px] font-semibold text-rose-600">
                {preview.store_open === false
                  ? "The store is closed right now."
                  : `Minimum order is ${formatMoney(preview.minimum_order_value)}.`}
              </p>
            ) : (
              <p className="mt-2 text-center text-[11px] text-slate-500">
                You pay cash when the order arrives.
              </p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Row({ label, value, muted, positive, bold }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className={`${muted ? "text-slate-500" : "text-slate-600"} ${bold ? "font-bold text-slate-900" : ""}`}>
        {label}
      </dt>
      <dd
        className={`shrink-0 tabular-nums ${
          positive ? "font-semibold text-brand-700" : bold ? "text-base font-extrabold text-slate-900" : "text-slate-800"
        }`}
      >
        {value}
      </dd>
    </div>
  );
}
