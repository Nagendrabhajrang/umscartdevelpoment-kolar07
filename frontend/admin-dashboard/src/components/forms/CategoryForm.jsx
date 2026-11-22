import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ImagePlus, Save } from "lucide-react";
import Input from "../common/Input";
import Select from "../common/Select";
import Textarea from "../common/Textarea";
import Button from "../common/Button";
import { categorySchema, applyServerErrors, cleanPayload } from "../../validations";
import { catalogService } from "../../services/catalogService";
import { useNotification } from "../../context/NotificationContext";

/** Category create/edit. Mirrors CategoryWriteRequest. */
export default function CategoryForm({ category = null, categories = [], onSaved, onCancel }) {
  const { notify } = useNotification();
  const [saving, setSaving] = useState(false);
  const isEdit = Boolean(category?.id);

  const {
    register, handleSubmit, setError, formState: { errors },
  } = useForm({
    resolver: zodResolver(categorySchema),
    defaultValues: {
      name: category?.name || "",
      parent: category?.parent || "",
      description: category?.description || "",
      icon_name: category?.icon_name || "",
      display_order: category?.display_order ?? 0,
      is_featured: category?.is_featured || false,
      is_active: category?.is_active ?? true,
    },
  });

  const submit = async (values) => {
    setSaving(true);
    try {
      const payload = cleanPayload(values);
      const file = document.getElementById("category-image")?.files?.[0];
      if (file) payload.image = file;

      const saved = isEdit
        ? await catalogService.updateCategory(category.id, payload)
        : await catalogService.createCategory(payload);
      notify.success(isEdit ? "Category updated" : "Category created");
      onSaved?.(saved);
    } catch (e) {
      applyServerErrors(e.details, setError);
      notify.error(e.message || "Could not save the category.");
    } finally {
      setSaving(false);
    }
  };

  const parentOptions = categories
    .filter((c) => c.id !== category?.id && !c.parent)
    .map((c) => ({ value: String(c.id), label: c.name }));

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-3" noValidate>
      <Input label="Category name" required {...register("name")} error={errors.name?.message} />
      <Select label="Parent category" placeholder="None (top level)" options={parentOptions} {...register("parent")} error={errors.parent?.message} />
      <Textarea label="Description" rows={3} {...register("description")} error={errors.description?.message} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="Icon name (Lucide)" placeholder="e.g. Carrot" {...register("icon_name")} error={errors.icon_name?.message} />
        <Input label="Display order" type="number" min="0" {...register("display_order")} error={errors.display_order?.message} />
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" {...register("is_featured")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          Featured
        </label>
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" {...register("is_active")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          Active
        </label>
      </div>

      <div>
        <span className="mb-1 block text-xs font-semibold text-slate-600">Category image</span>
        <div className="flex items-center gap-3">
          <label htmlFor="category-image" className="grid h-16 w-16 cursor-pointer place-items-center overflow-hidden rounded-full border-2 border-dashed border-slate-300 bg-slate-50 text-slate-400 transition hover:border-brand-400">
            {category?.image ? <img src={category.image} alt="" className="h-full w-full object-cover" /> : <ImagePlus className="h-5 w-5" aria-hidden="true" />}
          </label>
          <input id="category-image" type="file" accept="image/*" className="sr-only" />
          <p className="text-xs text-slate-500">Square image works best.</p>
        </div>
      </div>

      <div className="sticky bottom-0 -mx-5 -mb-4 flex justify-end gap-2 border-t border-slate-200 bg-white px-5 py-3">
        <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button type="submit" loading={saving} leftIcon={<Save className="h-4 w-4" />}>
          {isEdit ? "Save changes" : "Create category"}
        </Button>
      </div>
    </form>
  );
}
