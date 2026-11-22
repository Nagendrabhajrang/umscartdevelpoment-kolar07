import { get, getPaginated, post, patch, del } from "./api";

export const promotionService = {
  list: (params) => getPaginated("/promotions/", params),
  get: (id) => get(`/promotions/${id}/`),
  create: (payload) => post("/promotions/", payload),
  update: (id, payload) => patch(`/promotions/${id}/`, payload),
  remove: (id) => del(`/promotions/${id}/`),
  toggle: (id) => post(`/promotions/${id}/toggle/`, {}),
  summary: () => get("/promotions/summary/"),
  redemptions: (params) => getPaginated("/promotions/redemptions/", params),
};

export default promotionService;
