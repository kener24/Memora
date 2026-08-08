import { ArrowRight, Eye, EyeOff, LockKeyhole, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { Brand } from "../components/Brand";
import { useAuth } from "../contexts/AuthContext";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

interface LocationState {
  from?: string;
}

export function LoginPage() {
  useDocumentTitle("Iniciar sesión");
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await signIn(identifier.trim(), password);
      const destination = (location.state as LocationState | null)?.from ?? "/";
      navigate(destination, { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No fue posible iniciar sesión. Inténtelo nuevamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-story" aria-label="Presentación de Memora">
        <div className="login-story__inner">
          <Brand inverse />
          <div className="login-story__message">
            <span className="section-kicker">Gestión con propósito</span>
            <h1>Más claridad para acompañar mejor.</h1>
            <p>
              Una plataforma serena y confiable para organizar el trabajo de su empresa desde un solo lugar.
            </p>
          </div>
          <div className="login-story__trust">
            <ShieldCheck size={21} aria-hidden="true" />
            <span>Acceso privado y protegido</span>
          </div>
        </div>
        <div className="login-story__glow" aria-hidden="true" />
      </section>

      <section className="login-panel">
        <div className="login-panel__mobile-brand"><Brand /></div>
        <div className="login-card">
          <div className="login-card__heading">
            <span className="login-card__icon" aria-hidden="true"><LockKeyhole size={22} /></span>
            <div>
              <p className="section-kicker">Portal seguro</p>
              <h2>Bienvenido de nuevo</h2>
            </div>
            <p>Ingrese sus credenciales para continuar a su espacio de trabajo.</p>
          </div>

          <form onSubmit={handleSubmit} noValidate>
            <div className="field-group">
              <label htmlFor="identifier">Correo o usuario</label>
              <input
                id="identifier"
                name="identifier"
                type="text"
                autoComplete="username"
                value={identifier}
                onChange={(event) => setIdentifier(event.target.value)}
                placeholder="nombre@empresa.com"
                required
                autoFocus
                disabled={loading}
              />
            </div>

            <div className="field-group">
              <label htmlFor="password">Contraseña</label>
              <div className="password-field">
                <input
                  id="password"
                  name="password"
                  type={passwordVisible ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Ingrese su contraseña"
                  required
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setPasswordVisible((visible) => !visible)}
                  aria-label={passwordVisible ? "Ocultar contraseña" : "Mostrar contraseña"}
                  disabled={loading}
                >
                  {passwordVisible ? <EyeOff size={19} /> : <Eye size={19} />}
                </button>
              </div>
            </div>

            {error && <div className="form-error" role="alert">{error}</div>}

            <button className="primary-button" type="submit" disabled={loading || !identifier.trim() || !password}>
              {loading ? (
                <><span className="button-spinner" aria-hidden="true" /> Iniciando sesión…</>
              ) : (
                <>Iniciar sesión <ArrowRight size={18} aria-hidden="true" /></>
              )}
            </button>
          </form>

          <p className="login-card__support">El acceso es administrado por su empresa.</p>
        </div>
      </section>
    </main>
  );
}

