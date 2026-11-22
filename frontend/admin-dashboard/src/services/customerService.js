import { get, getPaginated, post, patch } from "./api";

export const customerService = {
  list: (params) => getPaginated("/customers/", params),
  get: (id) => get(`/customers/${id}/`),
  summary: () => get("/customers/summary/"),
  create: (payload) => post("/customers/", payload),
  update: (id, payload) => patch(`/customers/${id}/`, payload),

  setStatus: (id, status) => post(`/customers/${id}/status/`, { status }),
  addNote: (id, note) => post(`/customers/${id}/notes/`, { note }),
  notes: (id, params) => getPaginated(`/customers/${id}/notes/`, params),
};

export default customerService;
