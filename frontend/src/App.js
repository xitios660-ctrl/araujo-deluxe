import React from "react";
import "./App.css";
import { HashRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { CartProvider } from "./context/CartContext";
import Home from "./pages/Home";
import Checkout from "./pages/Checkout";
import OrderConfirmation from "./pages/OrderConfirmation";
import TrackOrder from "./pages/TrackOrder";
import Admin from "./pages/Admin";

function App() {
  return (
    <div className="App">
      <CartProvider>
        <HashRouter>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/checkout" element={<Checkout />} />
            <Route path="/pedido/:orderNumber" element={<OrderConfirmation />} />
            <Route path="/rastreio" element={<TrackOrder />} />
            <Route path="/rastreio/:orderNumber" element={<TrackOrder />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </HashRouter>
        <Toaster position="top-center" richColors />
      </CartProvider>
    </div>
  );
}

export default App;
