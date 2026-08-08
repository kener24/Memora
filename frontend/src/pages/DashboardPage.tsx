import { Building2, MapPin, ShieldCheck, Sparkles } from "lucide-react";

import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

export function DashboardPage() {
  useDocumentTitle("Inicio");
  const { user } = useAuth();
  const displayName = user?.nombre || user?.email || "usuario";

  return (
    <div className="dashboard">
      <section className="welcome-card">
        <div className="welcome-card__content">
          <span className="welcome-card__kicker"><Sparkles size={15} /> Espacio preparado</span>
          <h2>Bienvenido, {displayName}</h2>
          <p>
            La base de Memora está lista. Desde aquí tendrá acceso a las herramientas de gestión a medida que sean habilitadas.
          </p>
        </div>
        <div className="welcome-card__monogram" aria-hidden="true">M</div>
      </section>

      <section className="workspace-section" aria-labelledby="workspace-title">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Su espacio</p>
            <h2 id="workspace-title">Información de acceso</h2>
          </div>
          <span className="security-badge"><ShieldCheck size={16} /> Sesión protegida</span>
        </div>

        <div className="identity-grid">
          <article className="identity-card">
            <span className="identity-card__icon"><Building2 size={20} /></span>
            <div>
              <span>Organización</span>
              <strong>{user?.organizacion?.nombre ?? "Administración global"}</strong>
            </div>
          </article>
          <article className="identity-card">
            <span className="identity-card__icon identity-card__icon--sage"><ShieldCheck size={20} /></span>
            <div>
              <span>Rol</span>
              <strong>{user?.rol?.nombre ?? "Sin rol asignado"}</strong>
            </div>
          </article>
          <article className="identity-card">
            <span className="identity-card__icon identity-card__icon--sand"><MapPin size={20} /></span>
            <div>
              <span>Sucursal</span>
              <strong>{user?.sucursal?.nombre ?? "No asignada"}</strong>
            </div>
          </article>
        </div>
      </section>

      <section className="coming-soon" aria-label="Próximas funciones">
        <span className="coming-soon__line" aria-hidden="true" />
        <div>
          <p className="section-kicker">Próximamente</p>
          <h2>Los indicadores del negocio estarán disponibles próximamente.</h2>
          <p>Se incorporarán únicamente cuando existan datos reales y módulos operativos.</p>
        </div>
      </section>
    </div>
  );
}

