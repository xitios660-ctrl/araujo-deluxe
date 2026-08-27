import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Lock } from "@phosphor-icons/react";
import { useAuth } from "../context/AuthContext";
import { apiError } from "../lib/api";

export default function AdminLogin() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user && user !== false) navigate("/admin/dashboard");
  }, [user, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(password);
      navigate("/admin/dashboard");
    } catch (err) {
      toast.error(apiError(err, "Não foi possível entrar"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#221A0E] grain flex items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="glass-dark rounded-[2rem] p-10 w-full max-w-md relative z-10"
        data-testid="admin-login-card"
      >
        <div className="rounded-full bg-primary/20 w-14 h-14 flex items-center justify-center mb-6">
          <Lock size={26} className="text-primary" weight="duotone" />
        </div>
        <h1 className="font-display text-3xl text-white">Área do Gestor</h1>
        <p className="text-white/50 text-sm mt-2">Digite sua senha para acessar a agenda.</p>
        <form onSubmit={submit} className="mt-8 space-y-4">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Senha"
            required
            className="w-full rounded-xl bg-white/10 border border-white/20 text-white placeholder:text-white/40 px-5 py-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            data-testid="admin-login-password"
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-full bg-primary text-white font-semibold py-4 transition-transform duration-300 hover:scale-[1.02] hover:bg-[#a3822b] disabled:opacity-50"
            data-testid="admin-login-submit"
          >
            {loading ? "Entrando…" : "Entrar"}
          </button>
        </form>
        <Link to="/" className="block text-center text-white/40 text-xs mt-6 hover:text-primary transition-colors duration-300" data-testid="admin-login-back">
          ← Voltar ao site
        </Link>
      </motion.div>
    </div>
  );
}
