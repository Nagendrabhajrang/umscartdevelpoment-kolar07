import { get, getPaginated, post, patch, del, postMultipart } from "./api";

/**
 * Categories, products and product images - full admin CRUD.
 * Every function maps to a documented endpoint; nothing is invented.
 */
export const catalogService = {
  /* ---------------- Categories ---------------- */
  getCategories: (params) => getPaginated("/catalog/categories/", params),
  getAllCategories: async (params) => {
    const page = await getPaginated("/catalog/categories/", { page_size: 200, ...params });
    return page.results;
  },
  getCategoryTree: async () => {
    const data = await get("/catalog/categories/tree/");
    return Array.isArray(data) ? data : data?.results ?? [];
  },
  getCategory: (id) => get(`/catalog/categories/${id}/`),
  createCategory: (payload) => post("/catalog/categories/", payload),
  /** `image` may be a File - switches to multipart automatically. */
  updateCategory: (id, payload) =>
    payload.image instanceof File ? postMultipart(`/catalog/categories/${id}/`, payload, "patch") : patch(`/catalog/categories/${id}/`, payload),
  deleteCategory: (id) => del(`/catalog/categories/${id}/`),

  /* ---------------- Products ---------------- */
  getProducts: (params) => getPaginated("/catalog/products/", params),
  getProduct: (id) => get(`/catalog/products/${id}/`),
  createProduct: (payload) =>
    payload.image instanceof File ? postMultipart("/catalog/products/", payload) : post("/catalog/products/", payload),
  updateProduct: (id, payload) =>
    payload.image instanceof File ? postMultipart(`/catalog/products/${id}/`, payload, "patch") : patch(`/catalog/products/${id}/`, payload),
  deleteProduct: (id) => del(`/catalog/products/${id}/`),
  setProductStatus: (id, status) => post(`/catalog/products/${id}/status/`, { status }),
  getProductImages: (productId) => get(`/catalog/products/${productId}/images/`),

  /* ---------------- Product images ---------------- */
  listImages: (params) => getPaginated("/catalog/product-images/", params),
  createImage: (payload) => postMultipart("/catalog/product-images/", payload),
  createImageForProduct: (payload) => postMultipart("/catalog/product-images/", payload),
  updateImage: (id, payload) =>
    payload.image instanceof File ? postMultipart(`/catalog/product-images/${id}/`, payload, "patch") : patch(`/catalog/product-images/${id}/`, payload),
  deleteImage: (id) => del(`/catalog/product-images/${id}/`),
};

export default catalogService;
