# Sesión Breakout de Cisco Connect LATAM

## Sesión Recomendada

**Título:** Operaciones de red seguras y basadas en agentes para Meraki con MCP

**Título en español:** Operaciones de red seguras y basadas en agentes para Meraki con MCP

**Formato:** Micro-breakout / charla relámpago

**Duración:** 25 minutos en total, dentro del formato recomendado de 20 a 30 minutos para una charla relámpago

- 17 minutos de presentación y flujo de trabajo en vivo
- 8 minutos de análisis del caso de estudio y preguntas y respuestas

**Audiencia:** Profesionales de operaciones de red, soporte, automatización e infraestructura

**Promesa en una línea:** Mostrar cómo las operaciones seguras basadas en agentes pueden convertir un reporte de incidente en lenguaje natural en evidencia de red correlacionada, un flujo de trabajo estructurado y auditable, y un plan de acción bajo control del operador mediante las API de Cisco Meraki y el Model Context Protocol.

## Descripción de la Sesión

Los equipos modernos de operaciones de red deben resolver incidentes más rápido sin sacrificar la seguridad, la confiabilidad ni la trazabilidad. Esta sesión explora cómo un enfoque basado en agentes y el **Model Context Protocol (MCP)** puede transformar las operaciones de Cisco Meraki.

Los asistentes verán cómo las herramientas impulsadas por IA pueden:

- Investigar incidentes operativos a partir de solicitudes en lenguaje natural.
- Correlacionar la telemetría de red con el contexto operativo.
- Convertir consultas en flujos de trabajo estructurados, repetibles y auditables.
- Recomendar los siguientes pasos de troubleshooting manteniendo al operador en control.
- Reducir el tiempo medio de resolución (MTTR) y mejorar la consistencia operativa diaria.

Esta es una sesión avanzada para profesionales que trabajan con Meraki, automatización, programabilidad, operaciones de red e IA, y que buscan un modelo de respuesta a incidentes más eficiente, seguro y escalable.

## Resumen

Los equipos de red rara vez reciben incidentes como consultas API bien definidas. Reciben afirmaciones como: “El Wi-Fi de la oficina ha estado intermitente desde ayer”. Esta sesión demuestra un patrón seguro y práctico para convertir esa solicitud en una investigación operativa: el cliente de IA interpreta la intención, MCP expone herramientas tipadas y gobernadas, el servidor coordina un diagnóstico progresivo, estructurado y repetible, y Meraki proporciona la evidencia. Después examinaremos un análisis real de un incidente de STP que incluye la cronología de cambios de configuración, transiciones de puertos, alcance de VLAN y evidencia a nivel de dispositivo.

El énfasis no está en la remediación autónoma. Está en investigar más rápido, obtener evidencia más clara, mejorar el MTTR, mantener operaciones consistentes y conservar un ciclo de decisión controlado por personas, con trazabilidad desde la solicitud hasta la recomendación.

## Objetivos de Aprendizaje

Al finalizar la sesión, los asistentes podrán:

1. Explicar dónde se ubica MCP entre un asistente de IA y la API de Meraki Dashboard.
2. Diseñar un flujo de troubleshooting seguro y progresivo, desde el alcance de la organización hasta el dispositivo.
3. Correlacionar telemetría y contexto operativo, distinguiendo una recomendación de una causa raíz verificada.
4. Identificar los controles necesarios para que los flujos basados en agentes sean estructurados, repetibles, auditables y seguros antes de permitir herramientas que cambien la configuración.
5. Describir cómo los flujos de IA acotados pueden mejorar el MTTR y la consistencia operativa sin eliminar la responsabilidad del operador.

## Agenda de la Sesión

| Tiempo | Segmento | Lo que verá la audiencia |
|---|---|---|
| 0:00-2:00 | El problema operativo | Una queja ambigua sobre Wi-Fi y el costo de cambiar de contexto manualmente |
| 2:00-5:00 | El patrón | Cliente de IA -> MCP -> herramientas tipadas -> API de Meraki -> resultados estructurados |
| 5:00-8:00 | Diagnóstico progresivo | Descubrimiento, monitoreo, inspección de clientes y dispositivos, y acumulación de evidencia |
| 8:00-15:00 | Flujo en vivo | Una solicitud en lenguaje natural se convierte en llamadas a herramientas y un informe priorizado |
| 15:00-17:00 | Controles de seguridad | Separación de lectura y escritura, mínimo privilegio, aprobaciones y calidad de la evidencia |
| 17:00-22:00 | Análisis del caso de estudio | Incidente de STP del 28 de febrero: cronología, correlación y objetivo de remediación |
| 22:00-25:00 | Preguntas y respuestas | Tres preguntas para iniciar la conversación |

