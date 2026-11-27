# Dashboard meteorológico de comparación entre dos ciudades

Aplicación local para comparar el clima actual y el histórico de dos ciudades en un único origen.
Django concentra el acceso al proveedor y el almacenamiento, Redis aporta la caché documentada y la
capa de actualizaciones en vivo, y una SPA de React se sirve desde `/`. Todo el stack arranca con un
comando y sobrevive a reinicios.

## Arquitectura

```text
Navegador (SPA React)
   │  REST + WebSocket (mismo origen)
   ▼
Django / DRF / Channels ──► Redis (caché, group layer, broker de Celery)
   │
   ├──► PostgreSQL (WeatherData append-only + chat)
   └──► OpenWeather
```

### Superficie HTTP y WebSocket

| Ruta | Uso |
|---|---|
| `GET /` | SPA servida por Django |
| `GET /health/` | Estado de base de datos, caché, proveedor, scheduler y LLM |
| `GET /dashboard-data/` | Comparación completa; sin `cities` usa el par almacenado más reciente |
| `GET /weather/` | Historial paginado y filtrable |
| `POST /weather/refresh/` | Lectura del proveedor para un par de ciudades |
| `GET /weather/export/` | CSV de la ventana filtrada |
| `GET /cities/search/` | Búsqueda en caché, almacenamiento y proveedor, en ese orden |
| `GET /chat/messages/` | Historial de una sesión de chat |
| `POST /chat/messages/` | Turno del asistente con bucle de herramientas |
| `WS /ws/weather/?cities=<a>,<b>` | Snapshot, observaciones, heartbeat y errores |

### Flujo de datos

1. La SPA pide el dashboard; Django intenta la caché y, si falla, lee PostgreSQL.
2. Si hace falta una lectura viva, el backend resuelve la ciudad con OpenWeather Geocoding y consulta
   Current Weather con `units=metric`.
3. Cada lectura se persiste como fila inmutable en `WeatherData`, deduplicada por
   `(city_key, timestamp)`.
4. Tras el commit se invalidan las claves de esa ciudad y se publica la observación en el grupo de
   Channels correspondiente.
5. El worker y beat de Celery refrescan cada 60 s hasta 10 ciudades con observaciones en las últimas
   24 h, aunque no haya ningún navegador abierto.
6. La vista raíz, sin parámetros, devuelve el par de ciudades con las observaciones más recientes
   almacenadas; nunca inventa un par ni llama al proveedor para rellenar la primera pantalla.

### Contrato de caché

Redis es parte obligatoria del stack, pero su caída no tumba las lecturas HTTP: todo error se registra
como `cache_error` y se trata como un *miss*. Cada clave tiene TTL explícito.

| Clave | Contenido | TTL |
|---|---|---|
| `weather:current:v1:{city_key}` | Última observación de una ciudad | 60 s |
| `weather:dashboard:v1:{city_a}:{city_b}:{window}` | Payload ensamblado + versiones por ciudad | 30 s |
| `weather:series:v1:{city_key}:{window}:{version}` | Serie temporal agregada | 60 s |
| `weather:seriesver:v1:{city_key}` | Contador de versión por ciudad | sin TTL |
| `geo:search:v1:{query_hash}` | Candidatos de geocodificación | 24 h |
| `geo:invalid:v1:{query_hash}` | Resultado negativo de geocodificación | 10 min |

El dashboard se envuelve con las versiones de serie vigentes. Un desajuste provoca un *miss*, de modo
que una inserción invalida todas las cachés que contienen esa ciudad sin recorrer el keyspace.

### Tiempo real

- El consumidor acepta exactamente dos ciudades distintas y conocidas y se suscribe a
  `weather.<sha256(city_key)[:32]>` por ciudad; el hash mantiene válidos nombres con espacios o
  apóstrofes.
- Envía `snapshot` al conectar, `observation` tras cada inserción confirmada, `heartbeat` cada 25 s y
  `error` con cierre `4001` ante una suscripción inválida.
- El cliente solo puede enviar `ping`; deduplica por `(city_key, timestamp)` e ignora frames más
  antiguos que la lectura mostrada.
- La reconexión usa backoff exponencial de 1–30 s con 20 % de jitter, se reinicia tras 10 s estable y
  considera muerta una conexión sin frames durante 60 s.

### Frescura y veracidad

