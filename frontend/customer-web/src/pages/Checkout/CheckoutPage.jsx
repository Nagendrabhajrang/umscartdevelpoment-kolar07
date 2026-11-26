import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { orderService } from "../../services/orderService";
import { authService } from "../../services/authService";
import { addressService } from "../../services/addressService";
import { storeService } from "../../services/storeService";
import { paymentService } from "../../services/paymentService";
import UpiReferenceModal from "../../components/payment/UpiReferenceModal";
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
 * Payment: the customer picks cash on delivery or UPI. Which options appear is
 * driven by the store settings (`cod_enabled` / `upi_enabled`) so the admin can
 * switch either off without a redeploy. Choosing UPI reveals the store's QR and
 * UPI ID right here, and the order page then asks for the UPI reference.
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
  const [store, setStore] = useState(null);
  const [method, setMethod] = useState("cod");
  const [submitting, setSubmitting] = useState(false);
  /*
   * A UPI order is not finished the moment it is created: the customer still has
   * to say which payment it was. So instead of navigating straight to the order
   * page, hold this gate open - the modal has no way out until a transaction ID
   * is saved, and only then does the order page open.
   */
  const [upiGate, setUpiGate] = useState(null);
  /*
   * The UPI step is the popup, and it starts before the order exists: picking
   * "UPI - pay now" opens it there and then. Nothing UPI-shaped is drawn inline
   * on this page any more - no QR, no UPI ID, no "open in UPI app" button - so
   * the only place the QR appears is the popup the customer is asked to fill in.
   * The reference typed there is held here and submitted with the order.
   */
  const [upiSheet, setUpiSheet] = useState(false);
  const [upiRef, setUpiRef] = useState(null); // { reference, mobile }
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
    /*
     * While the UPI gate is open the basket has already been consumed by the
     * order, so a re-price would only fetch an empty cart and blank the screen
     * behind the modal. Nothing on this page matters until the reference is in.
     */
    if (upiGate) return;
    loadPreview();
  }, [cartSignature, loadPreview, upiGate]);

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

  // Payment options come from the store settings, not hardcoded.
  useEffect(() => {
    let alive = true;
    storeService
      .getSettings()
      .then((settings) => {
        if (!alive) return;
        setStore(settings);
        // Never leave the customer on a method the store has switched off.
        setMethod((current) => {
          if (current === "upi" && !settings.upi_enabled) return "cod";
          if (current === "cod" && !settings.cod_enabled) {
            return settings.upi_enabled ? "upi" : "cod";
          }
          return current;
        });
      })
      .catch(() => {
        /* settings are a nicety here: checkout still works with COD */
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
    /*
     * A UPI order without a reference is exactly the order the store cannot
     * match to a payment, so it is never created: the popup opens instead.
     */
    if (method === "upi" && !upiRef) {
      setUpiSheet(true);
      return;
    }

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
        payment_method: method,
        customer_notes: notes || undefined,
        coupon_code: preview?.coupon_code || undefined,
      });
      /*
       * A first-time customer typed their name on this form and nowhere else.
       * Persist it so the next sign-in greets them by name and the field is
       * prefilled instead of blank. Best effort: a failure here must never cost
       * them the order they just placed.
       */
      const knownName = (profile?.full_name || "").trim();
      if (!knownName && form.recipient_name.trim()) {
        authService
          .updateProfile({ display_name: form.recipient_name.trim() })
          .then(() => refreshProfile?.())
          .catch(() => {});
      }

      await refreshCart();
      notify.success(`Order ${order.order_number} placed`);

      if (method === "upi" && order.payment_id) {
        /*
         * The reference was typed into the popup before the order existed; the
         * payment row exists only now, so this is the first moment it can be
         * attached to it. Straight to the order page on success.
         */
        try {
          await paymentService.submitProof(order.payment_id, {
            transaction_reference: upiRef.reference,
            payer_mobile: upiRef.mobile || "",
          });
          notify.success("Transaction ID saved — the store will verify your payment.");
          navigate(`/orders/${order.id}`, {
            replace: true,
            state: { order, upiSubmitted: true },
          });
          return;
        } catch (e) {
          /*
           * The order exists but the reference did not stick. Fall back to the
           * blocking gate - the customer retries there instead of being sent to
           * an order page that looks paid when it is not.
           */
          notify.error(e?.message || "Could not save the transaction ID — enter it again.");
        }
        setUpiGate({
          paymentId: order.payment_id,
          orderId: order.id,
          orderNumber: order.order_number,
          amount: order.grand_total ?? order.total_amount ?? preview?.grand_total,
          /*
           * Carry the order itself. The order page reads the order from router
           * state (it will not fetch somebody else's order by id), so navigating
           * with only the id would land the customer on "Find your order" right
           * after paying - and demand the order number they never noted down.
           */
          order,
        });
        return;
      }

      navigate(`/orders/${order.id}`, { replace: true, state: { order } });
    } catch (e) {
      notify.error(e?.message || "Could not place the order");
    } finally {
      setSubmitting(false);
    }
  };

  /*
   * The gate, rendered on its own. Once the UPI order exists the basket is empty
   * and the checkout page would otherwise fall through to "Nothing to check
   * out" - which used to unmount the modal and strand the customer with an
   * order and no reference. So this branch short-circuits every other state:
   * empty cart, loading, error, whatever came before. The order is placed; the
   * only way forward is the transaction ID.
   */
  const upiGateModal = (
    <UpiReferenceModal
      open={Boolean(upiGate)}
      blocking
      paymentId={upiGate?.paymentId}
      amount={upiGate?.amount}
      orderNumber={upiGate?.orderNumber}
      upiId={store?.upi_id}
      payeeName={store?.upi_payee_name || store?.store_name}
      qrUrl={store?.upi_qr_image_url}
      onSubmitted={() => {
        const gate = upiGate;
        setUpiGate(null);
        if (gate?.orderId) {
          navigate(`/orders/${gate.orderId}`, {
            replace: true,
            state: { order: gate.order, upiSubmitted: true },
          });
        }
      }}
    />
  );

  if (upiGate) {
    return (
      <div className="container-page py-10">
        <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-5 text-center">
          <h1 className="text-lg font-extrabold tracking-tight text-slate-900">
            Order {upiGate.orderNumber} is placed
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            One last step: tell us the UPI transaction ID so the store can match your
            payment. Your order page opens as soon as it is saved.
          </p>
        </div>
        {upiGateModal}
      </div>
    );
  }

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
  const codOffered = store ? store.cod_enabled !== false : true;
  /*
   * UPI is offered when the admin left it on AND the store actually has a UPI ID,
   * or when the ID exists and the flag was never written (an older settings row).
   * An explicit `upi_enabled: false` is still respected - that is the admin's
   * switch, not a fallback.
   */
  const upiOffered =
    store?.upi_enabled === false
      ? false
      : Boolean(store?.upi_enabled || store?.upi_id);
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
            <div className="mt-3 space-y-2">
              {codOffered ? (
                <MethodOption
                  checked={method === "cod"}
                  onSelect={() => setMethod("cod")}
                  title="Cash on delivery"
                  description={
                    <>
                      Pay the delivery partner when your order arrives. Keep{" "}
                      <span className="font-bold">{formatMoney(preview.grand_total)}</span> ready.
                      {store?.cod_instructions ? (
                        <span className="mt-1 block text-[11px] text-slate-500">
                          {store.cod_instructions}
                        </span>
                      ) : null}
                    </>
                  }
                  icon={
                    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="2" y="6" width="20" height="12" rx="2" />
                      <circle cx="12" cy="12" r="2" />
                    </svg>
                  }
                />
              ) : null}

              {upiOffered ? (
                <MethodOption
                  checked={method === "upi"}
                  onSelect={() => {
                    setMethod("upi");
                    if (!upiRef) setUpiSheet(true);
                  }}
                  title="UPI — pay now"
                  description={
                    <>
                      Scan the store QR or pay to its UPI ID, then confirm the reference.
                      {store?.upi_id ? (
                        <span className="mt-0.5 block font-semibold text-slate-700">
                          {store.upi_id}
                        </span>
                      ) : null}
                    </>
                  }
                  icon={
                    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="3" y="3" width="7" height="7" rx="1" />
                      <rect x="14" y="3" width="7" height="7" rx="1" />
                      <rect x="3" y="14" width="7" height="7" rx="1" />
                      <path d="M14 14h3v3h-3zM20 14h1M14 20h1M18 18h3v3" />
                    </svg>
                  }
                />
              ) : null}
            </div>

            {/*
             * No QR and no UPI ID here: that is the popup's job. Once the
             * reference is typed this is just a receipt line, with one way back
             * into the popup to correct it.
             */}
            {method === "upi" ? (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2">
                <div className="min-w-0">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-brand-800">
                    {upiRef ? "UPI reference recorded" : "UPI reference needed"}
                  </p>
                  <p className="truncate text-xs font-semibold text-slate-800">
                    {upiRef
                      ? `${upiRef.reference}${upiRef.mobile ? ` · ${upiRef.mobile}` : ""}`
                      : "Pay with any UPI app, then enter the transaction ID."}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setUpiSheet(true)}
                >
                  {upiRef ? "Change" : "Enter transaction ID"}
                </Button>
              </div>
            ) : null}
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
                {method === "upi"
                  ? upiRef
                    ? "Your UPI reference is saved with the order."
                    : "Enter the transaction ID in the UPI popup to place this order."
                  : "You pay cash when the order arrives."}
              </p>
            )}
          </div>
        </aside>
      </div>

      {/*
       * The UPI step itself. Opening it from the payment option means the QR is
       * in front of the customer the moment they choose UPI, and the reference
       * collected here is what makes "Place order" possible.
       */}
      <UpiReferenceModal
        open={upiSheet}
        amount={preview.grand_total}
        upiId={store?.upi_id}
        payeeName={store?.upi_payee_name || store?.store_name}
        qrUrl={store?.upi_qr_image_url}
        initialReference={upiRef?.reference || ""}
        initialMobile={upiRef?.mobile || ""}
        onCollected={({ reference, mobile }) => {
          setUpiRef({ reference, mobile });
          setUpiSheet(false);
        }}
        onClose={() => setUpiSheet(false)}
      />

      {/* The blocking gate lives in `upiGateModal`, rendered above. */}
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

/** One selectable payment row (radio + icon + copy). */
function MethodOption({ checked, onSelect, title, description, icon }) {
  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition ${
        checked
          ? "border-brand-500 bg-brand-50/60 ring-1 ring-brand-500"
          : "border-slate-200 hover:border-slate-300"
      }`}
    >
      <input
        type="radio"
        name="payment_method"
        checked={checked}
        onChange={onSelect}
        className="mt-0.5 h-4 w-4 text-brand-600 focus:ring-brand-500"
      />
      <span
        className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${
          checked ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-500"
        }`}
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-bold text-slate-900">{title}</span>
        <span className="mt-0.5 block text-xs leading-relaxed text-slate-600">{description}</span>
      </span>
    </label>
  );
}
