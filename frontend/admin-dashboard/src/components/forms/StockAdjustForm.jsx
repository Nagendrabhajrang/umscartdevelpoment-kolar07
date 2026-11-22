import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowDownCircle, ArrowUpCircle } from "lucide-react";
import Input from "../common/Input";
import Select from "../common/Select";
import Button from "../common/Button";
import { stockAdjustSchema, applyServerErrors, cleanPayload } from "../../validations";
import { inventoryService } from "../../services/inventoryService";
import { useNotification } from "../../context/NotificationContext";

import { MOVEMENT_TYPES } from "../../utils/constants";

/**
 * Stock in / stock out. Calls POST /inventory/stock/{id}/add/ or /remove/,
 * which write an InventoryMovement so every change stays auditable.
 */
export default function StockAdjustForm({ stock, mode = "add", onSaved, onCancel }) {
  const { notify } = useNotification();
  const [saving, setSaving] = useState(false);
  const isAdd = mode === "add";

  const {
    register, handleSubmit, setError, formState: { errors },
  } = useForm({
    resolver: zodResolver(stockAdjustSchema(mode)),
    defaultValues: { quantity: "", reason: "", reference: "", movement_type: isAdd ? "purchase" : "damage" },
  });

  const submit = async (values) => {
    setSaving(true);
    try {
      const payload = cleanPayload(values);
      if (isAdd) await inventoryService.addStock(stock.id, payload);
      else await inventoryService.removeStock(stock.id, payload);
      notify.success(`Stock ${isAdd ? "added" : "removed"} for ${stock.product_name}`);
      onSaved?.();
    } catch (e) {
      applyServerErrors(e.details, setError);
      notify.error(e.message || "Could not adjust stock.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-3" noValidate>
      <div className="rounded-lg bg-slate-50 px-3 py-2.5 text-sm">
        <p className="font-bold text-slate-900">{stock.product_name}</p>
        <p className="text-xs text-slate-500">
          {stock.product_sku} · currently <span className="font-semibold text-slate-700">{stock.quantity_available}</span> available
          {Number(stock.reserved_quantity) > 0 && ` · ${stock.reserved_quantity} reserved`}
        </p>
      </div>

      <Input
        label={isAdd ? "Quantity to add" : "Quantity to remove"}
        required
        type="number"
        min="1"
        step="1"
        {...register("quantity")}
        error={errors.quantity?.message}
        autoFocus
      />

      <Select label="Reason type" options={MOVEMENT_TYPES} {...register("movement_type")} error={errors.movement_type?.message} />
      <Input label="Reference" placeholder="Invoice / bill number" {...register("reference")} error={errors.reference?.message} />
      <Input label="Note" placeholder="Optional explanation" {...register("reason")} error={errors.reason?.message} />

      <div className="sticky bottom-0 -mx-5 -mb-4 flex justify-end gap-2 border-t border-slate-200 bg-white px-5 py-3">
        <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button
          type="submit"
          loading={saving}
          variant={isAdd ? "success" : "danger"}
          leftIcon={isAdd ? <ArrowUpCircle className="h-4 w-4" /> : <ArrowDownCircle className="h-4 w-4" />}
        >
          {isAdd ? "Add stock" : "Remove stock"}
        </Button>
      </div>
    </form>
  );
}
