---
name: AGENT.md (Marketing Agent Bot)
version: 1.0.0
type: agent-manifest
agent: marketing-agent-bot
audience: claude-code-sessions + developer-reference
last_updated: 2026-05-18
author: Sofia Colombo + Claude
---

# AGENT.md — Marketing Agent Bot

> Source-of-truth del bot de marketing de Sofia Colombo.
> Este archivo documenta capacidades, clientes, crons, estado y reglas operativas.
> Leerlo al inicio de cada sesión de desarrollo antes de modificar el bot.

---

## §1. Identidad y propósito

Bot de Telegram que actúa como asistente de marketing operativo para Sofia Colombo.
Responde en tiempo real vía webhook (Vercel) y corre tareas automáticas por cron.

**Lo que hace:**
- Análisis de campañas Meta Ads por cliente
- Creación completa de campañas en Meta Ads (Campaign → Ad Set → Creative → Ad)
- Generación de copies para anuncios con exportación CSV
- Creación de tareas de diseño para Stefania en ClickUp
- Alertas de tareas en estado "validar" asignadas a Sofia
- Notificaciones de nuevas publicaciones en redes sociales (FB + IG)
- Reporte SEO/AEO mensual con PDF (Search Console + GA4 + PageSpeed + crawl técnico)
- Research de competencia, proyecciones, tendencias, evaluación de marca

**Lo que NO hace:**
- Activar campañas en Meta Ads (solo crea en estado PAUSADO)
- Ejecutar acciones destructivas sin confirmación explícita
- Responder a usuarios que no sean Sofia (filtro por chat_id)

**Usuario único:** Sofia Colombo — `chat_id: 8799388034`

---

## §2. Arquitectura técnica

| Capa | Detalle |
|------|---------|
| Runtime | Flask (Python 3.12) en Vercel Serverless |
| Archivo principal | `/tmp/vercel-deploy/app.py` |
| Espejo local | `/Users/sofiacolombo/Documents/Agentes/Marketing Agent/vercel-bot/api/webhook.py` |
| URL producción | https://vercel-deploy-tan-one.vercel.app |
| Proyecto Vercel | `sofia-claude/vercel-deploy` |
| Deploy | `cd /tmp/vercel-deploy && ~/.npm-global/bin/vercel --prod --yes` |
| Estado persistente | ClickUp task `86ahd3yp7` (campo description como JSON) |
| Modelo IA | `claude-haiku-4-5-20251001` (para classify, copy, acciones) |

**Regla de sincronización:** siempre copiar `app.py → webhook.py` antes de deployar.

---

## §3. Intents y handlers

El routing usa `classify(text, state)` que devuelve un intent string.

| Intent | Trigger keywords / condición | Handler | Descripción |
|--------|------------------------------|---------|-------------|
| `campaigns` | "campaña", "performance", "resultados", "leads", "cómo están" o cliente detectado | `h_campaigns` | Análisis Meta Ads últimos 30d por cliente |
| `create_task` | "tarea", "gráfica", "diseño", "stefania", "pieza" | `h_create_task` | Flujo multi-paso para crear tarea en ClickUp para Stefania |
| `draft_meta` | "crear campaña", "nueva campaña", "armame una campaña", "campaña para" | `h_draft_meta` | Flujo completo: Campaign + Ad Set + Creative + Ad en Meta |
| `copies` | "copy", "copies", "redactame", "variantes", "texto para" | `h_copies` | Genera 3 variantes de copy + CSV listo para planilla de Stefania |
| `research` | "competencia", "competidores", "benchmark" | `h_research` | Research via Meta Ads Library + DuckDuckGo |
| `trends` | "tendencias", "novedades", "qué hay de nuevo" | `h_trends` | Tendencias actuales Meta/Google via DuckDuckGo + Claude |
| `projection` | "proyección", "forecast", "cuánto necesito" | `h_projection` | Proyección de resultados dado presupuesto y objetivo |
| `brand_eval` | "evaluación de marca", "salud de marca", "cómo está la marca" | `h_brand_eval` | Análisis 90d Meta Ads + comparación vs benchmarks |
| `approve_own` | "ok"/"sí"/"dale" con `pending_approvals` activo | `h_approve_own` | Aprueba tarea pendiente (crear_tarea o campana_completa) |
| `approve_validar` | "aprobado", "pásala a done", nombre de tarea en texto | `h_approve_validar` | Marca tarea ClickUp como done / busca match flexible |
| `correct_validar` | "correcciones [tarea]: [desc]" | `h_correct_validar` | Comenta correcciones en ClickUp y vuelve a diseño |
| `continue` | `active_conversation` activo en estado | `h_continue` | Continúa flujo multi-paso (crear_tarea / proyeccion / campana_completa) |

