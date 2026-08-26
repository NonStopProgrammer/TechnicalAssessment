import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { AuditTrailPage } from "./pages/AuditTrailPage";
import { LoginPage } from "./pages/LoginPage";
import { QAPage } from "./pages/QAPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ScreeningPage } from "./pages/ScreeningPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/qa" element={<QAPage />} />
        <Route path="/screening" element={<ScreeningPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/audit" element={<AuditTrailPage />} />
        <Route path="/" element={<Navigate to="/qa" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/qa" replace />} />
    </Routes>
  );
}