- `age_seconds = now - observed_at`, acotado a cero.
- `freshness = current` si la edad es ≤ 60 s; `stale` en caso contrario; `unavailable` si no hay fila.
- Un fallo del proveedor fuerza `stale` incluso con una fila reciente y añade un `reason`
  (`credential_invalid`, `rate_limited`, `provider_unavailable`).
- Los valores derivados (deltas, buckets) no se almacenan. Los buckets vacíos se omiten, no se
  rellenan con ceros.

## Decisiones y trade-offs

| Decisión | Por qué | Trade-off / alternativa descartada |
|---|---|---|
| Django sirve la SPA en `/` desde un build único en un volumen | Un solo origen para REST, WebSocket y SPA; sin CORS y con un único comando | El servicio `frontend` es un builder efímero; Vite en modo dev delante de Django habría añadido un segundo runtime |
| Caché *cache-aside* en Redis con version-key por ciudad | TTL explícito, invalidación O(1) y ningún `KEYS`/`SCAN` por inserción | Solo TTL dejaría gráficas obsoletas hasta 60 s; escanear claves es O(keyspace) |
| PostgreSQL append-only para `WeatherData` | Histórico auditable y consultable; cada número mostrado es trazable | La tabla crece sin límite (≈1 M filas/año por ciudad a 2 lecturas/min; ≈2,1 M con dos ciudades) y no hay poda |
| Worker y beat de Celery separados | El histórico crece y los dashboards se actualizan sin un navegador abierto | Dos servicios extra y una imagen reutilizada con comandos distintos |
| LiteLLM en el backend, nunca en el navegador | La clave no se filtra, el proveedor se cambia solo con `LLM_MODEL` y hay un único camino a datos | La latencia del turno depende del proveedor externo y no hay streaming |
| Persistencia del chat en PostgreSQL | El historial y el log de herramientas sobreviven a recargas y reinicios, y se pueden auditar | Tres tablas nuevas y una sesión UUID sin autenticación real |
| Sin autenticación | El alcance es local y de un solo operador; añadir cuentas no aportaba valor | No debe exponerse a Internet; el `session_id` del chat no es un token de seguridad |
| Modo degradado en lugar de fallar al arrancar | El stack siempre arranca y la UI distingue datos frescos, stale y ausentes | Exige disciplina para etiquetar la frescura y no rellenar huecos |
| Exportación CSV en streaming | Memoria plana con 10 000+ filas y quoting RFC 4180 | No genera Excel; el CSV necesita neutralizar fórmulas |

## Cómo levantar

Requisitos: Docker con Compose v2.20+. No hace falta Node, Python, `.env`, migraciones manuales, seed
ni build previo.

```bash
docker compose up
```

Abre <http://localhost:8000/>. La primera ejecución construye imágenes y tarda unos minutos; las
siguientes son rápidas. Si cambias dependencias, el Dockerfile del backend o el frontend, usa
`docker compose up --build`.

`OPENWEATHER_API_KEY` es opcional. Sin ella el stack arranca en **modo degradado**: `/health/` informa
`provider_configured: false`, los refrescos caen a filas almacenadas marcadas como stale y el
dashboard nunca fabrica valores.

```bash
cp .env.example .env   # opcional: overrides locales; reemplaza los placeholders YOUR_*
docker compose up
```

Verificación rápida:

```bash
./scripts/verify-startup.sh
curl -s http://localhost:8000/health/ | jq
```

La vista `/` muestra las dos ciudades con observaciones almacenadas más recientes y el histórico
paginado en la tabla. Si todavía no hay filas, la UI presenta un estado vacío explícito: no inventa un
par ni rellena valores. `docker compose down` conserva los datos en `pg_data`, `redis_data` y
`spa_dist`; solo `docker compose down -v` es destructivo.

### Tests y calidad

```bash
# Backend (sin acceso a red)
docker compose exec backend pytest -q
docker compose exec backend ruff check .
docker compose exec backend mypy weather config

# Frontend
docker compose run --rm frontend npm test -- --run
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run lint
```

El frontend también puede correr contra el backend de Compose con `npm install && npm run dev` en
`frontend/`; Vite hace proxy de `/weather`, `/dashboard-data`, `/cities`, `/chat`, `/health` y `/ws`
al puerto 8000.

## Variables de entorno

Todas tienen un valor seguro en `docker-compose.yml`; `.env` es opcional.

