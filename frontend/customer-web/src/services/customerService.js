import { get, patch, getPaginated } from "./api";

/**
 * Customer record.
 *
 * NOTE: there is no public "me" endpoint yet. The storefront and the admin
 * dashboard both read `/customers/` (the admin list endpoint), which is open
 * in this pre-authentication build. When JWT/OTP lands, `getMe` should point
 * at the new endpoint and `resolveByMobile` should disappear.
 */
export const customerService = {
  get: (id) => get(`/customers/${id}/`),
  update: (id, payload) => patch(`/customers/${id}/`, payload),

  list: (params) => getPaginated("/customers/", params),

  /** Exact lookup by mobile number using the documented filter. */
  async findByMobile(mobile) {
    const page = await getPaginated("/customers/", { mobile_number: mobile.trim(), page_size: 1 });
    return page.results[0] || null;
  },

  /** Fall back to a free-text search if the exact filter finds nothing. */
  async resolveByMobile(mobile) {
    const exact = await this.findByMobile(mobile);
    if (exact) return exact.id;
    const page = await getPaginated("/customers/", { search: mobile.trim(), page_size: 1 });
    return page.results[0]?.id ?? null;
  },
};

export default customerService;
