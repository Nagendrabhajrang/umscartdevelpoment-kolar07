import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ImagePlus, Save } from "lucide-react";
import Input from "../common/Input";
import Select from "../common/Select";
import Button from "../common/Button";
import { bannerSchema, applyServerErrors, cleanPayload } from "../../validations";
import { BANNER_PLACEMENTS, LINK_TYPES } from "../../utils/constants";
import { bannerService } from "../../services/bannerService";
import { useNotification } from "../../context/NotificationContext";
import { toDateInput } from "../../utils/format";

/** Banner create/edit. Image fields are optional on edit (keeps the old file). */
export default function BannerForm({ banner = null, onSaved, onCancel }) {
  const { notify } = useNotification();
  const [saving, setSaving] = useState(false);
  const isEdit = Boolean(banner?.id);

  const {
    register, handleSubmit, setError, watch, formState: { errors },
  } = useForm({
    resolver: zodResolver(bannerSchema),
    defaultValues: {
      title: banner?.title || "",
      subtitle: banner?.subtitle || "",
      alt_text: banner?.alt_text || "",
      placement: banner?.placement || "home_hero",
      link_type: banner?.link_type || "none",
      link_url: banner?.link_url || "",
      linked_product: banner?.linked_product || "",
      linked_category: banner?.linked_category || "",
      linked_coupon_code: banner?.linked_coupon_code || "",
      display_order: banner?.display_order ?? 0,
      is_active: banner?.is_active ?? true,
      start_date: toDateInput(banner?.start_date),
      end_date: toDateInput(banner?.end_date),
    },
  });

  const linkType = watch("link_type");

  const submit = async (values) => {
    setSaving(true);
    try {
      const payload = cleanPayload(values);
      const image = document.getElementById("banner-image")?.files?.[0];
      const mobile = document.getElementById("banner-mobile-image")?.files?.[0];
      if (image) payload.image = image;
      if (mobile) payload.mobile_image = mobile;

      if (!isEdit && !image) {
        setError("title", { type: "manual", message: "A banner image is required for a new banner" });
        notify.error("Choose a banner image first.");
        return;
      }

      const saved = isEdit
        ? await bannerService.update(banner.id, payload)
        : await bannerService.create(payload);
      notify.success(isEdit ? "Banner updated" : "Banner created");
      onSaved?.(saved);
    } catch (e) {
      applyServerErrors(e.details, setError);
      notify.error(e.message || "Could not save the banner.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-3" noValidate>
      <Input label="Title" required {...register("title")} error={errors.title?.message} />
      <Input label="Subtitle" {...register("subtitle")} error={errors.subtitle?.message} />
      <Input label="Alt text (accessibility)" {...register("alt_text")} error={errors.alt_text?.message} hint="Describe the image for screen readers" />

      <div className="grid gap-3 sm:grid-cols-2">
        <Select label="Placement" options={BANNER_PLACEMENTS} {...register("placement")} error={errors.placement?.message} />
        <Select label="Link type" options={LINK_TYPES} {...register("link_type")} error={errors.link_type?.message} />
      </div>

      {linkType === "url" && <Input label="Link URL" placeholder="https://…" {...register("link_url")} error={errors.link_url?.message} />}
      {linkType === "product" && <Input label="Linked product ID" type="number" min="1" {...register("linked_product")} error={errors.linked_product?.message} />}
      {linkType === "category" && <Input label="Linked category ID" type="number" min="1" {...register("linked_category")} error={errors.linked_category?.message} />}
      {linkType === "coupon" && <Input label="Coupon code" {...register("linked_coupon_code")} error={errors.linked_coupon_code?.message} />}

      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="Start date" type="date" {...register("start_date")} error={errors.start_date?.message} />
        <Input label="End date" type="date" {...register("end_date")} error={errors.end_date?.message} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <span className="mb-1 block text-xs font-semibold text-slate-600">Desktop image {!isEdit && <span className="text-rose-500">*</span>}</span>
          <label htmlFor="banner-image" className="flex h-24 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 text-slate-400 transition hover:border-brand-400">
            <ImagePlus className="h-5 w-5" aria-hidden="true" />
            <span className="mt-1 text-[11px]">Choose image</span>
          </label>
          <input id="banner-image" type="file" accept="image/*" className="sr-only" />
        </div>
        <div>
          <span className="mb-1 block text-xs font-semibold text-slate-600">Mobile image (optional)</span>
          <label htmlFor="banner-mobile-image" className="flex h-24 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 text-slate-400 transition hover:border-brand-400">
            <ImagePlus className="h-5 w-5" aria-hidden="true" />
            <span className="mt-1 text-[11px]">Choose image</span>
          </label>
          <input id="banner-mobile-image" type="file" accept="image/*" className="sr-only" />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <Input label="Display order" type="number" min="0" {...register("display_order")} error={errors.display_order?.message} containerClassName="w-32" />
        <label className="mt-4 flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" {...register("is_active")} className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
          Active
        </label>
      </div>

      <div className="sticky bottom-0 -mx-5 -mb-4 flex justify-end gap-2 border-t border-slate-200 bg-white px-5 py-3">
        <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button type="submit" loading={saving} leftIcon={<Save className="h-4 w-4" />}>
          {isEdit ? "Save changes" : "Create banner"}
        </Button>
      </div>
    </form>
  );
}