| Variable | Default | Propósito |
|---|---|---|
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `weather` | Base de datos local, creada automáticamente |
| `REDIS_URL` | `redis://redis:6379/0` | Caché, capa de Channels y broker de Celery |
| `OPENWEATHER_API_KEY` | vacío | Vacío activa el modo degradado documentado |
| `OPENWEATHER_BASE_URL` | `https://api.openweathermap.org` | Override para un proveedor compatible o proxy |
| `DJANGO_SECRET_KEY` | valor de desarrollo | Cambiar fuera de uso local |
| `DJANGO_DEBUG` | `false` | Las páginas de debug nunca están activas por defecto |
| `BACKEND_PORT` | `8000` | Puerto publicado en el host |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,backend` | Hosts aceptados por Django y Channels |
| `LLM_MODEL` | `gpt-4o-mini` | Cualquier identificador de LiteLLM; cambiarlo cambia proveedor y modelo |
| `LLM_API_KEY` | vacío | Clave del proveedor. Vacía es un modo degradado válido; si el contenedor recibe la variable propia del proveedor (`OPENAI_API_KEY`, etc.), LiteLLM la usa. En Compose la vía soportada es `LLM_API_KEY` |
| `LLM_API_BASE` | vacío | Gateway opcional compatible con OpenAI |
| `LLM_TIMEOUT_SECONDS` | `30` | Timeout por llamada al modelo |
| `LLM_MAX_TOOL_ROUNDS` | `4` | Cota de rondas de herramientas por turno |
| `THROTTLE_REFRESH` | `30/min` | Refrescos aceptados por cliente |
| `THROTTLE_EXPORT` | `20/min` | Exportaciones aceptadas por cliente |
| `THROTTLE_CHAT` | `12/min` | Turnos de chat aceptados por cliente |

`LLM_MODEL` acepta, por ejemplo, `gpt-4o-mini`, `anthropic/claude-3-5-sonnet` o
`openrouter/meta-llama/llama-3.1-70b-instruct`. Cambiar de proveedor no requiere tocar código.

## Diseño del agente y las herramientas

El navegador nunca habla con el proveedor del modelo: envía la pregunta a `POST /chat/messages/` y
Django ejecuta un bucle acotado de LiteLLM con herramientas *backend-owned*.

```text
React ChatPanel ──► POST /chat/messages/ ──► Django
                                                ├──► LiteLLM (LLM_MODEL)
                                                │      └──► esquemas de herramientas
                                                ├──► herramientas tipadas ──► PostgreSQL (solo lectura)
                                                └──► ChatSession / ChatMessage / ToolRun
