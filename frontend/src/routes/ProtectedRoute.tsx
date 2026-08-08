import { Navigate, Outlet, useLocation } from "react-router-dom";

import { FullPageLoader } from "../components/FullPageLoader";
import { useAuth } from "../contexts/AuthContext";

export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") return <FullPageLoader />;
  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

