# Memora

Memora es una plataforma web para la gestión integral de empresas funerarias. Incluye autenticación segura, clientes y beneficiarios, catálogo de planes y la venta contractual completa con snapshots históricos y PDF profesional. Los pagos reales y la operación funeraria pertenecen a sprints posteriores.

## Arquitectura

```text
Memora/
├── backend/                 Django + Django REST Framework
│   ├── accounts/            Usuario, roles y autenticación JWT
│   ├── organizations/       Organizaciones y sucursales
│   ├── customers/           Clientes, beneficiarios, contactos e historial
│   ├── plans/               Planes, prestaciones, disponibilidad e historial
│   ├── contracts/           Contratos, ventas, snapshots, auditoría y PDF
│   ├── core/                Modelos base, respuestas y errores comunes
│   └── memora/              Configuración y rutas del proyecto
└── frontend/                React + TypeScript + Vite
    └── src/
        ├── api/             Cliente HTTP y manejo de tokens
        ├── components/      Componentes compartidos mínimos
        ├── contexts/        Estado de autenticación
        ├── hooks/           Hooks reutilizables
        ├── layouts/         Layout privado responsive
        ├── pages/           Login, clientes, planes y catálogo de servicios
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

El comando `seed_dev` crea una organización, una sucursal, un administrador, dos clientes, beneficiarios, un catálogo, un plan y un contrato activo de demostración. La contraseña siempre debe proporcionarla quien ejecuta el comando y no está almacenada en el repositorio:

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
| `GET` | `/api/customers/` | Según rol | Lista, busca, filtra, ordena y pagina clientes dentro del alcance permitido. |
| `POST` | `/api/customers/` | Admin, manager, seller | Registra un cliente asignando organización, creador y código desde backend. |
| `GET` | `/api/customers/{id}/` | Según alcance | Obtiene la ficha con beneficiarios, contactos e historial. |
| `PATCH` | `/api/customers/{id}/` | Admin, manager, seller | Actualiza información autorizada. |
| `POST` | `/api/customers/{id}/activate/` | Admin | Reactiva un cliente. |
| `POST` | `/api/customers/{id}/deactivate/` | Admin | Inactiva un cliente sin eliminarlo. |
| `POST` | `/api/customers/check-duplicates/` | Roles de creación | Comprueba coincidencias de identidad y teléfono. |
| `GET` | `/api/customers/options/` | Lectura | Entrega catálogos, sucursales y permisos del usuario. |
| `GET/POST` | `/api/customers/{id}/beneficiaries/` | Según rol | Lista o agrega beneficiarios. |
| `PATCH` | `/api/customers/{id}/beneficiaries/{id}/` | Según rol | Edita o activa/inactiva un beneficiario. |
| `GET/POST` | `/api/customers/{id}/contacts/` | Según rol | Lista o agrega contactos de referencia. |
| `PATCH` | `/api/customers/{id}/contacts/{id}/` | Según rol | Edita, activa/inactiva o selecciona el contacto principal. |
| `GET/POST` | `/api/plans/` | Según rol | Lista o crea planes con prestaciones y disponibilidad en una transacción. |
| `GET/PATCH` | `/api/plans/{id}/` | Según rol | Consulta o actualiza el detalle completo de un plan. |
| `POST` | `/api/plans/{id}/activate/` | Admin | Reactiva el plan. |
| `POST` | `/api/plans/{id}/deactivate/` | Admin | Inactiva el plan sin eliminar su configuración. |
| `POST` | `/api/plans/{id}/duplicate/` | Admin, manager | Duplica configuración, prestaciones y sucursales atómicamente. |
| `GET` | `/api/plans/options/` | Lectura | Entrega categorías, unidades, sucursales y permisos. |
| `GET/POST` | `/api/plans/services/` | Según rol | Consulta o agrega prestaciones al catálogo. |
| `GET/PATCH` | `/api/plans/services/{id}/` | Según rol | Consulta o edita una prestación. |
| `POST` | `/api/plans/services/{id}/activate/` | Admin | Reactiva una prestación. |
| `POST` | `/api/plans/services/{id}/deactivate/` | Admin | Inactiva una prestación sin retirarla de planes existentes. |
| `GET/POST` | `/api/contracts/` | Según rol | Lista contratos o crea un borrador con clave de idempotencia. |
| `GET/PATCH` | `/api/contracts/{id}/` | Según alcance | Consulta el snapshot o modifica únicamente un borrador. |
| `POST` | `/api/contracts/{id}/confirm/` | Admin, manager, seller | Confirma atómicamente y congela cliente, beneficiario, plan y prestaciones. |
| `POST` | `/api/contracts/{id}/cancel/` | Admin, manager | Cancela de forma irreversible, con motivo y auditoría. |
| `GET` | `/api/contracts/{id}/pdf/` | Lectura | Genera el documento contractual desde el snapshot histórico. |
| `GET` | `/api/contracts/options/` | Lectura | Entrega estados, frecuencias, sucursales, vendedores y permisos. |

Las operaciones de creación y confirmación requieren el encabezado `Idempotency-Key`. Repetir una solicitud con la misma clave recupera el mismo resultado sin duplicar ventas.

### Permisos de contratos

- `superadmin`: acceso global, gestión y costos internos.
- `admin` y `manager`: crean, confirman, aplican descuentos y cancelan dentro de su organización.
- `seller`: vende únicamente en su sucursal, queda fijado como vendedor y nunca recibe costos internos ni aplica descuentos.
- `collector` y `cashier`: lectura de contratos de su sucursal.
- `accountant`: lectura organizacional con costos internos, sin crear ni modificar.
- `inventory`: sin acceso al módulo.

### Decisiones del módulo de contratos

- Los números `CTR-000001` provienen de una secuencia transaccional por organización.
- Un contrato confirmado es inmutable; solo los borradores pueden editarse.
- La confirmación copia datos comerciales y prestaciones en snapshots históricos.
- La prima, cuota y primer vencimiento son condiciones futuras; no registran dinero recibido ni generan cuotas reales.
- El PDF utiliza exclusivamente el snapshot contractual, incluso si luego cambian clientes, planes o prestaciones.
- La cancelación conserva el contrato y registra actor, fecha, motivo e historial; no existe eliminación en la API.

### Permisos de clientes

- `superadmin`: acceso global de lectura y gestión.
- `admin`: gestión completa dentro de su organización y todas sus sucursales.
- `manager`: lectura, creación, edición y gestión de beneficiarios/contactos dentro de su organización.
- `seller`: gestión operativa dentro de su sucursal, sin cambiar la sucursal del cliente.
- `collector` y `cashier`: lectura dentro de su sucursal.
- `accountant`: lectura limitada a su sucursal.
- `inventory`: sin acceso al módulo.

Los permisos, el aislamiento por organización y el alcance de sucursal se validan en backend. Cambiar IDs o campos ocultos en el frontend no amplía el acceso.

### Permisos de planes

- `superadmin`: acceso global, incluyendo costos y administración.
- `admin`: gestión completa dentro de su organización, estados y costos.
- `manager`: lectura, creación, edición, duplicación, catálogo y costos dentro de su organización.
- `seller`: solo planes activos disponibles en su sucursal; nunca recibe costos ni márgenes.
- `collector`, `cashier` e `inventory`: lectura de planes activos disponibles en su sucursal, sin costos.
- `accountant`: lectura organizacional incluyendo costos y márgenes, sin modificación.

La protección de costos ocurre al serializar la respuesta del backend. Los campos sensibles no se envían al navegador de usuarios sin permiso.

### Decisiones del módulo de planes

- `FuneralServiceItem` representa una prestación comercial, no inventario ni un servicio funerario ejecutado.
- `FuneralPlanItem` normaliza cantidad, notas y orden; no se almacenan prestaciones como texto libre.
- Los códigos `PLA-000001` se asignan mediante secuencia transaccional por organización, sin conteos.
- Un plan puede estar disponible en todas las sucursales o utilizar `PlanBranchAvailability`; las asociaciones cruzadas se rechazan.
- Costo, margen y porcentaje son estimaciones calculadas desde los servicios y nunca utilidad contable real.
- Un servicio inactivo permanece en planes existentes, pero no puede agregarse a configuraciones nuevas.
- Duplicar un plan copia prestaciones y disponibilidad dentro de `transaction.atomic`, con código e historial nuevos.
- Los planes y servicios no se eliminan desde la API; se activan o inactivan.
- Un contrato futuro deberá guardar un snapshot comercial del plan para que cambios de catálogo no alteren contratos históricos.

### Decisiones del módulo

- El código `CLI-000001` se asigna mediante una secuencia transaccional por organización; no utiliza conteos.
- La identidad normalizada es única entre clientes activos de la misma organización.
- Los clientes nunca se eliminan desde la API; únicamente se activan o inactivan.
- Un beneficiario titular referencia los datos del cliente y no los duplica.
- Solo puede existir un contacto principal activo por cliente, garantizado también por la base de datos.
- `CustomerActivity` conserva un historial administrativo básico sin almacenar cambios sensibles completos.

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
