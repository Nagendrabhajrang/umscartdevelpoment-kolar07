import { z } from "zod";

/**
 * Admin form schemas. These mirror the DRF serializers exactly (field names are
 * the API's), and the backend still validates independently.
 */

export const mobileSchema = z
  .string()
  .trim()
  .transform((v) => v.replace(/[\s-]/g, "").replace(/^(\+91|91|0)(?=\d{10}$)/, ""))
  .refine((v) => /^[6-9]\d{9}$/.test(v), { message: "Enter a valid 10-digit mobile number" });

export const priceField = (label = "Price") =>
  z.coerce
    .number({ invalid_type_error: `${label} must be a number` })
    .min(0, `${label} cannot be negative`)
    .refine((v) => Math.round(v * 100) === v * 100, { message: `${label} allows at most 2 decimals` });

/* ---------------- Product ---------------- */
export const productSchema = z
  .object({
    name: z.string().trim().min(2, "Name is required").max(160, "Name is too long"),
    sku: z.string().trim().max(60, "SKU is too long").optional().or(z.literal("")),
    barcode: z.string().trim().max(60).optional().or(z.literal("")),
    category: z.coerce.number().int().positive({ message: "Choose a category" }),
    brand: z.string().trim().max(80).optional().or(z.literal("")),
    description: z.string().trim().max(4000).optional().or(z.literal("")),
    short_description: z.string().trim().max(300).optional().or(z.literal("")),
    unit_type: z.string().optional().or(z.literal("")),
    unit_value: z.string().trim().max(20).optional().or(z.literal("")),
    mrp: priceField("MRP"),
    selling_price: priceField("Selling price"),
    tax_percent: z.coerce.number().min(0, "Tax cannot be negative").max(100, "Tax cannot exceed 100%").optional(),
    max_order_quantity: z.coerce.number().int().min(1, "At least 1").max(9999).optional(),
    status: z.enum(["draft", "active", "inactive", "discontinued"]).optional(),
    is_featured: z.boolean().optional(),
    is_vegetarian: z.boolean().optional(),
    display_order: z.coerce.number().int().min(0).optional(),
  })
  .superRefine((val, ctx) => {
    if (val.selling_price > val.mrp) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["selling_price"],
        message: "Selling price cannot be higher than MRP",
      });
    }
  });

/* ---------------- Category ---------------- */
export const categorySchema = z.object({
  name: z.string().trim().min(2, "Name is required").max(120, "Name is too long"),
  parent: z.union([z.coerce.number().int().positive(), z.literal(""), z.null()]).optional(),
  description: z.string().trim().max(600).optional().or(z.literal("")),
  icon_name: z.string().trim().max(60, "Keep the icon name short").optional().or(z.literal("")),
  display_order: z.coerce.number().int().min(0).optional(),
  is_featured: z.boolean().optional(),
  is_active: z.boolean().optional(),
});

/* ---------------- Banner ---------------- */
export const bannerSchema = z.object({
  title: z.string().trim().min(2, "Title is required").max(140),
  subtitle: z.string().trim().max(200).optional().or(z.literal("")),
  alt_text: z.string().trim().max(200).optional().or(z.literal("")),
  placement: z.enum(["hero", "strip", "category", "cart", "checkout", "popup", "app"]).optional(),
  link_type: z.enum(["none", "url", "product", "category", "coupon"]).optional(),
  link_url: z.string().trim().url("Enter a full URL (https://…)").optional().or(z.literal("")),
  linked_product: z.union([z.coerce.number().int().positive(), z.literal("")]).optional(),
  linked_category: z.union([z.coerce.number().int().positive(), z.literal("")]).optional(),
  linked_coupon_code: z.string().trim().max(40).optional().or(z.literal("")),
  display_order: z.coerce.number().int().min(0).optional(),
  is_active: z.boolean().optional(),
  start_date: z.string().optional().or(z.literal("")),
  end_date: z.string().optional().or(z.literal("")),
});

