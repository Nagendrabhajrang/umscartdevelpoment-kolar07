import { get, getPaginated, post, patch, del } from "./api";

/** Customer addresses - admin read + default flag. */
export const addressService = {
  list: (params) => getPaginated("/addresses/", params),
  get: (id) => get(`/addresses/${id}/`),
  update: (id, payload) => patch(`/addresses/${id}/`, payload),
  remove: (id) => del(`/addresses/${id}/`),
  setDefault: (id) => post(`/addresses/${id}/set-default/`, {}),
};

export default addressService;
