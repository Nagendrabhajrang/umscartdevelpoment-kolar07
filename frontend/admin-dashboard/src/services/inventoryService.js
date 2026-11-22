import { get, getPaginated, post, patch } from "./api";

/** Stock levels and the movement log. */
export const inventoryService = {
  listStock: (params) => getPaginated("/inventory/stock/", params),
  getStock: (id) => get(`/inventory/stock/${id}/`),
  createStock: (payload) => post("/inventory/stock/", payload),
  updateStock: (id, payload) => patch(`/inventory/stock/${id}/`, payload),

  lowStock: (params) => getPaginated("/inventory/stock/low-stock/", params),
  summary: () => get("/inventory/stock/summary/"),

  addStock: (id, payload) => post(`/inventory/stock/${id}/add/`, payload),
  removeStock: (id, payload) => post(`/inventory/stock/${id}/remove/`, payload),
  // These three endpoints are PATCH-only on the API. Sending POST returns
  // 405 Method Not Allowed, which is why the tracking toggle silently failed.
  setQuantity: (id, quantity) => patch(`/inventory/stock/${id}/quantity/`, { quantity }),
  setThreshold: (id, low_stock_threshold) => patch(`/inventory/stock/${id}/threshold/`, { low_stock_threshold }),
  setTracking: (id, track_inventory) => patch(`/inventory/stock/${id}/tracking/`, { track_inventory }),
  movementsFor: (id, params) => getPaginated(`/inventory/stock/${id}/movements/`, params),

  listMovements: (params) => getPaginated("/inventory/movements/", params),
};

export default inventoryService;
