# Memora

Memora es una plataforma web para la gestión integral de empresas funerarias. Este repositorio contiene la fundación técnica del Sprint 0: autenticación segura, usuarios, roles, organizaciones, sucursales y una interfaz inicial protegida. Los módulos operativos se incorporarán en sprints posteriores con datos y reglas reales.

## Arquitectura

```text
Memora/
├── backend/                 Django + Django REST Framework
│   ├── accounts/            Usuario, roles y autenticación JWT
│   ├── organizations/       Organizaciones y sucursales
│   ├── core/                Modelos base, respuestas y errores comunes
│   └── memora/              Configuración y rutas del proyecto
└── frontend/                React + TypeScript + Vite
    └── src/
        ├── api/             Cliente HTTP y manejo de tokens
        ├── components/      Componentes compartidos mínimos
        ├── contexts/        Estado de autenticación
        ├── hooks/           Hooks reutilizables
        ├── layouts/         Layout privado responsive
        ├── pages/           Login y dashboard base
        ├── routes/          Protección de rutas
        ├── services/        Operaciones de autenticación
        ├── types/           Contratos TypeScript
        └── utils/           Reservado para utilidades futuras
```

El frontend se comunica exclusivamente con el backend mediante la API REST. SQLite se usa solo como base provisional de desarrollo; la configuración de datos está localizada para facilitar su sustitución antes de producción.

## Requisitos

- Python 3.12 o posterior.
- Node.js 22 o posterior.
- npm 10 o posterior.
- PowerShell en Windows.

## Backend en Windows

Desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\backend\requirements.txt
Copy-Item .\backend\.env.example .\backend\.env
```

Genere un valor local y único para `SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Pegue el resultado en `backend/.env`. Revise también:

- `DEBUG`: `True` únicamente para desarrollo local.
- `ALLOWED_HOSTS`: hosts aceptados, separados por coma.
- `CORS_ALLOWED_ORIGINS`: orígenes completos autorizados, separados por coma.

Prepare la base de datos y ejecute el servidor:

```powershell
Set-Location .\backend
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

El backend estará disponible en `http://127.0.0.1:8000` y Django Admin en `http://127.0.0.1:8000/admin/`.

## Datos locales opcionales

El comando `seed_dev` crea solo una organización, una sucursal y un administrador local. La contraseña siempre debe proporcionarla quien ejecuta el comando y no está almacenada en el repositorio:

```powershell
$env:SEED_ADMIN_PASSWORD = "elija-una-contraseña-local-segura"
python manage.py seed_dev
Remove-Item Env:SEED_ADMIN_PASSWORD
```

Si se ejecuta, el usuario local es `admin.dev` y el correo es `admin@memora.local`; la contraseña es exclusivamente el valor elegido en `SEED_ADMIN_PASSWORD`.

## Frontend en Windows

En una segunda terminal, desde la raíz:

```powershell
Set-Location .\frontend
Copy-Item .env.example .env
npm install
npm run dev
```

La aplicación estará disponible en `http://localhost:5173`. `VITE_API_BASE_URL` debe apuntar a la base `/api` del backend, por ejemplo `http://localhost:8000/api`.

## API disponible

| Método | Ruta | Acceso | Propósito |
| --- | --- | --- | --- |
| `POST` | `/api/auth/login/` | Público | Autentica por correo o usuario y entrega tokens JWT. |
| `POST` | `/api/auth/refresh/` | Público | Renueva el access token. |
| `GET` | `/api/auth/me/` | Privado | Devuelve identidad, rol, organización, sucursal y permisos básicos. |

Login recibe:

```json
{
  "identifier": "usuario-o-correo",
  "password": "contraseña"
}
```

Las respuestas de error mantienen esta estructura:

```json
{
  "success": false,
  "message": "Descripción del error",
  "errors": {}
}
```

## Validación

Backend:

```powershell
Set-Location .\backend
python manage.py check
python manage.py makemigrations --check
python manage.py migrate
python manage.py test
```

Frontend:

```powershell
Set-Location .\frontend
npm install
npm run build
```

## Preparación para producción

Antes de un despliegue en AWS se deberá configurar una base de datos administrada, almacenamiento persistente para archivos, servicio de estáticos, secretos del entorno, HTTPS, observabilidad, copias de seguridad y políticas de rotación/revocación de tokens. Ninguna de esas decisiones se simula en este sprint.

