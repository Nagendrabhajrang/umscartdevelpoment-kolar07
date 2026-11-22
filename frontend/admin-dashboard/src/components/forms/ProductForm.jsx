import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ImagePlus, Save } from "lucide-react";
import Input from "../common/Input";
import Select from "../common/Select";
import Textarea from "../common/Textarea";
import Button from "../common/Button";
import { productSchema, applyServerErrors, cleanPayload } from "../../validations";
import { PRODUCT_STATUSES, UNIT_TYPES } from "../../utils/constants";
import { catalogService } from "../../services/catalogService";
import { useNotification } from "../../context/NotificationContext";

/**
 * Create / edit a product. Field names match ProductWriteRequest exactly:
 * name*, sku, barcode, category*, brand, description, short_description,
 * unit_type, unit_value, mrp*, selling_price*, image, is_vegetarian,
 * tax_percent, max_order_quantity, status, is_featured, display_order.
 *
 * The Zod schema blocks selling_price > mrp in the browser; DRF enforces it
 * again server-side.
 */
export default function ProductForm({ product = null, categories = [], onSaved, onCancel }) {
  const { notify } = useNotification();
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(product?.image_url || product?.primary_image || null);
  const isEdit = Boolean(product?.id);

  const {
    register, handleSubmit, setError, watch, formState: { errors },
  } = useForm({
    resolver: zodResolver(productSchema),
    defaultValues: {
      name: product?.name || "",
      sku: product?.sku || "",
      barcode: product?.barcode || "",
      category: product?.category || "",
      brand: product?.brand || "",
      description: product?.description || "",
      short_description: product?.short_description || "",
      unit_type: product?.unit_type || "piece",
      unit_value: product?.unit_value || "",
      mrp: product?.mrp || "",
      selling_price: product?.selling_price || "",
      tax_percent: product?.tax_percent ?? 0,
      max_order_quantity: product?.max_order_quantity ?? 10,
      status: product?.status || "active",
      is_featured: product?.is_featured || false,
      is_vegetarian: product?.is_vegetarian || false,
      display_order: product?.display_order ?? 0,
    },
  });

  const mrp = watch("mrp");
  const price = watch("selling_price");
  const discount = Number(mrp) > 0 && Number(price) > 0
    ? Math.max(0, ((Number(mrp) - Number(price)) / Number(mrp)) * 100)
    : 0;

  useEffect(() => () => {
    if (preview?.startsWith("blob:")) URL.revokeObjectURL(preview);
  }, [preview]);

  const onFile = (e) => {
    const file = e.target.files?.[0];
    if (file) setPreview(URL.createObjectURL(file));
  };

  const submit = async (values) => {
    setSaving(true);
    try {
      const payload = cleanPayload(values);
      const file = document.getElementById("product-image")?.files?.[0];
      if (file) payload.image = file;

      const saved = isEdit
        ? await catalogService.updateProduct(product.id, payload)
        : await catalogService.createProduct(payload);

      notify.success(isEdit ? "Product updated" : "Product created");
      onSaved?.(saved);
    } catch (e) {
      applyServerErrors(e.details, setError);
      notify.error(e.message || "Could not save the product.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-4" noValidate>
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="Product name" required {...register("name")} error={errors.name?.message} containerClassName="sm:col-span-2" />
        <Select label="Category" required placeholder="Choose a category" options={categories.map((c) => ({ value: String(c.id), label: c.full_path || c.name }))} {...register("category")} error={errors.category?.message} />
        <Input label="Brand" placeholder="e.g. Amul" {...register("brand")} error={errors.brand?.message} />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Input label="MRP (₹)" required type="number" step="0.01" min="0" {...register("mrp")} error={errors.mrp?.message} />
        <Input label="Selling price (₹)" required type="number" step="0.01" min="0" {...register("selling_price")} error={errors.selling_price?.message} />
        <div>
          <span className="mb-1 block text-xs font-semibold text-slate-600">Discount</span>
          <div className="flex h-10 items-center rounded-lg bg-slate-50 px-3 text-sm font-bold text-emerald-700">
            {discount > 0 ? `${discount.toFixed(1)}% off` : "—"}
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Select label="Unit type" options={UNIT_TYPES} {...register("unit_type")} error={errors.unit_type?.message} />
        <Input label="Unit value" placeholder="e.g. 500" {...register("unit_value")} error={errors.unit_value?.message} hint="Shown as 500 g / 1 L" />
        <Input label="GST %" type="number" step="0.01" min="0" max="100" {...register("tax_percent")} error={errors.tax_percent?.message} />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Input label="SKU" placeholder="Auto-generated if blank" {...register("sku")} error={errors.sku?.message} />
        <Input label="Barcode" {...register("barcode")} error={errors.barcode?.message} />
        <Input label="Max per order" type="number" min="1" {...register("max_order_quantity")} error={errors.max_order_quantity?.message} />
      </div>

      <Textarea label="Short description" rows={2} placeholder="One line shown on the product page" {...register("short_description")} error={errors.short_description?.message} />
      <Textarea label="Full description" rows={4} {...register("description")} error={errors.description?.message} />

      <div className="grid gap-3 sm:grid-cols-2">
        <Select label="Status" options={PRODUCT_STATUSES} {...register("status")} error={errors.status?.message} />
        <Input label="Display order" type="number" min="0" {...register("display_order")} error={errors.display_order?.message} />
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" {...register("is_featured")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          Featured on home page
        </label>
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" {...register("is_vegetarian")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          Vegetarian
        </label>
      </div>

      <div>
        <span className="mb-1 block text-xs font-semibold text-slate-600">Product image</span>
        <div className="flex items-center gap-3">
          <label htmlFor="product-image" className="grid h-20 w-20 cursor-pointer place-items-center overflow-hidden rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 text-slate-400 transition hover:border-brand-400 hover:text-brand-500">
            {preview ? (
              <img src={preview} alt="" className="h-full w-full object-cover" />
            ) : (
              <ImagePlus className="h-6 w-6" aria-hidden="true" />
            )}
          </label>
          <input id="product-image" type="file" accept="image/*" onChange={onFile} className="sr-only" />
          <p className="text-xs text-slate-500">
            JPG or PNG. Leave empty to keep the current image.
            {product?.image_url && <span className="mt-0.5 block text-slate-400">Current: {product.image_url.split("/").pop()}</span>}
          </p>
        </div>
      </div>

      <div className="sticky bottom-0 -mx-5 -mb-4 flex justify-end gap-2 border-t border-slate-200 bg-white px-5 py-3">
        <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button type="submit" loading={saving} leftIcon={<Save className="h-4 w-4" />}>
          {isEdit ? "Save changes" : "Create product"}
        </Button>
      </div>
    </form>
  );
}
