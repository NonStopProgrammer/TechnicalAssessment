import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { auth, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">FinServ Compliance Assistant</div>
        <nav>
          <NavLink to="/qa">Q&amp;A</NavLink>
          <NavLink to="/screening">Screening</NavLink>
          <NavLink to="/reports">Reports</NavLink>
          <NavLink to="/audit">Audit Trail</NavLink>
        </nav>
        {auth && (
          <div className="user-chip">
            <span>
              {auth.userId} · {auth.role}
            </span>
            <button onClick={logout}>Log out</button>
          </div>
        )}
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}
