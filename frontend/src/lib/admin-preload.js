let pending;
export function preloadDashboard() {
  if (!pending) pending = import("../pages/AdminDashboard").catch(error => { pending = null; throw error; });
  return pending;
}
