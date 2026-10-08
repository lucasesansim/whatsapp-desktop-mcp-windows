# WhatsApp Desktop MCP — Windows, experimental fork

Fork de [Cristinacarolsouza/whatsapp-desktop-mcp-windows](https://github.com/Cristinacarolsouza/whatsapp-desktop-mcp-windows), mantenido en [lucasesansim/whatsapp-desktop-mcp-windows](https://github.com/lucasesansim/whatsapp-desktop-mcp-windows) como base de investigación para ChatIÁ. Conserva la licencia MIT y la autoría original.

Permite consultar la caché local de WhatsApp Desktop para Windows mediante WebView2/CDP y ofrece herramientas MCP para clientes compatibles. La app oficial realiza la conexión con WhatsApp. Este proyecto usa estructuras y funciones internas no documentadas: **no es una API oficial de Meta**.

## Estado real

Experimental. Las correcciones de envío se verificaron con datos sintéticos; no se enviaron mensajes reales. Se completó una prueba de lectura limitada con WhatsApp Desktop 2.2639.100.0 x64. Esta comprobación no garantiza compatibilidad con otras versiones ni rendimiento estable.

Usar la app oficial no garantiza que la automatización esté autorizada por WhatsApp ni que la cuenta no pueda sufrir restricciones. Tampoco garantiza acceso al historial completo: los resultados dependen de lo que la app tenga sincronizado.

## Correcciones de este fork

- Destinatario comprobado por identificador completo, sin aceptar nombres o coincidencias parciales. Se vuelve a comprobar junto con el clic de envío.
- Los mensajes de texto no se añaden a un borrador existente. Si cambia el destinatario o el texto, se bloquea el envío; se eliminó el recurso alternativo de pulsar Enter a ciegas.
- La verificación exige un registro nuevo del mismo destinatario, con texto exacto y fecha compatible. Excluye IDs presentes antes del intento y resultados ambiguos. Para archivos exige además nombre, tamaño y leyenda exactos cuando son observables.
- Un registro local coincidente **no es una confirmación de entrega o lectura**. Si no puede verificarse, se devuelve `sent_unverified`; no se reintenta automáticamente.
- Los adjuntos requieren exactamente un archivo seleccionado con nombre y tamaño coincidentes antes del clic; si la app no permite comprobarlo, se bloquea el envío.
- Confirmación interactiva obligatoria para texto y archivos. La variable anterior `WHATSAPP_DESKTOP_MCP_SKIP_CONFIRM` ya no permite omitirla. Un cliente sin soporte de confirmación no puede enviar.
- Exclusión de envíos simultáneos entre procesos MCP que comparten el directorio de estado. Los intentos se cuentan antes de actuar, incluidos los de resultado incierto.
- Modo de solo lectura por defecto, destinos CDP restringidos al origen exacto de WhatsApp y a `127.0.0.1` en el puerto configurado, valores JavaScript codificados como JSON.
- Pruebas reales desactivadas salvo que se elija expresamente `RUN_LIVE=1`.

## Desarrollo y pruebas

Requiere Windows, Python 3.12+ y, para las pruebas de los programas JavaScript, Node.js. Puede usarse `uv sync --extra dev` con el archivo de dependencias existente, o un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check src tests
.\.venv\Scripts\python -m mypy src --ignore-missing-imports
```

Las pruebas sintéticas aíslan los registros y bloquean conexiones a WhatsApp. Las de JavaScript requieren `node` en PATH o `TEST_NODE` apuntando al ejecutable.


## Prueba de lectura en Windows x64

Requiere Windows x64, PowerShell 7, el compilador .NET Framework de Windows y las dependencias Python instaladas. Con WhatsApp abierto, ejecutar:

    .\scripts\Test-ReadOnly.ps1

El script pide escribir PROBAR, reinicia WhatsApp, obtiene una muestra de hasta 5 chats y 5 mensajes y muestra solo cantidades y tiempos. No imprime ni guarda cuerpos, nombres o números. Los resultados locales y el ayudante compilado quedan en work/read-only-test/, excluido de Git.

Usa IPackageDebugSettings y la activación de apps de Microsoft Store para aplicar opciones temporales únicamente a WhatsApp. No escribe en la rama de políticas, modifica permisos ni solicita administrador. Al terminar retira las opciones, reinicia WhatsApp normalmente y comprueba que el puerto esté cerrado. No cerrar la consola durante la prueba.

El ayudante C# solo reanuda el hilo inicial que Windows suspende para ese inicio diagnóstico, tras comprobar que pertenece al ejecutable instalado de WhatsApp. No inyecta código. Este mecanismo sigue el [procedimiento de Microsoft para pasar un entorno a una app de Store](https://learn.microsoft.com/en-us/dotnet/framework/unmanaged-api/profiling/clr-profilers-and-windows-store-apps#startup-load).

Para revisar requisitos y compilar sin reiniciar ni leer WhatsApp: Test-ReadOnly.ps1 -PreflightOnly. Si Windows rechaza la API, la prueba se detiene; no cambiar permisos ni ejecutar como administrador como solución automática.

## Uso como MCP

El comando `whatsapp-desktop-mcp --read-only` inicia el servidor stdio; el cliente MCP debe ejecutarlo como subproceso. No requiere una clave de OpenAI.

Ejemplo para un cliente que use el formato `mcpServers` (las rutas dependen de la instalación):

```json
{
  "mcpServers": {
    "whatsapp-desktop": {
      "command": "C:\\ruta\\proyecto\\.venv\\Scripts\\whatsapp-desktop-mcp.exe",
      "args": ["--read-only"]
    }
  }
}
```

La configuración varía entre clientes. Este fork aún no incluye un plugin instalado de ChatGPT ni una skill compartible de ChatIÁ. No se ha probado su uso desde todas las superficies de ChatGPT.

Antes de consultar datos reales se necesita una sesión de WhatsApp Desktop y una configuración de depuración revisada. Véase [SECURITY.md](SECURITY.md). El servidor MCP no habilita depuración ni vincula una cuenta automáticamente. El script de prueba anterior activa y retira una conexión temporal solo cuando se ejecuta expresamente.

La opción `--no-read-only` habilita las herramientas de envío, pero cada operación sigue requiriendo confirmación. Los archivos y grupos siguen siendo experimentales y los selectores de archivos heredados dependen del idioma de la interfaz.

## Archivos relevantes

- [HARDENING.md](HARDENING.md): alcance de las correcciones y limitaciones pendientes.
- [SECURITY.md](SECURITY.md): acceso local, datos y riesgos.
- [LICENSE](LICENSE): MIT, conservada del proyecto original.
