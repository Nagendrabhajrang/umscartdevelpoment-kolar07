import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, UserX, Eye } from "lucide-react";
import Button from "../../components/common/Button";
import Input from "../../components/common/Input";
import Select from "../../components/common/Select";
import Modal from "../../components/common/Modal";
import Pagination from "../../components/common/Pagination";
import DataTable from "../../components/tables/DataTable";
import TableToolbar from "../../components/tables/TableToolbar";
import Badge from "../../components/common/Badge";
import ErrorState from "../../components/common/ErrorState";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import StatCard from "../../components/charts/StatCard";
import { StatSkeleton } from "../../components/common/Skeleton";
import { useListPage } from "../../hooks/useListPage";
import { useStore } from "../../context/StoreContext";
import { useNotification } from "../../context/NotificationContext";
import { customerService } from "../../services/customerService";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { customerSchema, applyServerErrors, cleanPayload } from "../../validations";
import { formatMoney, formatDate, formatNumber, initials, downloadCsv } from "../../utils/format";
import { CUSTOMER_STATUSES } from "../../utils/constants";

/** Customer directory: search, status, block/unblock, notes, create, edit. */
export default function CustomersPage() {
  const { dataVersion, bumpDataVersion } = useStore();
  const { notify } = useNotification();

  const list = useListPage(customerService.list, { page_size: 20, ordering: "-created_at" });
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [blockTarget, setBlockTarget] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSummaryLoading(true);
    customerService.summary()
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setSummaryLoading(false));
  }, [dataVersion]);

  useEffect(() => { list.reload(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [dataVersion]);

  const toggleBlock = async () => {
    setBusy(true);
    const block = blockTarget.status !== "blocked";
    try {
      await customerService.setStatus(blockTarget.id, block ? "blocked" : "active");
      notify.success(block ? `${blockTarget.full_name} blocked` : `${blockTarget.full_name} reactivated`);
      setBlockTarget(null);
      list.reload();
      bumpDataVersion();
    } catch (e) {
      notify.error(e.message || "Could not change the customer status.");
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    {
      key: "full_name",
      header: "Customer",
      sortable: true,
      render: (r) => (
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-100 text-[11px] font-bold text-brand-700">
            {initials(r.full_name)}
          </span>
          <div className="min-w-0">
            <Link to={`/customers/${r.id}`} className="font-semibold text-slate-900 hover:text-brand-700">{r.full_name}</Link>
            <p className="truncate text-[11px] text-slate-500">{r.mobile_number}{r.email ? ` · ${r.email}` : ""}</p>
          </div>
        </div>
      ),
    },
    {
      key: "orders",
      header: "Orders",
      align: "right",
      sortable: true,
      render: (r) => <span className="font-semibold tabular-nums text-slate-800">{formatNumber(r.order_count)}</span>,
    },
    {
      key: "address_count",
      header: "Addresses",
      align: "right",
      render: (r) => <span className="text-xs tabular-nums text-slate-600">{formatNumber(r.address_count)}</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (r) => (
        <Badge tone={r.status === "active" ? "green" : r.status === "blocked" ? "red" : "slate"}>
          {r.status}
        </Badge>
      ),
    },
    {
      key: "created_at",
      header: "Joined",
      sortable: true,
      render: (r) => <span className="text-[11px] text-slate-500">{formatDate(r.created_at)}</span>,
    },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => (
        <div className="flex justify-end gap-1">
          <Link to={`/customers/${row.id}`} title="View customer profile"
            className="rounded p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800">
            <Eye className="h-4 w-4" aria-hidden="true" /><span className="sr-only">View {row.full_name}</span>
          </Link>
          <button type="button" onClick={() => setBlockTarget(row)} title={row.status === "blocked" ? "Reactivate" : "Block"}
            className={`rounded p-1.5 ${row.status === "blocked" ? "text-emerald-600 hover:bg-emerald-50" : "text-rose-600 hover:bg-rose-50"}`}>
            <UserX className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">{row.status === "blocked" ? "Reactivate" : "Block"} {row.full_name}</span>
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="page-title">Customers</h1>
          <p className="mt-0.5 text-xs text-slate-500">{formatNumber(list.count)} registered customers</p>
        </div>
        <Button onClick={() => { setEditing(null); setFormOpen(true); }} leftIcon={<Plus className="h-4 w-4" />}>New customer</Button>
      </div>

      {summaryLoading && !summary ? (
        <StatSkeleton count={4} />
      ) : summary ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total customers" value={formatNumber(summary.total)} tone="brand" />
          <StatCard label="Active" value={formatNumber(summary.active)} tone="green" />
          <StatCard label="Blocked" value={formatNumber(summary.blocked)} tone="rose" />
          <StatCard label="Inactive" value={formatNumber(summary.inactive)} tone="slate" />
        </div>
      ) : null}

      <TableToolbar
        search={list.searchInput}
        onSearchChange={list.setSearch}
        searchPlaceholder="Name, mobile or email…"
        onRefresh={list.reload}
        refreshing={list.loading}
        onExport={() => downloadCsv("customers.csv", list.rows, ["id", "full_name", "mobile_number", "email", "status", "order_count", "created_at"])}
        filters={
          <Select aria-label="Filter by status" value={list.filters.status || ""} onChange={(e) => list.setFilter("status", e.target.value)}
            options={[{ value: "", label: "Any status" }, ...CUSTOMER_STATUSES]} containerClassName="w-40" className="h-9" />
        }
      />

      {list.error ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : (
        <>
          <DataTable columns={columns} rows={list.rows} loading={list.loading} sort={list.sort} onSortChange={list.setSort}
            emptyTitle="No customers found" emptyDescription="Customers are created when someone places their first order."
            caption="Customers" />
          <Pagination count={list.count} page={list.page} pageSize={list.pageSize}
            hasNext={list.hasNext} hasPrevious={list.hasPrevious} onPageChange={list.setPage} />
        </>
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? "Edit customer" : "New customer"} size="md">
        <CustomerForm
          customer={editing}
          onSaved={() => { setFormOpen(false); list.reload(); bumpDataVersion(); }}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <ConfirmDialog
        open={Boolean(blockTarget)}
        onClose={() => setBlockTarget(null)}
        onConfirm={toggleBlock}
        loading={busy}
        tone={blockTarget?.status === "blocked" ? "success" : "danger"}
        title={blockTarget?.status === "blocked" ? "Reactivate customer?" : "Block customer?"}
        description={blockTarget?.status === "blocked"
          ? `${blockTarget?.full_name} will be able to order again.`
          : `${blockTarget?.full_name} will not be able to place new orders. Existing orders are unaffected.`}
        confirmLabel={blockTarget?.status === "blocked" ? "Reactivate" : "Block customer"}
      />
    </div>
  );
}

/** Create / edit customer. Mirrors CustomerWriteRequest. */
function CustomerForm({ customer, onSaved, onCancel }) {
  const { notify } = useNotification();
  const [saving, setSaving] = useState(false);
  const isEdit = Boolean(customer?.id);

  const {
    register, handleSubmit, setError, formState: { errors },
  } = useForm({
    resolver: zodResolver(customerSchema),
    defaultValues: {
      full_name: customer?.full_name || "",
      mobile_number: customer?.mobile_number || "",
      email: customer?.email || "",
      status: customer?.status || "active",
      is_mobile_verified: customer?.is_mobile_verified || false,
      notes: customer?.notes || "",
    },
  });

  const submit = async (values) => {
    setSaving(true);
    try {
      const payload = cleanPayload(values);
      const saved = isEdit
        ? await customerService.update(customer.id, payload)
        : await customerService.create(payload);
      notify.success(isEdit ? "Customer updated" : "Customer created");
      onSaved?.(saved);
    } catch (e) {
      applyServerErrors(e.details, setError);
      notify.error(e.message || "Could not save the customer.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-3" noValidate>
      <Input label="Full name" required {...register("full_name")} error={errors.full_name?.message} />
      <Input label="Mobile number" required inputMode="numeric" {...register("mobile_number")} error={errors.mobile_number?.message} />
      <Input label="Email" type="email" {...register("email")} error={errors.email?.message} />
      <Select label="Status" options={CUSTOMER_STATUSES} {...register("status")} error={errors.status?.message} />
      <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
        <input type="checkbox" {...register("is_mobile_verified")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
        Mobile number verified
      </label>
      <div>
        <label htmlFor="customer-notes" className="mb-1 block text-xs font-semibold text-slate-600">Internal notes</label>
        <textarea id="customer-notes" rows={3} {...register("notes")}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100" />
      </div>
      <div className="flex justify-end gap-2 border-t border-slate-200 pt-3">
        <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button type="submit" loading={saving}>{isEdit ? "Save changes" : "Create customer"}</Button>
      </div>
    </form>
  );
}
