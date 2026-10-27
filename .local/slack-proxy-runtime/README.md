# Autorización local del proxy Slack

Esta carpeta es privada del host y queda fuera de Git y del contexto Docker.

1. Cuando hayas creado tu app Slack y cuentes con la aprobación que exija tu workspace, sustituye el contenido vacío de `client-id` por su Client ID OAuth, en una sola línea. No es el App ID (`A...`). No uses el identificador de otra aplicación.
2. Si la app exige autenticación confidencial OAuth, introduce su Client Secret únicamente en `client-secret`, en una sola línea. No pegues tokens ni secretos en el chat. Slack publica `client_secret_post` como método de autenticación.
3. La app debe tener registrado el redirect que utiliza este proxy: `http://localhost:3118/callback`. No se cambian permisos ni políticas de Slack automáticamente.
4. La conexión inicial pide únicamente `channels:history` (lectura de canales públicos/hilos); no solicita publicación, búsqueda global ni seguimiento automático. Cualquier ampliación posterior requiere revisión.

OpenCode leerá estos archivos mediante referencias `{file:...}`; no se copiará su contenido en el JSON de configuración. Mientras no se complete la autorización, la conexión no se declara operativa. La carpeta debe mantener permisos 700 y los archivos 600.

Verificar conexión significa inicializar MCP y listar herramientas, no leer mensajes. El bridge Claude existente y la demo Efren Bot permanecen intactos.

## Estado observado — 2026-10-23

- El usuario aclaró que aún no tiene creada la app. `client-id` y `client-secret` siguen vacíos; no hubo autorización OAuth. No se ha acreditado aprobación de app/perfil.
- El OpenCode v2.1.3 integrado de OpenChamber tiene una entrada remota `slack`, URL `http://127.0.0.1:3120/mcp`, **disabled:true**. Settings MCP, tras Refresh, mostró `Disabled slack … Remote server`. Mantener deshabilitada mientras no se autorice; esto NO es una conexión Slack operativa.
- Referencias OAuth a estos archivos locales, no sus valores, están en la entrada global. Scope inicial `channels:history`: solo lectura de canales públicos/hilos; sin canales privados, búsqueda, publicación ni seguimiento automático. No ampliar permisos ni habilitar automáticamente el ajuste público/PKCE de Slack, que es de una sola dirección.
- El dueño debe registrar en Slack `http://localhost:3118/callback`. El callback interno del cliente es distinto: `http://127.0.0.1:19876/mcp/oauth/callback` (callback_port 19876). Discovery local: `http://127.0.0.1:3120/.well-known/oauth-authorization-server`.

## Proceso manual y operación segura

Última observación del padre: proceso propio PID 48834, iniciado a las `2026-10-23T22:22:54Z` mediante `/opt/homebrew/bin/node build/index.js`, cwd `/Users/efren.herrera/workspace/efren-bot/.local/slack-mcp-proxy`. Listeners comprobados exactamente `127.0.0.1:3120` (fachada) y `127.0.0.1:3118` (callback). Entorno allowlist sin HOME ni claves de proveedores; NODE_ENV production, timeout 10000 y destino callback interno indicado arriba. No se reenviaron credenciales. No hay autostart, LaunchAgent, instalación global ni servicio del sistema configurados.

Artefactos privados de ese arranque: `run-20261023T222254Z/process.json` y `proxy.log` (0600, directorio 0700). Un PID guardado es solo una pista histórica: antes de cualquier parada/reinicio hay que comprobar de nuevo propietario, ejecutable, cwd e identidad del proceso propio y sus listeners. Nunca matar por nombre, por puerto (`kill $(lsof …)`) ni por un PID sin revalidar; no tocar servicios ajenos. Este README no configura un launcher ni ejecuta operaciones de proceso.

Los dos endpoints discovery devolvieron 200. Una inicialización MCP **sin OAuth** recibió el 401 esperado del upstream Slack y WWW-Authenticate local: confirma únicamente transporte sin autenticar. No se probó conexión autenticada ni catálogo. No hubo tools/call ni lectura Slack. Logs reales inspeccionados solo sin auth; las regresiones con secretos fueron sintéticas. La primera aserción HTTP falló por exigir barra final al issuer origin; corregido solo el test, reintento PASS. Historial completo de fuente/checks y límites en `.odd/openchamber-slack-proxy.md` y `.local/slack-mcp-proxy/.provenance/validation.md`.

Siguiente paso: crear la app, aportar Client ID local y completar login humano en la UI oficial cuando corresponda. No pegar secretos/tokens, screenshots ni enlaces de hilos en el chat para esta verificación. No confundir este proxy independiente con el bridge Claude ni alterar la demo.
