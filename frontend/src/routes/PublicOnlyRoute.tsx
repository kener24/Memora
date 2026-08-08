import { Navigate, Outlet } from "react-router-dom";

import { FullPageLoader } from "../components/FullPageLoader";
import { useAuth } from "../contexts/AuthContext";

export function PublicOnlyRoute() {
  const { status } = useAuth();
  if (status === "loading") return <FullPageLoader />;
  if (status === "authenticated") return <Navigate to="/" replace />;
  return <Outlet />;
}

