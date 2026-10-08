# Cambios revisables del fork

Base: commit upstream `23821a4261c7ffbd83dbac8ad0035d53d6ae324a`.
Rama de trabajo: `fix/recipient-and-send-verification`.

## Fallos corregidos

1. El transporte aceptaba coincidencias parciales entre nombres aun con identificadores distintos. Ahora exige el identificador completo y lo comprueba otra vez en el mismo programa JavaScript que envía.
2. La verificación aceptaba cualquier salida reciente, incluidos mensajes anteriores al intento, y no comparaba el cuerpo. Ahora conserva una instantánea previa, exige texto exacto y rechaza varias coincidencias nuevas.
3. El envío de archivos podía continuar sin contexto MCP de confirmación y leía el resultado de aceptación desde un campo incorrecto. Ahora texto y archivos comparten confirmación obligatoria.
4. Las instancias stdio podían intercalar sus operaciones sobre la misma app. Un bloqueo del sistema operativo excluye envíos simultáneos desde este fork con el mismo directorio de estado.
5. El descubrimiento CDP aceptaba títulos y URLs que solo contenían la cadena WhatsApp. Ahora se comprueba origen HTTPS exacto y endpoint WebSocket local en el puerto esperado.
6. Las pruebas de integración se activaban por defecto. Ahora requieren una elección explícita y las pruebas unitarias bloquean las conexiones reales.

Los valores que se incorporan a programas JavaScript se codifican como JSON. Los logs de errores de envío guardan el tipo de excepción, no su texto potencialmente sensible.

## Validación

Validación local en Windows: 89 pruebas sintéticas aprobadas, 4 pruebas reales omitidas; Ruff y mypy sin errores. El SDK emitió un aviso de definición incompleta de su campo lifespan. Ejecutar las comprobaciones como indica README. Se incluyen regresiones de destinatarios ambiguos, cambios de borrador, texto distinto, IDs previos, archivos incorrectos, rechazo de confirmación, resultados inciertos, destinos CDP engañosos y exclusión entre procesos.

Las pruebas de los guardas JavaScript ejecutan los programas generados en Node con un DOM ficticio. No ejecutan WhatsApp ni son un benchmark.

## Pendiente antes de usarlo con una cuenta

- Medir latencia y consumo de lectura en una caché real.
- Validar estructuras de mensajes, nombres de módulos internos y selectores con la versión e idioma elegidos.
- Revisar el acceso local al puerto CDP y el ciclo de vida de la depuración.
- Probar los envíos en un entorno elegido por el propietario, sin reintentos automáticos.
- Completar la integración de ChatIÁ como skill/plugin, si esta arquitectura resulta viable.

No se garantiza historial completo, entrega, compatibilidad futura ni ausencia de bloqueos.