/* ---------------- Promotion ---------------- */
export const promotionSchema = z
  .object({
    name: z.string().trim().min(2, "Give the promotion a name").max(140),
    code: z.string().trim().max(40).regex(/^[A-Za-z0-9_-]*$/, "Letters, numbers, - and _ only").optional().or(z.literal("")),
    description: z.string().trim().max(400).optional().or(z.literal("")),
    discount_type: z.enum(["percentage", "fixed_amount", "free_delivery"]),
    discount_value: priceField("Discount"),
    max_discount_amount: z.union([priceField("Max discount"), z.literal("")]).optional(),
    min_order_value: z.union([priceField("Minimum order"), z.literal("")]).optional(),
    min_item_quantity: z.union([z.coerce.number().int().min(1), z.literal("")]).optional(),
    applies_to: z.enum(["all", "category", "products"]).optional(),
    category: z.union([z.coerce.number().int().positive(), z.literal("")]).optional(),
    start_date: z.string().optional().or(z.literal("")),
    end_date: z.string().optional().or(z.literal("")),
    usage_limit_total: z.union([z.coerce.number().int().min(1), z.literal("")]).optional(),
    usage_limit_per_customer: z.union([z.coerce.number().int().min(1), z.literal("")]).optional(),
    first_order_only: z.boolean().optional(),
    is_active: z.boolean().optional(),
    is_visible: z.boolean().optional(),
    priority: z.coerce.number().int().min(0).optional(),
  })
  .superRefine((val, ctx) => {
    if (val.discount_type === "percentage" && (val.discount_value <= 0 || val.discount_value > 100)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["discount_value"], message: "Percentage must be between 1 and 100" });
    }
    if (val.start_date && val.end_date && new Date(val.end_date) < new Date(val.start_date)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["end_date"], message: "End date must be after the start date" });
    }
    if (val.applies_to === "category" && !val.category) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["category"], message: "Choose the category this applies to" });
    }
  });

/* ---------------- Customer ---------------- */
export const customerSchema = z.object({
  full_name: z.string().trim().min(2, "Name is required").max(120),
  mobile_number: mobileSchema,
  email: z.string().trim().email("Enter a valid email").optional().or(z.literal("")),
  status: z.enum(["active", "blocked", "inactive"]).optional(),
  is_mobile_verified: z.boolean().optional(),
  notes: z.string().trim().max(1000).optional().or(z.literal("")),
});

/* ---------------- Inventory ---------------- */
export const stockAdjustSchema = (mode = "add") =>
  z.object({
    quantity: z.coerce
      .number({ invalid_type_error: "Enter a number" })
      .int("Whole numbers only")
      .positive("Must be greater than zero"),
    reason: z.string().trim().max(200).optional().or(z.literal("")),
    reference: z.string().trim().max(60).optional().or(z.literal("")),
    movement_type: z.string().optional(),
    mode: z.literal(mode).optional(),
  });

/* ---------------- Settings ---------------- */
export const settingsSchema = z.object({
  store_name: z.string().trim().min(2, "Store name is required").max(120),
  tagline: z.string().trim().max(200).optional().or(z.literal("")),
  contact_phone: mobileSchema,
  contact_email: z.string().trim().email("Enter a valid email").optional().or(z.literal("")),
  address: z.string().trim().max(400).optional().or(z.literal("")),
  currency_symbol: z.string().trim().max(4).optional(),
  delivery_charge: priceField("Delivery charge").optional(),
  free_delivery_threshold: priceField("Free delivery threshold").optional(),
  minimum_order_value: priceField("Minimum order value").optional(),
  packaging_charge: priceField("Packaging charge").optional(),
  default_tax_percent: z.coerce.number().min(0).max(100).optional(),
  delivery_eta_minutes: z.coerce.number().int().min(0).optional(),
  max_items_per_order: z.coerce.number().int().min(1).optional(),
  upi_id: z.string().trim().max(80).optional().or(z.literal("")),
  upi_payee_name: z.string().trim().max(120).optional().or(z.literal("")),
  cod_enabled: z.boolean().optional(),
  upi_enabled: z.boolean().optional(),
  cod_instructions: z.string().trim().max(300).optional().or(z.literal("")),
  is_store_open: z.boolean().optional(),
  maintenance_message: z.string().trim().max(300).optional().or(z.literal("")),
});

/** Apply DRF field errors onto a react-hook-form instance. */
export function applyServerErrors(details, setError) {
  if (!details || typeof details !== "object") return false;
  let applied = false;
  Object.entries(details).forEach(([field, message]) => {
    setError(field, {
      type: "server",
      message: Array.isArray(message) ? message[0] : String(message),
    });
    applied = true;
  });
  return applied;
}

/** Strip empty strings so DRF does not reject "" for numeric fields. */
export function cleanPayload(values) {
  const out = {};
  Object.entries(values).forEach(([key, value]) => {
    if (value === "" || value === undefined || value === null) return;
    out[key] = value;
  });
  return out;
}
