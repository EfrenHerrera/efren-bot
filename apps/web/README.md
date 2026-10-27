# Efren Bot · web en blanco

Retiro solicitado el 2026-10-24: `App` no renderiza contenido ni realiza consultas,
polling, almacenamiento o navegación. Se eliminaron las simulaciones, la bandeja,
el panel manual, sus clientes/hooks/pruebas y el proxy; no están ocultos por CSS.
El backend y sus datos permanecen independientes y no se eliminan con este retiro.

Se conserva React/TypeScript/Vite, el entrypoint con StrictMode y los locks existentes.
Servidor de desarrollo: `127.0.0.1:5173`, puerto estricto, hosts locales y CORS
deshabilitado; preview conserva restricciones locales. No hay proxy ni configuración
horaria de producto. El contenedor existente publica solo loopback según el proyecto.

Comprobaciones obligatorias de fuente, desde la raíz:

```sh
npm --prefix apps/web ci
npm --prefix apps/web run typecheck
npm --prefix apps/web run test -- --run
npm --prefix apps/web run build
```

Las nuevas pruebas montan el App real y exigen DOM vacío y cero efectos de aplicación
tras StrictMode, rerender, espera, visibilidad, ciclo de página y remount. Las pruebas
de las features retiradas ya no forman la suite actual; los conteos anteriores son
[evidencia histórica](../../docs/synthetic-work.md#evidencia-de-comprobaciones).
Estos checks no acreditan despliegue, apariencia en navegador ni preservación DB/runtime;
esa aceptación corresponde a la integración web separada. No iniciar servicios ni
reutilizar puertos ocupados sin autorización. Ver [desarrollo local](../../docs/local-development.md).
