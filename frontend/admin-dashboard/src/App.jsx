import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { MotionConfig } from "framer-motion";
import { AdminAuthProvider } from "./context/AdminAuthContext";
import { NotificationProvider } from "./context/NotificationContext";
import { StoreProvider } from "./context/StoreContext";
import ToastContainer from "./components/common/ToastContainer";
import Spinner from "./components/common/Spinner";
import AdminLayout from "./layouts/AdminLayout";
import AdminRoute from "./components/common/AdminRoute";

// Route-level code splitting: the dashboard shell loads first.
const DashboardPage = lazy(() => import("./pages/Dashboard/DashboardPage"));
const OrdersPage = lazy(() => import("./pages/Orders/OrdersPage"));
const OrderDetailsPage = lazy(() => import("./pages/Orders/OrderDetailsPage"));
const PaymentsPage = lazy(() => import("./pages/Payments/PaymentsPage"));
const ProductsPage = lazy(() => import("./pages/Products/ProductsPage"));
const CategoriesPage = lazy(() => import("./pages/Categories/CategoriesPage"));
const InventoryPage = lazy(() => import("./pages/Inventory/InventoryPage"));
const CustomersPage = lazy(() => import("./pages/Customers/CustomersPage"));
const CustomerDetailsPage = lazy(() => import("./pages/Customers/CustomerDetailsPage"));
const PromotionsPage = lazy(() => import("./pages/Promotions/PromotionsPage"));
const BannersPage = lazy(() => import("./pages/Banners/BannersPage"));
const SettingsPage = lazy(() => import("./pages/Settings/SettingsPage"));
const AdminLoginPage = lazy(() => import("./pages/Login/AdminLoginPage"));

function Fallback() {
  return (
    <div className="grid min-h-[50vh] place-items-center" role="status" aria-live="polite">
      <Spinner size="lg" />
    </div>
  );
}

/**
 * Admin routes.
 *
 * `/login` is the only unauthenticated page; everything under the layout is
 * wrapped in `AdminRoute`, which redirects to it when there is no session.
 * The gate is a convenience, not the security boundary - the API rejects
 * unauthenticated admin calls on its own.
 */
export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <NotificationProvider>
        <AdminAuthProvider>
          <StoreProvider>
            <BrowserRouter>
              <ToastContainer />
              <Suspense fallback={<Fallback />}>
                <Routes>
                  <Route path="login" element={<AdminLoginPage />} />
                  <Route
                    element={
                      <AdminRoute>
                        <AdminLayout />
                      </AdminRoute>
                    }
                  >
                    <Route index element={<DashboardPage />} />
                    <Route path="orders" element={<OrdersPage />} />
                    <Route path="orders/:id" element={<OrderDetailsPage />} />
                    <Route path="payments" element={<PaymentsPage />} />
                    <Route path="products" element={<ProductsPage />} />
                    <Route path="categories" element={<CategoriesPage />} />
                    <Route path="inventory" element={<InventoryPage />} />
                    <Route path="customers" element={<CustomersPage />} />
                    <Route path="customers/:id" element={<CustomerDetailsPage />} />
                    <Route path="promotions" element={<PromotionsPage />} />
                    <Route path="banners" element={<BannersPage />} />
                    <Route path="settings" element={<SettingsPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Route>
                </Routes>
              </Suspense>
            </BrowserRouter>
          </StoreProvider>
        </AdminAuthProvider>
      </NotificationProvider>
    </MotionConfig>
  );
}
