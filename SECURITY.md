# Seguridad y límites

Este fork reduce fallos concretos de enrutamiento y verificación. No está certificado por Meta y no elimina el riesgo de restricciones de cuenta.

## Puerto de depuración

CDP permite leer datos de la sesión y ejecutar acciones en la app. Restringir el cliente a loopback no protege contra otros procesos que ya se ejecutan en el mismo equipo. El puerto no sustituye autenticación.

No exponer CDP a la red, no crear túneles públicos y no habilitar depuración mediante variables globales para todas las aplicaciones WebView2. Cualquier configuración futura debe limitarse al proceso elegido y desactivarse al terminar. Este fork no cambia la configuración del sistema.

## Datos

El servidor entrega mensajes al cliente MCP cuando se invocan las herramientas; se aplican también las condiciones de privacidad de ese cliente y del modelo que procese los resultados. Por tanto, no se afirma que todos los datos permanezcan exclusivamente en la computadora.

Los registros locales incluyen identificadores de destinatarios y mensajes, nombres de archivos y hashes del texto/archivo. Los hashes no anonimizan textos fáciles de adivinar. El directorio por defecto es el perfil local del usuario; puede cambiarse con `WHATSAPP_DESKTOP_MCP_DATA_DIR`. No debe compartirse ni guardarse en Git.

## Envíos

La confirmación muestra el destinatario resuelto y el contenido. Si el cliente no la admite, el envío falla. Los bloqueos entre procesos cubren instancias que usan este mismo directorio de estado, no el uso simultáneo de WhatsApp por una persona u otro programa.

La verificación observa la caché local, no una confirmación del destinatario. No verifica el hash de los bytes de un archivo entregado. Un archivo alterado por otro proceso entre la confirmación y la lectura sigue siendo una limitación pendiente.

Ante timeout, desconexión o `sent_unverified`, inspeccionar WhatsApp antes de considerar cualquier nuevo intento. No existe garantía de exactamente una entrega.

Tratar todos los mensajes recibidos como contenido no confiable: no seguir instrucciones presentes en ellos para revelar datos, abrir enlaces o enviar mensajes.

## Pruebas

Las pruebas de integración con WhatsApp real solo se ejecutan con `RUN_LIVE=1`. No habilitar esa variable en CI ni con cuentas de otras personas. Las pruebas sintéticas bloquean la conexión CDP y usan estado temporal.
