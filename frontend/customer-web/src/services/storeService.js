import { get, post } from "./api";

export const storeService = {
  getSettings: () => get("/store-settings/"),
  deliveryQuote: (payload) => post("/store-settings/delivery-quote/", payload),
  getDeliverySlabs: async () => {
    const data = await get("/store-settings/delivery-slabs/");
    return Array.isArray(data) ? data : data?.results ?? [];
  },
  getHolidays: async () => {
    const data = await get("/store-settings/holidays/");
    return Array.isArray(data) ? data : data?.results ?? [];
  },
};

export default storeService;