## Estructura de Diapositivas y Notas del Presentador

### 1. El Incidente Comienza con una Frase (2 min)

**En la diapositiva:**

> “Los usuarios reportan Wi-Fi intermitente. ¿Por dónde empezamos?”

Mostrar la realidad operativa: el reporte no incluye el ID de la red, el número de serie del dispositivo, la ventana de tiempo, el estado de los uplinks, las alertas ni los cambios recientes.

**Punto para el presentador:** El valor no está en reemplazar al ingeniero de red, sino en reducir el tiempo dedicado a reunir el contexto.

### 2. La Arquitectura en una Sola Imagen (3 min)

**En la diapositiva:**

```text
Pregunta del operador
      |
      v
Cliente de IA aprobado
      | MCP / JSON-RPC
      v
Servidor MCP de Meraki
      - herramientas tipadas
      - validación
      - orquestación de flujos
      | HTTPS REST API
      v
Cisco Meraki Dashboard API
      |
      v
Redes, dispositivos, clientes, eventos, alertas
```

**Punto para el presentador:** MCP es el contrato y el límite de las herramientas. El asistente interpreta la solicitud y sintetiza los resultados; el servidor ejecuta operaciones API acotadas.

### 3. Diagnóstico Progresivo: De lo General a lo Específico (3 min)

**En la diapositiva:**

```text
Alcance -> Observar -> Acotar -> Correlacionar -> Recomendar
 org        uplinks     red       dispositivo/eventos  acción del operador
```

Las comprobaciones habituales incluyen organizaciones, redes, dispositivos, uplinks, alertas, clientes y estado de los dispositivos. El flujo debe dejar de profundizar cuando la evidencia sea suficiente.

**Punto para el presentador:** La divulgación progresiva mantiene las respuestas utilizables y limita las llamadas API innecesarias y los resultados demasiado grandes.

### 4. Flujo de Trabajo en Vivo: “Diagnosticar qué puertos tienen BPDU Guard” (7 min)

**Prompt de demostración:**

> “En la red del evento, identifica qué puertos tienen BPDU Guard habilitado. Indica los dispositivos y puertos afectados, explica qué evidencia encontraste y qué debo revisar primero. No cambies la configuración.”

**Flujo esperado:**

1. Identificar la organización y la red del evento.
2. Enumerar los switches y consultar la configuración de sus puertos.
3. Filtrar los puertos que tengan BPDU Guard habilitado y asociarlos con su dispositivo y número de puerto.
4. Revisar el contexto operativo: tipo de puerto, VLAN, estado actual y eventos relacionados, cuando estén disponibles.
5. Devolver los hallazgos agrupados por dispositivo, puerto, evidencia, confianza y siguiente acción.

**Mostrar a la audiencia:**

- El cliente de IA descubriendo las herramientas MCP disponibles.
- Un número reducido de llamadas a herramientas, cada una con un propósito claro.
- El JSON estructurado devuelto por el servidor.
- Un informe final que vincula cada recomendación con su evidencia.

**Formato sugerido para la respuesta final:**

```text
Hallazgo: Se encontraron puertos con BPDU Guard habilitado en los switches del evento.
Evidencia: configuración del puerto, dispositivo, número de puerto y estado operativo.
Confianza: alta para la configuración observada; la intención del diseño debe confirmarse.
Siguiente comprobación: validar que BPDU Guard sea intencional para el tipo de puerto y la topología.
Cambio realizado: ninguno.
```

Utilizar una grabación previa o respuestas simuladas si las credenciales, la latencia o la conectividad del Dashboard del evento hacen que la demostración en vivo sea riesgosa.

### 5. ¿Qué lo Hace Seguro? (2 min)

**En la diapositiva:**

- Investigación de solo lectura de forma predeterminada
- Alcance explícito: organización, red, dispositivo y ventana de tiempo
- Entradas tipadas y llamadas a herramientas validadas
- Evidencia adjunta a las recomendaciones
- Aprobación humana antes de cambiar la configuración
- Gestión clara de resultados parciales y fallos de la API