**Flujos multi-paso activos:**
- `crear_tarea`: cliente → objetivo → formato → deadline → copy/brief → aprobación
- `proyeccion`: cliente/objetivo → presupuesto → resultado
- `campana_completa`: cliente → objetivo → nombre → presupuesto → país/edad → URL → imagen → copy review → creación

---

## §4. Clientes configurados

### Meta Ads (campañas y análisis)

| Cliente | Ad Account | FB Page ID | ClickUp WS |
|---------|-----------|-----------|------------|
| BHU/UIN | act_2249213495344845 | 329482500949627 | 90132956644 |
| EBDS | act_2249213495344845 | 102439669276120 | 90132956682 |
| Somostec | act_2001890360733504 | 100114645473318 | — |
| Pediapartner | act_882383240407303 | 61562531372652 | — |

### SEO/AEO (reporte mensual)

| Cliente | URL | SC Property | GA4 Property ID |
|---------|-----|-------------|-----------------|
| EBDS | ebds.online | sc-domain:ebds.online | 426749533 |
| Sibila | sibila.app | sc-domain:sibila.app | 426775519 |
| Tivenos | tivenos.com | sc-domain:tivenos.com | 438322787 |
| BehindU | behind-u.net | sc-domain:behind-u.net | 420486833 |
| ZoWeAre | zoweare.com | — (sin SC) | 521287190 |
| Pediapartner | pediapartner.com | — (sin SC) | 456852321 |

### Social monitoring (FB + IG, LinkedIn pendiente)

| Cliente | FB Page ID | IG Account ID | LinkedIn Org ID |
|---------|-----------|---------------|-----------------|
| Behind-U | 329482500949627 | 17841409037631007 | 33294267 |
| EBDS | 102439669276120 | 17841455358314149 | 81972160 |
| Sibila | 100075997488468 | 50607705062 | 77605671 |
| ZoWeAre | 933257013195402 | 17841479150682279 | 110340230 |
| Tivenos | 100077396560752 | 52254063803 | 9256248 |

### ClickUp workspaces (alertas validar)

| Workspace ID | Cliente | Status done |
|-------------|---------|------------|
| 90132956644 | BHU | hecho |
| 90132956682 | EBDS | done |
| 90131113078 | Tivenos | done |
| 90132956656 | Sibila | done |
| 90132956693 | ZoWeAre | done |

**Filtro validar:** solo tareas asignadas a `sofia.colombo@tivenos.com`

---

## §5. Crons automáticos

| Ruta | Schedule (UTC) | Horario BA | Qué hace |
|------|---------------|-----------|----------|
| `/cron/check-validar` | `0 13,18 * * 1-5` | Lun-Vie 10h y 15h | Chequea tareas en estado "validar" en todos los workspaces |
| `/cron/check-posts` | `*/30 18-21 * * 1-5` | Lun-Vie cada 30min 15h-18:30h | Detecta nuevas publicaciones FB + IG por cliente |
| `/cron/seo-report` | `0 13 1-3 * *` | 1er día hábil del mes 10h | Reporte SEO/AEO completo con PDF |

---

## §6. Estado y persistencia

El estado se guarda como JSON en el campo `description` de la tarea ClickUp `86ahd3yp7`.

