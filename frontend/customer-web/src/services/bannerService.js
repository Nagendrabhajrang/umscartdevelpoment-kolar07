import { get } from "./api";

export const bannerService = {
  getLive: async (params) => {
    const data = await get("/banners/live/", params);
    return Array.isArray(data) ? data : data?.results ?? [];
  },
  registerClick: (id) => get(`/banners/${id}/click/`).catch(() => null),
};

export default bannerService;
