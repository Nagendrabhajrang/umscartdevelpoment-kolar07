import { get, getPaginated, post, patch, del, postMultipart } from "./api";

/**
 * Store configuration: the single settings row plus delivery slabs and
 * holidays. StoreSettings holds the UPI QR image, so updates go through the
 * multipart helper when a new file is chosen.
 */
export const storeService = {
  get: () => get("/store-settings/"),

  update: (payload) =>
    payload?.upi_qr_image instanceof File
      ? postMultipart("/store-settings/", payload, "patch")
      : patch("/store-settings/", payload),

  /* ---------------- Delivery slabs ---------------- */
  deliverySlabs: (params) => getPaginated("/store-settings/delivery-slabs/", params),
  createSlab: (payload) => post("/store-settings/delivery-slabs/", payload),
  updateSlab: (id, payload) => patch(`/store-settings/delivery-slabs/${id}/`, payload),
  deleteSlab: (id) => del(`/store-settings/delivery-slabs/${id}/`),

  /* ---------------- Holidays ---------------- */
  holidays: (params) => getPaginated("/store-settings/holidays/", params),
  createHoliday: (payload) => post("/store-settings/holidays/", payload),
  updateHoliday: (id, payload) => patch(`/store-settings/holidays/${id}/`, payload),
  deleteHoliday: (id) => del(`/store-settings/holidays/${id}/`),

  deliveryQuote: (payload) => post("/store-settings/delivery-quote/", payload),

  /** Draw a fresh QR from the saved UPI ID (no phone, no upload). */
  generateUpiQr: (payload = {}) => post("/store-settings/upi-qr/", payload),
};

export default storeService;
