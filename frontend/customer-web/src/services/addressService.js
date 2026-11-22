import { get, post, patch, put, del } from "./api";

export const addressService = {
  listMine: async () => {
    const data = await get("/addresses/mine/");
    return Array.isArray(data) ? data : data?.results ?? [];
  },
  list: (params) => get("/addresses/", params),
  get: (id) => get(`/addresses/${id}/`),
  create: (payload) => post("/addresses/", payload),
  createMine: (payload) => post("/addresses/mine/add/", payload),
  update: (id, payload) => patch(`/addresses/${id}/`, payload),
  replace: (id, payload) => put(`/addresses/${id}/`, payload),
  remove: (id) => del(`/addresses/${id}/`),
  setDefault: (id) => post(`/addresses/${id}/set-default/`, {}),
};

export default addressService;
