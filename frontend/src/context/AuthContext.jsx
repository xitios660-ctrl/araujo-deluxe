import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api, apiError } from "../lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [authError, setAuthError] = useState(null);
  const revision = useRef(0);

  useEffect(() => {
    const token = localStorage.getItem("ad_token");
    if (!token) {
      setUser(false);
      return;
    }
    const controller = new AbortController();
    const current = revision.current;
    api.get("/auth/me", { signal: controller.signal, timeout: 90000 })
      .then(r => { if (current === revision.current) { setUser(r.data); setAuthError(null); } })
      .catch(error => {
        if (controller.signal.aborted || current !== revision.current) return;
        if (error.response?.status === 401 || error.response?.status === 403) {
          localStorage.removeItem("ad_token");
          setUser(false);
        } else {
          setAuthError(apiError(error, "Não foi possível verificar sua sessão."));
        }
      });
    return () => controller.abort();
  }, []);

  const login = async (password) => {
    const current = ++revision.current;
    setAuthError(null);
    const { data } = await api.post("/auth/login", { password }, { timeout: 90000 });
    if (current !== revision.current) return null;
    localStorage.setItem("ad_token", data.access_token);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    revision.current++;
    setAuthError(null);
    localStorage.removeItem("ad_token");
    setUser(false);
  };

  return <AuthContext.Provider value={{ user, login, logout, authError }}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
