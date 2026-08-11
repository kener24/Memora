# Memora

Memora es una plataforma web para la gestión integral de empresas funerarias. Incluye autenticación segura, clientes y beneficiarios, catálogo de planes, venta contractual, cuotas versionadas y cobros reales con aplicación de abonos, recibos y PDF.

## Arquitectura

```text
Memora/
├── backend/                 Django + Django REST Framework
│   ├── accounts/            Usuario, roles y autenticación JWT
│   ├── organizations/       Organizaciones y sucursales
│   ├── customers/           Clientes, beneficiarios, contactos e historial
│   ├── plans/               Planes, prestaciones, disponibilidad e historial
│   ├── contracts/           Contratos, ventas, snapshots, auditoría y PDF
│   ├── installments/        Cuotas, calendarios, reprogramación y plan de pagos
│   ├── payments/            Pagos, aplicaciones, recibos, anulación y PDF
│   ├── collection_management/ Cartera, cobradores, rutas, jornadas y liquidaciones
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
| `GET` | `/api/installments/` | Según alcance | Busca, filtra, ordena y pagina las obligaciones del calendario activo. |
| `GET` | `/api/installments/options/` | Lectura | Entrega filtros y permisos del módulo de cuotas. |
| `GET` | `/api/installments/summary/` | Lectura | Resume vencimientos de hoy, vencidas y monto programado del mes. |
| `GET` | `/api/contracts/{id}/installment-schedule/` | Lectura | Obtiene calendario, cuotas paginadas y versiones históricas. |
| `POST` | `/api/contracts/{id}/installment-schedule/generate/` | Admin, manager | Genera de forma idempotente un calendario faltante o personalizado. |
| `POST` | `/api/contracts/{id}/installment-schedule/preview/` | Admin, manager | Calcula una vista previa sin persistir datos. |
| `POST` | `/api/contracts/{id}/installment-schedule/reprogram/` | Admin, manager | Reemplaza el calendario activo conservando la versión anterior. |
| `GET` | `/api/contracts/{id}/installment-schedule/pdf/` | Lectura | Descarga el plan histórico de pagos en PDF. |
| `GET/POST` | `/api/payments/` | Según rol | Busca, filtra y pagina pagos, o registra dinero con idempotencia. |
| `GET` | `/api/payments/{id}/` | Según alcance | Consulta el pago, sus aplicaciones y el recibo histórico. |
| `POST` | `/api/payments/{id}/void/` | Admin, manager | Anula con motivo y reconstruye determinísticamente las aplicaciones. |
| `GET` | `/api/payments/{id}/receipt/` | Lectura | Obtiene el snapshot del recibo emitido. |
| `GET` | `/api/payments/{id}/receipt/pdf/` | Lectura | Descarga el recibo imprimible, también si está anulado. |
| `GET` | `/api/payments/options/` | Lectura | Entrega métodos, tipos, estados, filtros y permisos. |
| `GET` | `/api/contracts/{id}/payments/` | Lectura | Obtiene resumen financiero e historial del contrato. |
| `POST` | `/api/contracts/{id}/payments/preview/` | Roles de cobro | Calcula la aplicación del abono sin guardar cambios. |
| `POST` | `/api/contracts/{id}/settle/` | Admin, manager | Liquida exactamente el saldo vigente con control de concurrencia. |

Las operaciones de creación, confirmación y cobro requieren el encabezado `Idempotency-Key`. Repetir una solicitud idéntica recupera el mismo resultado; reutilizar la clave con otra carga produce conflicto.

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
- La prima, cuota y primer vencimiento son condiciones comerciales; al confirmar un financiamiento automático generan obligaciones, nunca dinero recibido.
- El PDF utiliza exclusivamente el snapshot contractual, incluso si luego cambian clientes, planes o prestaciones.
- La cancelación conserva el contrato y registra actor, fecha, motivo e historial; no existe eliminación en la API.

### Decisiones del motor de cuotas

- `InstallmentSchedule` es una cabecera versionada. Solo existe una versión activa por contrato; las reemplazadas y canceladas nunca se eliminan.
- `Installment` es una obligación contractual, no un pago, recibo, movimiento de caja ni comprobante fiscal.
- El pendiente se deriva de monto vigente menos monto pagado y el estado vencido se calcula con la fecha local efectiva, evitando datos obsoletos.
- Todos los importes se calculan con `Decimal`; la última cuota se ajusta para que la suma coincida exactamente con el monto financiado.
- La frecuencia mensual conserva el día ancla original y usa el último día válido del mes cuando corresponde: 31 de enero, 28/29 de febrero, 31 de marzo.
- Semanal usa intervalos de 7 días y cada 15 días usa intervalos exactos de 15 días.
- Los calendarios personalizados exigen fechas e importes manuales cuya suma sea exactamente el monto financiado.
- Confirmar un contrato financiado automático genera el calendario en la misma transacción. Los contratos al contado no generan cuotas y los personalizados esperan carga manual.
- Reprogramar exige motivo, cancela las obligaciones anteriores y crea una nueva versión. En este sprint se bloquea si existiera algún pago aplicado.
- Cancelar un contrato cancela su calendario activo y todas sus obligaciones sin borrar la trazabilidad.
- Los contratos activos creados antes del Sprint 4 pueden generar su calendario mediante el endpoint seguro e idempotente.

### Permisos de cuotas

- `superadmin` tiene alcance global; `admin` y `manager` gestionan calendarios dentro de su organización.
- `seller`, `collector`, `cashier` y `accountant` poseen lectura según las reglas de sucursal/organización existentes.
- `inventory` no tiene acceso al módulo. El backend aplica aislamiento por organización, sucursal y contrato en cada endpoint y PDF.

### Decisiones del módulo de pagos

- `Payment` representa dinero realmente recibido; `PaymentApplication` explica cuánto se aplicó a cada cuota y `Receipt` congela el comprobante histórico.
- Los números `PAG-000001` y `REC-000001` usan secuencias transaccionales independientes por organización.
- Prima, monto financiado, cuotas y saldo directo se mantienen separados. El total pagado solo suma pagos confirmados y el saldo contractual nunca puede ser negativo.
- Los abonos se distribuyen de la obligación más antigua a la más reciente, incluyendo cuotas futuras. La liquidación exige exactamente el saldo vigente.
- Registro, aplicaciones, estados de cuota, recibo, actividad e idempotencia se guardan en una transacción con bloqueo del contrato.
- Los pagos confirmados son inmutables y no se eliminan. La anulación conserva pago y recibo, marca ambos como anulados y reconstruye todos los abonos por fecha de pago, creación e ID.
- El recibo conserva organización, cliente, contrato, concepto, método, receptor, saldos y aplicaciones tal como existían al emitirse.
- Registrar dinero bloquea la cancelación simple del contrato y la reprogramación del calendario; cualquier ajuste posterior requiere un proceso financiero controlado.

### Permisos de pagos

- `superadmin` tiene alcance global y todas las operaciones.
- `admin` y `manager` consultan, cobran, registran prima, liquidan, retrofechan y anulan dentro de su organización.
- `cashier` cobra, registra prima y consulta recibos dentro de su sucursal, sin anular ni retrofechar.
- `collector` cobra cuotas y adelantos dentro de su sucursal, sin prima, liquidación, anulación ni retrofecha.
- `seller` solo consulta pagos dentro de su sucursal. `accountant` consulta a nivel organizacional. `inventory` no tiene acceso.
- Todos los endpoints, recibos y PDFs aplican alcance de organización, sucursal y contrato en backend.

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

### Sprint 6: cartera, morosidad y cobranza

La cartera no almacena un saldo paralelo. `PortfolioService` deriva cada indicador desde contratos activos, cuotas del calendario activo y pagos confirmados:

- cartera pendiente = precio contractual − pagos confirmados;
- cartera vencida = suma del pendiente de cuotas con vencimiento anterior a hoy;
- cartera por vencer = cartera pendiente − cartera vencida (incluye prima pendiente sin fecha de vencimiento propia);
- días de mora = días desde la cuota pendiente vencida más antigua;
- estado crítico = más de 90 días de mora; próximo a vencer = cuota entre hoy y los próximos 7 días;
- aging = 1–30, 31–60, 61–90, 91–120 y más de 120 días, calculado cuota por cuota.

`CollectionAction` registra contactos inmutables y anulables con motivo. `PaymentPromise` conserva una sola promesa pendiente por contrato; su estado efectivo pasa a incumplido al vencer la fecha aunque no exista un cron, y la resolución controlada deja auditoría. Cumplir una promesa exige un pago confirmado posterior, del mismo contrato, por monto suficiente y dentro de la ventana permitida.

| Método | Endpoint | Uso |
| --- | --- | --- |
| `GET` | `/api/collections/portfolio/` | Cartera paginada, búsqueda, filtros, ordenamiento y totales filtrados. |
| `GET` | `/api/collections/portfolio/summary/` | Indicadores globales y cobro confirmado del mes. |
| `GET` | `/api/collections/portfolio/aging/` | Antigüedad de las cuotas vencidas. |
| `GET` | `/api/collections/portfolio/contracts/{id}/` | Detalle financiero, gestiones y promesas del contrato. |
| `GET` | `/api/collections/portfolio/customers/{id}/` | Cartera y cobranza consolidada del cliente. |
| `GET/POST` | `/api/collections/collection-actions/` | Historial o registro de gestiones. |
| `POST` | `/api/collections/collection-actions/{id}/void/` | Anulación auditada, sin eliminar historial. |
| `GET/POST` | `/api/collections/payment-promises/` | Consulta o registro de promesas. |
| `POST` | `/api/collections/payment-promises/{id}/fulfill/` | Cumplimiento contra un pago confirmado real. |
| `POST` | `/api/collections/payment-promises/{id}/break/` | Confirmación auditada de incumplimiento efectivo. |
| `POST` | `/api/collections/payment-promises/{id}/cancel/` | Cancelación controlada con motivo. |
| `GET` | `/api/collections/collection-follow-ups/` | Agenda atrasada, de hoy y de próximos 7 días. |
| `GET` | `/api/collections/portfolio/export.xlsx` | Excel real con filtros, totales, formatos y panel congelado. |
| `GET` | `/api/collections/portfolio/export.pdf` | PDF horizontal filtrado con encabezados repetidos. |

Administradores y gerentes gestionan y resuelven cobranza en toda su organización; cobradores registran gestiones y promesas en su sucursal; cajeros, vendedores y contadores consultan según su alcance; contadores también exportan. Inventario no tiene acceso. El backend aplica alcance de organización, sucursal y contrato en cada consulta, detalle, mutación y exportación.

La interfaz `/cartera` ofrece indicadores, aging, filtros, tabla responsive con enlaces telefónicos, detalle, agenda y formulario de gestión. El inicio reutiliza el resumen real. El registro de dinero permanece exclusivamente en el flujo seguro del Sprint 5.

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

### Sprint 7: cobradores, rutas y liquidación diaria

Sprint 7 amplía el motor de cartera existente sin crear saldos ni pagos paralelos. Una asignación activa vincula cada contrato con un único cobrador; las reasignaciones cierran el registro anterior y conservan la cadena histórica. Las zonas agrupan clientes por sucursal y las rutas ordenan paradas reutilizando clientes y gestiones de cobranza reales.

El espacio responsive `/mi-jornada` permite al cobrador iniciar una jornada única, consultar su cartera y ruta del día, registrar visitas y entrar al flujo seguro de pagos. Un pago creado por un cobrador exige jornada abierta y asignación activa, y queda enlazado a esa jornada. Administradores y cajeros conservan su flujo normal del Sprint 5.

Al cerrar la jornada, Memora congela un resumen calculado exclusivamente con pagos confirmados asociados: `total cobrado = efectivo + transferencias + tarjetas + cheques + otros`, `efectivo esperado = pagos en efectivo` y `diferencia = efectivo reportado − efectivo esperado`. Una diferencia exige observación; revisión, aceptación y rechazo conservan actor, fecha y auditoría. La anulación posterior de un pago no reescribe el snapshot liquidado y deja un evento explícito.

| Recurso | Operaciones principales |
| --- | --- |
| `/api/collectors/` | Perfiles, disponibilidad, cartera individual y métricas de productividad. |
| `/api/collection-assignments/` | Asignación individual, masiva atómica, consulta histórica y reasignación. |
| `/api/collection-zones/` | Zonas por sucursal y asociación de clientes. |
| `/api/collection-routes/` | Rutas, paradas, ordenamiento e inactivación. |
| `/api/collector/portfolio/`, `/today/`, `/metrics/`, `/routes/` | Espacio operativo limitado al cobrador autenticado. |
| `/api/collector-work-sessions/` | Inicio, jornada vigente, cierre y resumen diario. |
| `/api/collector-settlements/` | Vista previa, envío idempotente, revisión, aceptación o rechazo. |
| `/api/collectors/productivity/export.xlsx` | Productividad de cobradores en Excel real. |
| `/api/collectors/{id}/portfolio/export.xlsx` | Cartera individual en Excel real. |
| `/api/collector-settlements/export.xlsx` | Historial de liquidaciones en Excel real. |
| `/api/collector-settlements/{id}/pdf/` | Comprobante de liquidación con snapshot y firmas. |

Administradores y gerentes gestionan cobradores, asignaciones, zonas, rutas y decisiones de liquidación dentro de su organización. Contabilidad consulta métricas, liquidaciones y exportaciones. Caja consulta liquidaciones. Cada cobrador solo opera su propia cartera, ruta, jornada y liquidación; el backend vuelve a validar organización, sucursal, propietario y permiso en cada acción.

La consola administrativa responsive está en `/operacion-cobranza`. Los orígenes locales `http://localhost:5173` y `http://127.0.0.1:5173` están habilitados por defecto para desarrollo; en otros entornos se deben declarar explícitamente mediante `CORS_ALLOWED_ORIGINS`.

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
