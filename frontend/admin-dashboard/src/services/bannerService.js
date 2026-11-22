import { get, getPaginated, post, patch, del, postMultipart } from "./api";

export const bannerService = {
  list: (params) => getPaginated("/banners/", params),
  get: (id) => get(`/banners/${id}/`),
  live: () => get("/banners/live/"),
  create: (payload) => postMultipart("/banners/", payload),
  update: (id, payload) => postMultipart(`/banners/${id}/`, payload, "patch"),
  remove: (id) => del(`/banners/${id}/`),
  toggle: (id) => post(`/banners/${id}/toggle/`, {}),
};

export default bannerService;
