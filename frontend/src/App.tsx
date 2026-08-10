import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./contexts/AuthContext";
import { ToastProvider } from "./contexts/ToastContext";
import { AppLayout } from "./layouts/AppLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { CustomerDetailPage } from "./pages/CustomerDetailPage";
import { CustomerFormPage } from "./pages/CustomerFormPage";
import { CustomersPage } from "./pages/CustomersPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PlanDetailPage } from "./pages/PlanDetailPage";
import { PlanFormPage } from "./pages/PlanFormPage";
import { PlansPage } from "./pages/PlansPage";
import { ServicesPage } from "./pages/ServicesPage";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { PublicOnlyRoute } from "./routes/PublicOnlyRoute";

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route element={<PublicOnlyRoute />}>
              <Route path="/login" element={<LoginPage />} />
            </Route>
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route index element={<DashboardPage />} />
                <Route path="clientes" element={<CustomersPage />} />
                <Route path="clientes/nuevo" element={<CustomerFormPage />} />
                <Route path="clientes/:id" element={<CustomerDetailPage />} />
                <Route path="clientes/:id/editar" element={<CustomerFormPage />} />
                <Route path="planes" element={<PlansPage />} />
                <Route path="planes/nuevo" element={<PlanFormPage />} />
                <Route path="planes/servicios" element={<ServicesPage />} />
                <Route path="planes/:id" element={<PlanDetailPage />} />
                <Route path="planes/:id/editar" element={<PlanFormPage />} />
              </Route>
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
