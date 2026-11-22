import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { orderService } from "../../services/orderService";
import { useNotification } from "../../context/NotificationContext";
import Button from "../../components/common/Button";
import Input from "../../components/common/Input";
import EmptyState from "../../components/common/EmptyState";
import { formatMoney } from "../../utils/format";

/**
 * Order history without an account.
 *
 * Round 25 removed the customer login, so there is no "my orders" list to fetch.
 * An order is instead found with the two things a shopper actually has: the
 * order number printed on their confirmation and the mobile number they gave at
 * checkout. Both must match, which stops one order number from revealing
 * somebody else's delivery address.
 *
 * The most recent order is remembered in localStorage so returning to this page
 * is one click, not a retype.
 */

const RECENT_KEY = "ums.recentOrder";

function readRecent() {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export default function OrderLookupPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { notify } = useNotification();

  const [orderNumber, setOrderNumber] = useState("");
  const [mobile, setMobile] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [recent, setRecent] = useState(() => readRecent());

  // A confirmation screen sends the shopper here with the number prefilled.
  useEffect(() => {
    const prefilled = location.state?.orderNumber;
    if (prefilled) setOrderNumber(prefilled);
  }, [location.state]);

  const search = async (event) => {
    event?.preventDefault();
    const number = orderNumber.trim().toUpperCase();
    const digits = mobile.replace(/\D/g, "").replace(/^91(?=\d{10}$)/, "");
    if (!number || !/^[6-9]\d{9}$/.test(digits)) {
      setError("Enter your order number and the mobile number you ordered with.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const order = await orderService.lookup(number, digits);
      try {
        localStorage.setItem(
          RECENT_KEY,
          JSON.stringify({ orderNumber: number, mobile: digits }),
        );
      } catch {
        /* storage unavailable - nothing to remember */
      }
      navigate(`/orders/${order.id}`, { replace: true, state: { order } });
    } catch (e) {
      setError(
        e?.status === 404
          ? "No order matches that number and mobile number. Check both and try again."
          : e?.message || "Could not look that order up.",
      );
    } finally {
      setBusy(false);
    }
  };

  const openRecent = async () => {
    if (!recent) return;
    setOrderNumber(recent.orderNumber);
    setMobile(recent.mobile);
    setBusy(true);
    setError(null);
    try {
      const order = await orderService.lookup(recent.orderNumber, recent.mobile);
      navigate(`/orders/${order.id}`, { replace: true, state: { order } });
    } catch {
      setRecent(null);
      try {
        localStorage.removeItem(RECENT_KEY);
      } catch {
        /* ignore */
      }
      notify.error("That order could not be found any more.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container-page py-6">
      <div className="mx-auto max-w-lg">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          Track your order
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          No account needed. Enter the order number from your confirmation and the
          mobile number you gave us.
        </p>

        {recent ? (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-brand-200 bg-brand-50/70 p-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-brand-800">
                Your last order
              </p>
              <p className="mt-0.5 text-sm font-semibold text-slate-900">
                {recent.orderNumber}
              </p>
            </div>
            <Button size="sm" onClick={openRecent} loading={busy}>
              View order
            </Button>
          </div>
        ) : null}

        <form onSubmit={search} className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
          <div className="space-y-3">
            <Input
              label="Order number"
              required
              name="order_number"
              value={orderNumber}
              onChange={(e) => setOrderNumber(e.target.value.toUpperCase())}
              placeholder="UMS-20261111-ABC123"
              autoComplete="off"
            />
            <Input
              label="Mobile number"
              required
              name="mobile_number"
              inputMode="tel"
              value={mobile}
              onChange={(e) => setMobile(e.target.value)}
              placeholder="10-digit mobile"
              autoComplete="tel"
              hint="The number you entered at checkout."
            />
          </div>

          {error ? (
            <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-800">
              {error}
            </p>
          ) : null}

          <Button type="submit" size="lg" fullWidth className="mt-4" loading={busy}>
            Find my order
          </Button>
        </form>

        <div className="mt-4">
          <EmptyState
            title="Don't have an order number?"
            description="It is on the confirmation screen after checkout and in the order card above."
            action={
              <Button as={Link} to="/products" variant="secondary">
                Continue shopping
              </Button>
            }
          />
        </div>
      </div>
    </div>
  );
}
