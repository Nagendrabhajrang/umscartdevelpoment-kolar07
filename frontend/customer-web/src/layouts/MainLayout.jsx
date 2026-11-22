import { Outlet } from "react-router-dom";
import NavBar from "../components/layout/NavBar";
import FootBar from "../components/layout/FootBar";
import ScrollToTop from "../components/common/ScrollToTop";
import StoreClosedBanner from "../components/common/StoreClosedBanner";
import BadgeStyles from "../components/common/BadgePop";

/**
 * Shell for every customer page: header, page slot, footer.
 *
 * The slot is a bare <Outlet /> — the same shape the admin dashboard uses.
 * There is no AnimatePresence and no pathname key, so navigating can never
 * wait for an exit animation and navigation can never be blocked.
 */
export default function MainLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <BadgeStyles />
      <ScrollToTop />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-brand-700 focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>
      <NavBar />
      <StoreClosedBanner />
      <main id="main" className="flex-1 pb-16 sm:pb-8">
        <Outlet />
      </main>
      <FootBar />
    </div>
  );
}
