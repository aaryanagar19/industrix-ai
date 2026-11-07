import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./contexts/AuthContext";
import AppLayout from "./layouts/AppLayout";
import { Skeleton } from "./components/ui";
import Login from "./pages/Login";

const P = (f: () => Promise<any>) => lazy(f);
const Dashboard = P(() => import("./pages/Dashboard")), Monitoring = P(() => import("./pages/Monitoring")), MachineDetail = P(() => import("./pages/MachineDetail")),
  Prediction = P(() => import("./pages/Prediction")), Forecast = P(() => import("./pages/Forecast")), Anomalies = P(() => import("./pages/Anomalies")),
  Explain = P(() => import("./pages/Explain")), Twin = P(() => import("./pages/DigitalTwin")), Propagation = P(() => import("./pages/Propagation")),
  Maintenance = P(() => import("./pages/Maintenance")), Incidents = P(() => import("./pages/Incidents")), Emergency = P(() => import("./pages/Emergency")),
  Documents = P(() => import("./pages/Documents")), Reports = P(() => import("./pages/Reports")), Notifications = P(() => import("./pages/Notifications")),
  Users = P(() => import("./pages/Users")), SettingsPage = P(() => import("./pages/Settings"));

export function Protected({ children, roles }: { children: JSX.Element; roles?: string[] }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-10"><Skeleton className="h-8 w-48" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && user.role !== "super_admin" && !roles.includes(user.role)) return <div className="p-10 text-center text-muted" role="alert">Your role does not have access to this page.</div>;
  return children;
}

export default function App() {
  const { user } = useAuth();
  return (
    <Suspense fallback={<div className="p-10"><Skeleton className="h-8 w-48" /></div>}>
      <Routes>
        <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
        <Route element={<Protected><AppLayout /></Protected>}>
          <Route index element={<Dashboard />} />
          <Route path="monitoring" element={<Monitoring />} />
          <Route path="machines/:id" element={<MachineDetail />} />
          <Route path="prediction" element={<Prediction />} />
          <Route path="forecast" element={<Forecast />} />
          <Route path="anomalies" element={<Anomalies />} />
          <Route path="explain" element={<Explain />} />
          <Route path="twin" element={<Twin />} />
          <Route path="propagation" element={<Propagation />} />
          <Route path="maintenance" element={<Maintenance />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="emergency" element={<Emergency />} />
          <Route path="documents" element={<Documents />} />
          <Route path="reports" element={<Reports />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="users" element={<Protected roles={["super_admin"]}><Users /></Protected>} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
