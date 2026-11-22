import { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "../components/sidebar/Sidebar";
import NavBar from "../components/navbar/NavBar";

/** Fixed sidebar on desktop, drawer on mobile, scrollable content area. */
export default function AdminLayout() {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-100">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="lg:pl-64">
        <NavBar onMenuClick={() => setNavOpen(true)} />
        <main className="px-3 py-4 sm:px-4 lg:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
