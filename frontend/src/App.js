import "@/App.css";
import { HashRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider } from "@/context/AuthContext";
import { lazy, Suspense } from "react";
import { preloadDashboard } from "./lib/admin-preload";
const Landing = lazy(() => import("./pages/Landing"));
const AdminLogin = lazy(() => import("./pages/AdminLogin"));
const AdminDashboard = lazy(preloadDashboard);

function App() {
  return (
    <AuthProvider>
      <HashRouter>
        <Suspense fallback={<div role="status" className="min-h-screen bg-[#F1EBDD] flex items-center justify-center text-stone-700">Carregando…</div>}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/admin" element={<AdminLogin />} />
          <Route path="/admin/dashboard" element={<AdminDashboard />} />
        </Routes>
        </Suspense>
      </HashRouter>
      <Toaster position="top-center" richColors />
    </AuthProvider>
  );
}

export default App;
