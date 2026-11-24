import { useState } from "react";
import { useStore } from "../../context/StoreContext";
import { formatMoney } from "../../utils/format";

/**
 * Help & contact.
 *
 * This replaces the old support-ticket module: the store's real phone, email
 * and address (from store settings) plus an expandable FAQ. No API calls beyond
 * the settings already in context, so the page can never fail to load.
 */
const FAQ = [
  {
    q: "How do I pay for my order?",
    a: "Cash on delivery only. Keep the exact amount ready and hand it to the delivery partner when your order arrives. You will get a confirmation the moment it is collected.",
  },
  {
    q: "How long does delivery take?",
    a: "Most orders arrive within 45 minutes. You can follow every step from My orders — pending, packed, out for delivery, delivered.",
  },
  {
    q: "Can I cancel an order?",
    a: "Yes, until it is delivered. Open the order and choose Cancel order.",
  },
  {
    q: "What if an item is missing or damaged?",
    a: "Call the store on the number below within 24 hours of delivery. We refund that item in full — no photographs, no arguments.",
  },
  {
    q: "How do I return something?",
    a: "Fresh produce, dairy and frozen items cannot be returned once delivered, but they are covered by the freshness refund above. Unopened packaged goods can be returned within 7 days.",
  },
  {
    q: "Is there a minimum order value?",
    a: "Yes. The minimum is shown at checkout, and delivery is free above the store's threshold. Both are visible on your bill before you confirm.",
  },
  {
    q: "Do you deliver to my area?",
    a: "The store delivers within its local radius. If your pincode is outside it, checkout will tell you before you pay.",
  },
  {
    q: "How do I change my delivery address?",
    a: "Go to Saved addresses from the account menu. You can add, edit or delete any address, and mark one as the default for checkout.",
  },
];

export default function HelpPage() {
  const { settings } = useStore();
  const [openIndex, setOpenIndex] = useState(0);

  const phone = settings?.contact_phone;
  const email = settings?.contact_email;
  const address = settings?.address;
  const storeName = settings?.store_name || "UMS Mart";

  return (
    <div className="container-page py-6">
      <header className="max-w-2xl">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Help &amp; contact</h1>
        <p className="mt-1 text-sm text-slate-600">
          Answers to the usual questions, and a direct line to {storeName}.
        </p>
      </header>

      {/* Contact cards */}
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <ContactCard
          title="Call the store"
          value={phone || "Not published"}
          href={phone ? `tel:${phone}` : null}
          note="Fastest way to reach us"
          icon={
            <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.9a2 2 0 0 1-.5 2.1L8.1 10a16 16 0 0 0 6 6l1.3-1.2a2 2 0 0 1 2.1-.5c.9.3 1.9.6 2.9.7a2 2 0 0 1 1.7 2Z" />
          }
        />
        <ContactCard
          title="Email us"
          value={email || "Not published"}
          href={email ? `mailto:${email}` : null}
          note="Replies within one working day"
          icon={
            <>
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <path d="m2 7 10 6 10-6" />
            </>
          }
        />
        <ContactCard
          title="Visit the store"
          value={address || "Not published"}
          note="Open 8am – 10pm daily"
          icon={
            <>
              <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
              <circle cx="12" cy="10" r="3" />
            </>
          }
        />
      </div>

      {/* Store facts */}
      {settings ? (
        <div className="mt-3 grid gap-2.5 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
          <Fact label="Delivery time" value={`${settings.delivery_eta_minutes ?? 45} minutes`} />
          <Fact
            label="Free delivery above"
            value={formatMoney(settings.free_delivery_threshold ?? 499)}
          />
          <Fact label="Payment" value="Cash on delivery" />
        </div>
      ) : null}

      {/* FAQ */}
      <section className="mt-6">
        <h2 className="text-lg font-bold text-slate-900">Frequently asked</h2>
        <p className="mt-0.5 text-sm text-slate-600">Tap a question to expand it.</p>

        <div className="mt-3 divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white">
          {FAQ.map((item, i) => {
            const open = openIndex === i;
            return (
              <div key={item.q}>
                <h3>
                  <button
                    type="button"
                    onClick={() => setOpenIndex(open ? -1 : i)}
                    aria-expanded={open}
                    aria-controls={`faq-panel-${i}`}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left text-sm font-semibold text-slate-900 hover:bg-slate-50"
                  >
                    {item.q}
                    <span
                      aria-hidden="true"
                      className={`grid h-6 w-6 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-600 transition-transform ${
                        open ? "rotate-45" : ""
                      }`}
                    >
                      +
                    </span>
                  </button>
                </h3>
                {open ? (
                  <div id={`faq-panel-${i}`} className="px-4 pb-4 text-sm leading-relaxed text-slate-600">
                    {item.a}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>

      <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-5 text-center">
        <p className="text-sm font-bold text-slate-900">Still stuck?</p>
        <p className="mx-auto mt-1 max-w-md text-xs text-slate-600">
          Call the store on{" "}
          {phone ? (
            <a href={`tel:${phone}`} className="font-bold text-brand-700 hover:underline">
              {phone}
            </a>
          ) : (
            "the number on your order confirmation"
          )}
          . Quote your order number and we will sort it out.
        </p>
      </div>
    </div>
  );
}

function ContactCard({ title, value, href, note, icon }) {
  const body = (
    <>
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-50 text-brand-700">
        <svg viewBox="0 0 24 24" className="h-4.5 w-4.5" fill="none" stroke="currentColor" strokeWidth="2">
          {icon}
        </svg>
      </span>
      <span className="mt-2.5 block text-[11px] font-bold uppercase tracking-wide text-slate-500">
        {title}
      </span>
      <span className="mt-1 block break-words text-sm font-semibold leading-snug text-slate-900">
        {value}
      </span>
      <span className="mt-1 block text-[11px] text-slate-500">{note}</span>
    </>
  );

  const cls =
    "block rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-brand-300";
  return href ? (
    <a href={href} className={cls}>
      {body}
    </a>
  ) : (
    <div className={cls}>{body}</div>
  );
}

function Fact({ label, value }) {
  return (
    <div>
      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-slate-800">{value}</p>
    </div>
  );
}