```

### Bucle del agente

- Máximo `LLM_MAX_TOOL_ROUNDS` rondas (4 por defecto); si se agota, el turno falla con
  `tool_round_limit`.
- `temperature=0`, timeout por llamada de `LLM_TIMEOUT_SECONDS` (30 s) y sin streaming.
- Contexto: mensaje del sistema + las 20 entradas más recientes de la sesión; la respuesta del
  asistente se recorta a 8 000 caracteres antes de persistirse.
- El prompt de sistema está en inglés (artefacto de repositorio) pero exige responder en español,
  citar ciudad, rango efectivo y `sample_count`, y no inventar, interpolar ni calcular.
- Si no hay modelo o credencial, responde `llm_not_configured`. Si el proveedor falla o tarda,
  `llm_unavailable`. Nunca se guarda ni se muestra el cuerpo del error del proveedor.

### Herramientas

| Herramienta | Argumentos | Salida |
|---|---|---|
| `consultar_clima` | `city` obligatorio; `start`/`end` ISO 8601; `limit` 1–100 (default 20) | Filas más recientes en `[start, end)`, `total_matched`, `no_data` y `evidence` |
| `calcular_estadistica` | `city`, `metric` (`temperature`, `humidity`, `wind_speed`), `statistic` (`average`, `minimum`, `maximum`); `start`/`end` opcionales | Agregado `Avg`/`Min`/`Max` calculado por la BD, `value`, `sample_count` y `evidence` |

Reglas de ejecución:

1. Los argumentos se validan antes de cualquier consulta; las claves desconocidas se rechazan.
2. `city` se normaliza con el validador de frontera existente.
3. Sin fechas se usa la ventana de los últimos 30 días y el rango efectivo se informa en `evidence`.
4. Solo se lee `WeatherData` mediante el ORM; no hay SQL, shell ni URLs controladas por el modelo.
5. `consultar_clima` devuelve como máximo 100 filas; nunca la tabla completa.
6. Las respuestas de datos incluyen `evidence` con ciudad, `city_key`, filtros y `sample_count`;
   `source` es siempre `weather_data`. Los errores de validación devuelven un código y, cuando ya se
   resolvieron ciudad y rango, la evidencia aplicada.
7. Si no hay filas, devuelve `ok: true` con `no_data: true` y `sample_count: 0`; el agente debe decir
   honestamente que no hay datos.

### Persistencia y privacidad

- `ChatSession`, `ChatMessage` y `ToolRun` viven en PostgreSQL. La sesión es un UUID generado por el
  navegador y guardado en `localStorage` (`weather-chat-session`).
- Al recargar se restauran los últimos 100 mensajes y su log de herramientas; no se pierde nada al
  limpiar la pestaña mientras el UUID siga en el navegador.
- Argumentos y salidas de herramientas pasan por redacción recursiva de claves tipo
  `api_key|token|secret|password|authorization` y de valores con forma de credencial antes de
  persistirse.
- El historial de chat no usa la caché meteorológica ni añade claves nuevas a su contrato.

### Fallos del asistente

| Situación | Resultado |
|---|---|
| Sin `LLM_MODEL` o sin credencial | `llm_not_configured`; el panel muestra un estado seguro en español y el resto del dashboard sigue operativo |
| Proveedor lento, con error o sin cuota | `llm_unavailable`; no se almacena ni se muestra el cuerpo del error |
| Se agota el límite de rondas | `tool_round_limit`; el mensaje queda como fallido y visible |
| Respuesta vacía del modelo | `llm_empty_response` |
| Herramienta con argumentos inválidos o sin datos | Error tipado o `no_data`; el agente debe pedir aclaración, no inventar |

### Uso

1. Abre <http://localhost:8000/>.
2. Pulsa el botón flotante de chat (abajo a la derecha).
3. Pregunta, por ejemplo: `¿Cuál fue la temperatura promedio en Santiago en los últimos 7 días?`.
4. Cada respuesta muestra las herramientas usadas, los filtros y el número de observaciones.
5. Recarga la página: el historial y el log de herramientas se restauran desde PostgreSQL.

## Comportamiento ante fallos

| Situación | Resultado |
|---|---|
| Falta la clave del proveedor o es rechazada | El arranque continúa; las lecturas vienen del almacenamiento y se marcan stale |
| Proveedor no disponible durante la búsqueda | Las ciudades almacenadas siguen apareciendo; el proveedor es solo el tercer paso |
| Proveedor lento, 5xx o rate limit | Dos reintentos y luego la última fila almacenada como stale |
| Redis caído | Las peticiones HTTP siguen funcionando desde PostgreSQL; la caché y el tiempo real se degradan y se registra `cache_error` |
| Sin filas y proveedor no disponible | `503` con `no_data_available`; la UI muestra un estado vacío explícito |
| WebSocket caído | El cliente reconecta con backoff y jitter; el snapshot elimina huecos |
| Clave LLM ausente o inválida | El stack sigue sano; el chat muestra un fallo seguro y el clima no se ve afectado |
| Proveedor LLM lento o fallando | El turno se clasifica como `llm_unavailable`; no se guardan secretos ni respuestas crudas |

## Limitaciones

### Alcance y seguridad

- **No hay autenticación.** El alcance es local y de un solo operador; no debe exponerse a Internet.
  El UUID de sesión del chat no es un token de seguridad: quien lo conozca puede leer ese historial.
- El *throttling* es por IP y protege sobre todo contra abuso accidental, no contra un atacante
  decidido.
- No hay cuentas, roles, auditoría de usuarios ni aislamiento multi-tenant.

### Datos y cobertura

- Solo se ingieren **condiciones actuales**, no pronósticos ni alertas. No hay backfill histórico: la
  historia empieza cuando el stack empieza a observar.
- El scheduler refresca como máximo 10 ciudades con actividad en las últimas 24 h. Una ciudad sin
  observaciones en 24 h sale de la lista y deja de acumular historia.
- `WeatherData` no guarda latitud/longitud; cada refresco vuelve a geocodificar. Es una concesión de
  simplicidad, no un fallo de datos.
- La tabla es append-only y **no tiene política de retención ni poda**. A ~2 lecturas/min son ≈1 M
  filas/año por ciudad (≈2,1 M con dos ciudades); el crecimiento es aceptable en local, no
  indefinido en producción.
- Los huecos no se interpolan ni se rellenan con ceros; si no hay observación, no hay punto.
- El proveedor es la única fuente de verdad meteorológica. Sin clave, la aplicación es honesta pero
  limitada a lo ya almacenado.

### Asistente

- El chat depende de un proveedor externo: la latencia del turno está dominada por el modelo y el
  objetivo de <10 s no está garantizado con cualquier proveedor.
- No hay streaming; el turno es síncrono y la UI muestra un estado local de “en curso”.
- Las herramientas solo leen `WeatherData` almacenado. El asistente no consulta OpenWeather ni puede
  responder sobre ciudades o fechas sin datos.
- El prompt y la evidencia reducen las alucinaciones, pero no las eliminan por completo; la
  verificación última es la evidencia devuelta por la base de datos.
- El historial se limita a 100 mensajes por sesión y el contexto del modelo a 20 entradas.

### Operación y escala

- Diseñado para un operador, ~10 sesiones concurrentes y 2 ciudades por vista. No hay pruebas de carga
  horizontal ni *sharding*.
- Redis es necesario para caché, Channels y Celery. Si cae, las lecturas HTTP sobreviven desde
  PostgreSQL, pero el tiempo real y las tareas en segundo plano quedan degradados.
- La paginación offset es adecuada para este volumen, pero pierde eficiencia con historiales muy
  grandes.
- La SPA se sirve como build estático desde Django; no hay SSR ni CDN.
- No hay CI/CD ni despliegue productivo incluido; el objetivo es un stack local reproducible.

## Metodología y herramientas

El proyecto se desarrolló con **Spec-Driven Development** usando **Spec Kit** (`speckit`) como flujo
de especificación, con **OpenCode** como harness y **DeepSeek V4.1 Flash** como LLM.

## Tiempo real invertido

Medición tomada de los registros locales de sesiones de OpenCode para este repositorio. El “trabajo
activo” suma los intervalos entre mensajes y recorta cualquier pausa mayor de 10 minutos; por tanto,
excluye tiempo de lectura, revisión o pensamiento fuera de sesión.

| Métrica | Valor |
|---|---|
| Periodo | 25 nov 2026 16:46 → 27 nov 2026 00:31 (hora local) |
| Sesiones registradas | 11 |
| Trabajo activo estimado (sesiones) | 4 h 04 min |
| Revisión y pruebas (3 h × 2 días) | 6 h 00 min |
| **Tiempo total estimado** | **10 h 04 min** |
| Tiempo dentro de sesión | 6 h 56 min |
| Ventana de calendario | 31 h 45 min (dos tardes/noches) |

La diferencia entre trabajo activo y calendario corresponde a pausas entre sesiones y a esperas
largas dentro de una misma sesión. Al trabajo activo se suman 3 h de revisión y pruebas por cada uno
de los dos días invertidos (6 h), para un total estimado de 10 h 04 min. La cifra es una estimación
reproducible a partir de los logs, no un cronómetro manual.

## Estructura del repositorio

```text
backend/      Proyecto Django (config/) y app weather/ (API, datos, chat, tests)
frontend/     SPA Vite + React + Ant Design
scripts/      verify-startup.sh
specs/        Especificación, plan, research, contratos, tareas y quickstarts
docs/         Arquitectura, rendimiento y cumplimiento de la constitución
```

## Documentación

- [docs/architecture.md](docs/architecture.md) — flujo de datos, contrato de caché, taxonomía de
  errores.
- [docs/performance.md](docs/performance.md) — objetivos y mediciones.
- [docs/constitution-compliance.md](docs/constitution-compliance.md) — revisión principio a
  principio.
- [specs/001-weather-comparison-dashboard/quickstart.md](specs/001-weather-comparison-dashboard/quickstart.md)
  — escenarios de validación del dashboard.
- [specs/001-weather-comparison-dashboard/contracts/openapi.yaml](specs/001-weather-comparison-dashboard/contracts/openapi.yaml)
  — contrato REST.
- [specs/001-weather-comparison-dashboard/contracts/websocket.md](specs/001-weather-comparison-dashboard/contracts/websocket.md)
  — protocolo en vivo.
- [specs/002-weather-data-chat/quickstart.md](specs/002-weather-data-chat/quickstart.md) — puesta en
  marcha y validación del asistente.
- [specs/002-weather-data-chat/contracts/chat-tools.md](specs/002-weather-data-chat/contracts/chat-tools.md)
  — contrato tipado de herramientas.
