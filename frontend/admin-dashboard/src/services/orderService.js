import { get, getPaginated, post } from "./api";

/** Orders, the status machine and dashboard stats. */
export const orderService = {
  list: (params) => getPaginated("/orders/", params),
  get: (id) => get(`/orders/${id}/`),
  stats: (params) => get("/orders/stats/", params),
  active: (params) => getPaginated("/orders/active/", params),

  updateStatus: (id, status, note) => post(`/orders/${id}/status/`, { status, note }),
  confirm: (id) => post(`/orders/${id}/confirm/`, {}),
  markDelivered: (id) => post(`/orders/${id}/mark-delivered/`, {}),
  history: (id) => get(`/orders/${id}/history/`),
};

export default orderService;
