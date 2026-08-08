import { Link } from "react-router-dom";

import { useDocumentTitle } from "../hooks/useDocumentTitle";

export function NotFoundPage() {
  useDocumentTitle("Página no encontrada");
  return (
    <main className="not-found">
      <span>404</span>
      <h1>Esta página no está disponible.</h1>
      <p>La dirección puede ser incorrecta o la sección todavía no existe.</p>
      <Link to="/">Volver al inicio</Link>
    </main>
  );
}

