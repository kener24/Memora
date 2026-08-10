import { CalendarClock, ChevronDown, FileSignature, Home, Layers3, LogOut, Menu, PanelLeftClose, Users, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { Brand } from "../components/Brand";
import { useAuth } from "../contexts/AuthContext";

export function AppLayout() {
  const { user, signOut } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    function closeProfile(event: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", closeProfile);
    return () => document.removeEventListener("mousedown", closeProfile);
  }, []);

  const fullName = [user?.nombre, user?.apellido].filter(Boolean).join(" ") || user?.email || "Usuario";
  const initials = fullName
    .split(" ")
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
  const pageTitle = location.pathname.startsWith("/clientes") ? "Clientes" : location.pathname.startsWith("/planes") ? "Planes" : location.pathname.startsWith("/contratos") ? "Contratos" : location.pathname.startsWith("/cuotas") ? "Cuotas" : "Inicio";

  function handleSignOut() {
    setProfileOpen(false);
    signOut();
    navigate("/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <button
        className={`sidebar-scrim ${sidebarOpen ? "sidebar-scrim--visible" : ""}`}
        aria-label="Cerrar menú"
        onClick={() => setSidebarOpen(false)}
      />

      <aside className={`sidebar ${sidebarOpen ? "sidebar--open" : ""}`} aria-label="Navegación principal">
        <div className="sidebar__top">
          <Brand inverse />
          <button className="icon-button sidebar__close" onClick={() => setSidebarOpen(false)} aria-label="Cerrar menú">
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar__nav">
          <p className="sidebar__label">Espacio de trabajo</p>
          <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}>
            <Home size={19} strokeWidth={1.8} />
            <span>Inicio</span>
          </NavLink>
          {user?.permisos.clientes.view && (
            <NavLink to="/clientes" className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}>
              <Users size={19} strokeWidth={1.8} />
              <span>Clientes</span>
            </NavLink>
          )}
          {user?.permisos.planes.view && (
            <NavLink to="/planes" className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}>
              <Layers3 size={19} strokeWidth={1.8} />
              <span>Planes</span>
            </NavLink>
          )}
          {user?.permisos.contratos.view && (
            <NavLink to="/contratos" className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}>
              <FileSignature size={19} strokeWidth={1.8} />
              <span>Contratos</span>
            </NavLink>
          )}
          {user?.permisos.cuotas.view_installments && (
            <NavLink to="/cuotas" className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}>
              <CalendarClock size={19} strokeWidth={1.8} />
              <span>Cuotas</span>
            </NavLink>
          )}
        </nav>

        <div className="sidebar__footer">
          <div className="sidebar__organization">
            <span className="sidebar__organization-mark" aria-hidden="true">
              {user?.organizacion?.nombre.charAt(0).toUpperCase() ?? "M"}
            </span>
            <span>
              <small>Organización</small>
              <strong>{user?.organizacion?.nombre ?? "Administración global"}</strong>
            </span>
          </div>
          <div className="sidebar__foundation">
            <PanelLeftClose size={16} aria-hidden="true" />
            <span>Cuotas y calendario · Sprint 4</span>
          </div>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="topbar__left">
            <button className="icon-button menu-button" onClick={() => setSidebarOpen(true)} aria-label="Abrir menú">
              <Menu size={22} />
            </button>
            <div>
              <p className="topbar__eyebrow">Memora</p>
              <h1>{pageTitle}</h1>
            </div>
          </div>

          <div className="profile-menu" ref={profileRef}>
            <button
              className="profile-trigger"
              onClick={() => setProfileOpen((open) => !open)}
              aria-expanded={profileOpen}
              aria-haspopup="menu"
            >
              <span className="avatar" aria-hidden="true">{initials || "U"}</span>
              <span className="profile-trigger__copy">
                <strong>{fullName}</strong>
                <small>{user?.rol?.nombre ?? "Sin rol asignado"}</small>
              </span>
              <ChevronDown size={16} aria-hidden="true" />
            </button>
            {profileOpen && (
              <div className="profile-popover" role="menu">
                <div className="profile-popover__identity">
                  <strong>{fullName}</strong>
                  <span>{user?.email}</span>
                </div>
                <button role="menuitem" onClick={handleSignOut}>
                  <LogOut size={17} />
                  Cerrar sesión
                </button>
              </div>
            )}
          </div>
        </header>

        <main className="content-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
