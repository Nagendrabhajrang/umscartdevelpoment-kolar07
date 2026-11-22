import { get, getPaginated } from "./api";

/** Category listing + tree used by the home page and category page. */
export const catalogService = {
  getCategories: (params) => getPaginated("/catalog/categories/", params),
  getAllCategories: async (params) => {
    const first = await get("/catalog/categories/", { ...params, page_size: 100 });
    return first?.results ?? [];
  },
  getCategoryTree: async () => {
    const data = await get("/catalog/categories/tree/");
    return Array.isArray(data) ? data : data?.results ?? [];
  },
  getCategory: (id) => get(`/catalog/categories/${id}/`),

  getProducts: (params) => getPaginated("/catalog/products/", params),
  getProduct: (id) => get(`/catalog/products/${id}/`),
  getFeatured: (params) => getPaginated("/catalog/products/featured/", params),
  getRelated: (id) => get(`/catalog/products/${id}/related/`),
  getProductImages: (id) => get(`/catalog/products/${id}/images/`),
};

export default catalogService;