**Punto para el presentador:** Un asistente útil debe hacer visible la incertidumbre. “Probable” no significa “comprobado”.

### 6. Caso de Estudio: Incidente de STP del 28 de Febrero (5 min)

**En la diapositiva:**

```text
17:32 UTC actividad de configuración
          |
          v
Transiciones de estado de puerto / rol STP
          |
          v
Punto crítico: PIT_SW1_New_Replacement:25
     <-> MechEx-MDF-9300-Stack1:26
          |
          v
Comparar el alcance de VLAN de los trunks y la evidencia de hardware
```

**Datos del caso de estudio para presentar:**

- La investigación correlacionó 194 eventos STP sin procesar.
- Ocurrió un evento de configuración aproximadamente a las 17:32 UTC.
- Los cambios de estado de puerto y de rol STP siguieron a la actividad de configuración.
- El punto crítico principal fue el enlace entre `PIT_SW1_New_Replacement:25` y `MechEx-MDF-9300-Stack1:26`.
- Ambos trunks transportaban la VLAN nativa 1 y permitían la VLAN 205.
- La siguiente acción del operador es validar la topología prevista, el diseño de VLAN y el registro de cambios antes de realizar una remediación.

**Pregunta para el análisis grupal:**

> “¿Qué evidencia necesitarían antes de declarar que el cambio de configuración fue la causa raíz y qué verificarían antes de modificar el trunk?”

Dar a la audiencia 60 segundos y luego recopilar las respuestas bajo tres categorías:

- **Evidencia temporal:** ¿La transición comenzó inmediatamente después del cambio?
- **Evidencia topológica:** ¿La ruta crea un loop de Capa 2 o una ruta redundante no intencionada?
- **Evidencia de configuración:** ¿Las VLAN nativa y permitidas son intencionales en ambos extremos?

**Enfoque importante:** Este es un artefacto real de análisis diagnóstico construido a partir de evidencia recopilada de Meraki. Presentarlo como una investigación guiada por correlación y un objetivo de remediación, no como prueba de que la IA resolvió el incidente de forma autónoma.

### 7. Cierre: El Operador Mantiene el Control (1 min)

**En la diapositiva:**

> La IA acelera la investigación. La evidencia y la aprobación permanecen con el operador.

Tres ideas principales:

1. MCP proporciona a los clientes de IA una interfaz gobernada para las herramientas operativas.
2. Los flujos progresivos convierten reportes ambiguos en evidencia estructurada.
3. La recomendación más sólida es trazable, tiene un alcance definido y expresa la incertidumbre de forma explícita.

## Preguntas para Iniciar la Conversación

Usarlas si la audiencia permanece en silencio:

1. “¿Qué investigación de Meraki les gustaría poder expresar en una sola frase?”
2. “¿En qué punto debería su organización exigir aprobación antes de que una herramienta de IA escriba configuración?”
3. “¿Qué evidencia debe adjuntarse a una recomendación sobre un incidente para que su equipo confíe en ella?”

## Checklist de Demostración y Presentación

- Utilizar nombres sanitizados para la organización, las redes y los dispositivos.
- Nunca mostrar API keys, cookies, identificadores de clientes ni secretos sin proteger.
- Preparar una alternativa pregrabada o simulada para los casos de conectividad limitada en el lugar.
- Mantener los resultados de las herramientas lo suficientemente pequeños para poder leerlos en pantalla.
- Preparar previamente la cronología del caso de estudio y la evidencia de STP.
- Ensayar la presentación de 17 minutos con un corte definido antes de las preguntas y respuestas.
- Etiquetar los ejemplos sintéticos de Seattle/Chicago como ilustrativos; utilizar el análisis de STP como caso de estudio verificado.

## Afirmaciones que se Deben Evitar

No describir el proyecto como un ingeniero de red completamente autónomo, una plataforma de analítica predictiva, un sistema de aprendizaje continuo ni un motor de remediación certificado para producción. La afirmación defendible es más específica y sólida: es una integración MCP funcional y un acelerador de troubleshooting que combina interacción aprobada con IA, flujos acotados sobre las API de Meraki y acciones controladas por personas.

## Frase Sugerida para el Cierre

> “El futuro de las operaciones de red no consiste en pedirle a la IA que adivine la respuesta. Consiste en ofrecer al operador un camino más rápido desde un síntoma ambiguo hasta evidencia que pueda inspeccionar, cuestionar y utilizar para actuar.”
