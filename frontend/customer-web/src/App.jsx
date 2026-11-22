import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { NotificationProvider } from "./context/NotificationContext";
import { AuthProvider } from "./context/AuthContext";
import { StoreProvider } from "./context/StoreContext";
import { CustomerProvider } from "./context/CustomerContext";
import { CartProvider } from "./context/CartContext";
import { WishlistProvider } from "./context/WishlistContext";
import ToastContainer from "./components/common/ToastContainer";
import Spinner from "./components/common/Spinner";
import RequireAuth from "./components/common/RequireAuth";
import MainLayout from "./layouts/MainLayout";

// Route-level code splitting, same as the admin dashboard.
const HomePage = lazy(() => import("./pages/Home/HomePage"));
const CategoriesPage = lazy(() => import("./pages/Categories/CategoriesPage"));
const ProductsPage = lazy(() => import("./pages/Products/ProductsPage"));
const ProductDetailsPage = lazy(() => import("./pages/ProductDetails/ProductDetailsPage"));
const SearchPage = lazy(() => import("./pages/Search/SearchPage"));
const CartPage = lazy(() => import("./pages/Cart/CartPage"));
const CheckoutPage = lazy(() => import("./pages/Checkout/CheckoutPage"));
const OrdersPage = lazy(() => import("./pages/Orders/OrdersPage"));
const OrderDetailsPage = lazy(() => import("./pages/Orders/OrderDetailsPage"));
const HelpPage = lazy(() => import("./pages/Help/HelpPage"));
const LoginPage = lazy(() => import("./pages/Login/LoginPage"));
const ProfilePage = lazy(() => import("./pages/Profile/ProfilePage"));
const AddressesPage = lazy(() => import("./pages/Addresses/AddressesPage"));
const WishlistPage = lazy(() => import("./pages/Wishlist/WishlistPage"));
const OrderLookupPage = lazy(() => import("./pages/Orders/OrderLookupPage"));
const NotFoundPage = lazy(() => import("./pages/NotFound/NotFoundPage"));

function Fallback() {
  return (
    <div className="grid min-h-[50vh] place-items-center" role="status" aria-live="polite">
      <Spinner size="lg" label="Loading page" />
    </div>
  );
}

/**
 * Customer storefront routes.
 *
 * Round 27 - guest shopping with checkout-time authentication.
 *
 * Everything a shopper does before paying is public: browse, search, filter,
 * add to cart, change quantities, view the cart. Authentication is required only
 * for the things that genuinely belong to an account:
 *
 *   /checkout   - signing in there is the "login to continue with your order"
 *                 step; the basket travels through the login untouched
 *   /orders     - the customer's own order history
 *   /profile    - their saved details
 *   /addresses  - their address book
 *   /wishlist   - saved products
 *
 * Provider order: Auth owns the session and must sit above Customer, which
 * resolves the acting shopper from it. Store provides settings + dataVersion;
 * Cart and Wishlist read dataVersion. BrowserRouter sits above the providers
 * that navigate.
 */
export default function App() {
  return (
    <NotificationProvider>
      <AuthProvider>
        <StoreProvider>
          <BrowserRouter>
            <CustomerProvider>
              <CartProvider>
                <WishlistProvider>
                  <ToastContainer />
                  <Suspense fallback={<Fallback />}>
                    <Routes>
                      <Route element={<MainLayout />}>
                        {/* --- public: no account needed --- */}
                        <Route index element={<HomePage />} />
                        <Route path="categories" element={<CategoriesPage />} />
                        <Route path="products" element={<ProductsPage />} />
                        <Route path="product/:id" element={<ProductDetailsPage />} />
                        <Route path="search" element={<SearchPage />} />
                        <Route path="cart" element={<CartPage />} />
                        <Route path="login" element={<LoginPage />} />
                        {/* Order lookup by number + mobile: no account needed. */}
                        <Route path="track" element={<OrderLookupPage />} />
                        <Route path="help" element={<HelpPage />} />
                        {/* /support was the old ticket page; keep the URL working. */}
                        <Route path="support" element={<HelpPage />} />

                        {/* --- account pages --- */}
                        <Route
                          path="checkout"
                          element={
                            <RequireAuth>
                              <CheckoutPage />
                            </RequireAuth>
                          }
                        />
                        <Route
                          path="orders"
                          element={
                            <RequireAuth>
                              <OrdersPage />
                            </RequireAuth>
                          }
                        />
                        <Route
                          path="orders/:id"
                          element={
                            <RequireAuth>
                              <OrderDetailsPage />
                            </RequireAuth>
                          }
                        />
                        <Route
                          path="profile"
                          element={
                            <RequireAuth>
                              <ProfilePage />
                            </RequireAuth>
                          }
                        />
                        <Route
                          path="addresses"
                          element={
                            <RequireAuth>
                              <AddressesPage />
                            </RequireAuth>
                          }
                        />
                        <Route
                          path="wishlist"
                          element={
                            <RequireAuth>
                              <WishlistPage />
                            </RequireAuth>
                          }
                        />

                        <Route path="404" element={<NotFoundPage />} />
                        <Route path="*" element={<Navigate to="/404" replace />} />
                      </Route>
                    </Routes>
                  </Suspense>
                </WishlistProvider>
              </CartProvider>
            </CustomerProvider>
          </BrowserRouter>
        </StoreProvider>
      </AuthProvider>
    </NotificationProvider>
  );
}
