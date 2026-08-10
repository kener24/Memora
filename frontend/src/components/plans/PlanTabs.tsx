import { ClipboardList, Library } from "lucide-react";
import { NavLink } from "react-router-dom";


export function PlanTabs() {
  return (
    <nav className="module-tabs" aria-label="Secciones de planes">
      <NavLink to="/planes" end className={({ isActive }) => isActive ? "module-tab module-tab--active" : "module-tab"}>
        <ClipboardList size={17} /> Planes funerarios
      </NavLink>
      <NavLink to="/planes/servicios" className={({ isActive }) => isActive ? "module-tab module-tab--active" : "module-tab"}>
        <Library size={17} /> Catálogo de servicios
      </NavLink>
    </nav>
  );
}
