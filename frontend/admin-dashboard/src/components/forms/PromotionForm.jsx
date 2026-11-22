import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Save } from "lucide-react";
import Input from "../common/Input";
import Select from "../common/Select";
import Textarea from "../common/Textarea";
import Button from "../common/Button";
import { promotionSchema, applyServerErrors, cleanPayload } from "../../validations";
import { DISCOUNT_TYPES } from "../../utils/constants";
import { promotionService } from "../../services/promotionService";
import { useNotification } from "../../context/NotificationContext";
import { toDateInput } from "../../utils/format";

/** Promotion / coupon create-edit. Mirrors PromotionWriteRequest. */
export default function PromotionForm({ promotion = null, categories = [], onSaved, onCancel }) {
  const { notify } = useNotification();
  const [saving, setSaving] = useState(false);
  const isEdit = Boolean(promotion?.id);

  const {
    register, handleSubmit, setError, watch, formState: { errors },
  } = useForm({
    resolver: zodResolver(promotionSchema),
    defaultValues: {
      name: promotion?.name || "",
      code: promotion?.code || "",
      description: promotion?.description || "",
      discount_type: promotion?.discount_type || "percentage",
      discount_value: promotion?.discount_value ?? "",
      max_discount_amount: promotion?.max_discount_amount ?? "",
      min_order_value: promotion?.min_order_value ?? "",
      min_item_quantity: promotion?.min_item_quantity ?? "",
      applies_to: promotion?.applies_to || "all",
      category: promotion?.category || "",
      start_date: toDateInput(promotion?.start_date),
      end_date: toDateInput(promotion?.end_date),
      usage_limit_total: promotion?.usage_limit_total ?? "",
      usage_limit_per_customer: promotion?.usage_limit_per_customer ?? "",
      first_order_only: promotion?.first_order_only || false,
      is_active: promotion?.is_active ?? true,
      is_visible: promotion?.is_visible ?? true,
      priority: promotion?.priority ?? 0,
    },
  });

  const discountType = watch("discount_type");
  const appliesTo = watch("applies_to");

  const submit = async (values) => {
    setSaving(true);
    try {
      const payload = cleanPayload(values);
      const saved = isEdit
        ? await promotionService.update(promotion.id, payload)
        : await promotionService.create(payload);
      notify.success(isEdit ? "Promotion updated" : "Promotion created");
      onSaved?.(saved);
    } catch (e) {
      applyServerErrors(e.details, setError);
      notify.error(e.message || "Could not save the promotion.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-3" noValidate>
      <Input label="Promotion name" required {...register("name")} error={errors.name?.message} />
      <Input
        label="Coupon code"
        {...register("code")}
        error={errors.code?.message}
        hint="Leave blank for an automatic offer that needs no code"
        placeholder="e.g. SAVE50"
      />
      <Textarea label="Description" rows={2} {...register("description")} error={errors.description?.message} />

      <div className="grid gap-3 sm:grid-cols-3">
        <Select label="Discount type" options={DISCOUNT_TYPES} {...register("discount_type")} error={errors.discount_type?.message} />
        <Input
          label={discountType === "percentage" ? "Percent off" : discountType === "fixed_amount" ? "Amount off (₹)" : "Free delivery threshold (₹)"}
          required
          type="number"
          step="0.01"
          min="0"
          {...register("discount_value")}
          error={errors.discount_value?.message}
        />
        <Input label="Max discount (₹)" type="number" step="0.01" min="0" {...register("max_discount_amount")} error={errors.max_discount_amount?.message} hint="Cap for percentage offers" />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Input label="Min order (₹)" type="number" step="0.01" min="0" {...register("min_order_value")} error={errors.min_order_value?.message} />
        <Input label="Min item qty" type="number" min="1" {...register("min_item_quantity")} error={errors.min_item_quantity?.message} />
        <Select
          label="Applies to"
          options={[{ value: "all", label: "All products" }, { value: "category", label: "A category" }, { value: "products", label: "Specific products" }]}
          {...register("applies_to")}
          error={errors.applies_to?.message}
        />
      </div>

      {appliesTo === "category" && (
        <Select
          label="Category"
          placeholder="Choose a category"
          options={categories.map((c) => ({ value: String(c.id), label: c.name }))}
          {...register("category")}
          error={errors.category?.message}
        />
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="Starts" type="date" {...register("start_date")} error={errors.start_date?.message} />
        <Input label="Ends" type="date" {...register("end_date")} error={errors.end_date?.message} />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Input label="Total uses" type="number" min="1" {...register("usage_limit_total")} error={errors.usage_limit_total?.message} hint="Blank = unlimited" />
        <Input label="Uses per customer" type="number" min="1" {...register("usage_limit_per_customer")} error={errors.usage_limit_per_customer?.message} />
        <Input label="Priority" type="number" min="0" {...register("priority")} error={errors.priority?.message} hint="Higher wins conflicts" />
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" {...register("is_active")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          Active
        </label>
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" {...register("is_visible")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          Visible to customers
        </label>
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" {...register("first_order_only")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          First order only
        </label>
      </div>

      <div className="sticky bottom-0 -mx-5 -mb-4 flex justify-end gap-2 border-t border-slate-200 bg-white px-5 py-3">
        <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button type="submit" loading={saving} leftIcon={<Save className="h-4 w-4" />}>
          {isEdit ? "Save changes" : "Create promotion"}
        </Button>
      </div>
    </form>
  );
}