```json
{
  "last_offset": 0,
  "notified_validar_tasks": [
    {"task_id": "...", "name": "...", "cliente": "...", "done_status": "done"}
  ],
  "active_conversation": {
    "topic": "campana_completa",
    "step": "presupuesto",
    "data": {}
  },
  "pending_approvals": [
    {"type": "campana_completa", "data": {}}
  ],
  "last_post_ids": {
    "fb_329482500949627": "post_id",
    "ig_17841409037631007": "post_id"
  },
  "last_run": "2026-05-18T13:00:00Z"
}
```

**Tipos de pending_approvals:**
- `crear_tarea` → crea task en ClickUp asignada a Stefania (ID `112045438`)
- `campana_completa` → crea Campaign + Ad Set + Creative + Ad en Meta Ads

---

## §7. APIs y servicios

| Servicio | Uso | Variable de entorno |
|----------|-----|-------------------|
| Telegram Bot API | Webhook entrada + sendMessage/sendDocument | `TELEGRAM_TOKEN` |
| Meta Graph API v21.0 | Ads insights, campaign creation, social posts | `META_TOKEN` |
| ClickUp API v2 | Estado, tareas, comentarios, workspaces | `CLICKUP_TOKEN` |
| Anthropic API | Generación de copy, análisis, classify | `ANTHROPIC_API_KEY` |
| Google OAuth2 | Token para SC + GA4 | Hardcoded en app.py |
| Google Search Console v3 | Métricas de búsqueda orgánica | Google token |
| Google Analytics Data API v1beta | Sesiones, usuarios, canales | Google token |
| PageSpeed Insights v5 | Score performance + Core Web Vitals | Sin key (público) |
| DuckDuckGo Instant Answers | Tendencias y research | Sin key (público) |

**Google OAuth2:**
- Client ID: `75867073584-qof2qcdtmcppgookbkft3qvp8gp4vnq6.apps.googleusercontent.com`
- Refresh token: hardcoded en `GOOGLE_REFRESH_TOKEN` en app.py
- Scopes: `webmasters.readonly` + `analytics.readonly`

---

## §8. Reglas operativas

1. **Nunca activar campañas en Meta Ads** — solo crear en estado `PAUSED`
2. **Nunca ejecutar acciones destructivas** sin confirmación explícita de Sofia
3. **Solo responder al chat_id de Sofia** (`8799388034`) — ignorar cualquier otro
4. **Validar notifica solo tareas asignadas a Sofia** — filtrar por `sofia.colombo@tivenos.com`
5. **Siempre responder en español**
6. **check_validar va solo en el cron** — no llamar desde webhook para evitar condición de carrera
7. **Sincronizar siempre** `app.py → webhook.py` antes de deployar
8. **Forzar rebuild sin cache** si hay problemas de dependencias: agregar `--force` al deploy

---

## §9. Pendientes y próximos features

| Feature | Estado | Notas |
|---------|--------|-------|
| LinkedIn notifications | ⏳ Pendiente | Requiere OAuth LinkedIn separado (token distinto a Meta) |
| LinkedIn org IDs configurados | ✅ En código | Behind-U: 33294267, EBDS: 81972160, Sibila: 77605671, ZoWeAre: 110340230, Tivenos: 9256248 |
| Test campaña completa Meta | ⏳ Pendiente | Probar con cliente real |
| Goya removido | ✅ | Ya no es cliente activo |

---

## §10. Cómo agregar un feature nuevo

1. Editar `/tmp/vercel-deploy/app.py`
2. Si es un intent nuevo: agregar keyword en `classify()` + función `h_nuevo()` + entrada en `handlers` dict
3. Si es un cron nuevo: agregar ruta Flask + entrada en `vercel.json`
4. Sincronizar: `cp /tmp/vercel-deploy/app.py "/Users/sofiacolombo/Documents/Agentes/Marketing Agent/vercel-bot/api/webhook.py"`
5. Deployar: `cd /tmp/vercel-deploy && ~/.npm-global/bin/vercel --prod --yes`
6. Actualizar este AGENT.md con el nuevo feature
