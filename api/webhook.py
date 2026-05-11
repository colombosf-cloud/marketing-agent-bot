import json, os, re
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler
from datetime import datetime

# --- Config ---
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CLICKUP_TOKEN = os.environ['CLICKUP_TOKEN']
META_TOKEN = os.environ['META_TOKEN']
ANTHROPIC_KEY = os.environ['ANTHROPIC_API_KEY']
STATE_TASK_ID = '86ahd3yp7'
SOFIA_CHAT_ID = 8799388034
STEFANIA_ID = 112045438
PARRILLA = 'https://workdrive.zohoexternal.com/external/sheet/f952ca11370ee5ce5c463f1ec5bfd85944c2dad0929cd333147285edfafa1712'

CLIENTS = {
    'bhu':      {'name': 'BHU/UIN', 'meta': 'act_2249213495344845', 'list_id': '901326439751', 'done': 'hecho'},
    'uin':      {'name': 'BHU/UIN', 'meta': 'act_2249213495344845', 'list_id': '901326439751', 'done': 'hecho'},
    'behind':   {'name': 'BHU/UIN', 'meta': 'act_2249213495344845', 'list_id': '901326439751', 'done': 'hecho'},
    'ebds':     {'name': 'EBDS',    'meta': 'act_2249213495344845', 'list_id': '901324498269', 'done': 'done'},
    'goya':     {'name': 'Goya',    'meta': 'act_2677321078947278', 'done': 'done'},
    'somostec': {'name': 'Somostec','meta': 'act_865020240718182',  'done': 'done'},
    'tivenos':  {'name': 'Tivenos', 'list_id': '901324496237', 'done': 'done'},
    'sibila':   {'name': 'Sibila',  'list_id': '901324495956', 'done': 'done'},
    'zoweare':  {'name': 'ZoWeAre', 'done': 'done'},
}

WORKSPACES = {
    '90132956644': {'name': 'BHU',     'done': 'hecho'},
    '90132956682': {'name': 'EBDS',    'done': 'done'},
    '90131113078': {'name': 'Tivenos', 'done': 'done'},
    '90132956656': {'name': 'Sibila',  'done': 'done'},
    '90132956693': {'name': 'ZoWeAre', 'done': 'done'},
}

# --- HTTP helpers ---
def http_req(url, method='GET', data=None, headers=None):
    h = {'Content-Type': 'application/json', **(headers or {})}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def tg_send(text):
    http_req(
        f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
        'POST', {'chat_id': SOFIA_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}
    )

def cu_get(path):
    return http_req(f'https://api.clickup.com/api/v2/{path}', headers={'Authorization': CLICKUP_TOKEN})

def cu_post(path, data):
    return http_req(f'https://api.clickup.com/api/v2/{path}', 'POST', data, {'Authorization': CLICKUP_TOKEN})

def cu_put(path, data):
    return http_req(f'https://api.clickup.com/api/v2/{path}', 'PUT', data, {'Authorization': CLICKUP_TOKEN})

def claude(prompt, system=None):
    data = {
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': 1024,
        'messages': [{'role': 'user', 'content': prompt}]
    }
    if system:
        data['system'] = system
    result = http_req('https://api.anthropic.com/v1/messages', 'POST', data, {
        'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2023-06-01'
    })
    return result['content'][0]['text']

# --- State ---
def read_state():
    try:
        task = cu_get(f'task/{STATE_TASK_ID}')
        desc = task.get('description', '')
        if desc:
            return json.loads(desc)
    except Exception:
        pass
    return {'last_offset': 0, 'notified_validar_tasks': [], 'active_conversation': None, 'pending_approvals': []}

def save_state(state):
    state['last_run'] = datetime.utcnow().isoformat() + 'Z'
    cu_put(f'task/{STATE_TASK_ID}', {'description': json.dumps(state)})

# --- Helpers ---
def detect_client(text):
    t = text.lower()
    for key, client in CLIENTS.items():
        if key in t:
            return client
    return None

def notified_ids(state):
    return {(t['task_id'] if isinstance(t, dict) else t) for t in state.get('notified_validar_tasks', [])}

# --- Intent classification ---
def classify(text, state):
    t = text.lower().strip()
    if state.get('active_conversation'):
        return 'continue'
    if t in ['ok', 'aprobado', 'dale', 'sí', 'si', 'adelante'] and state.get('pending_approvals'):
        return 'approve_own'
    if re.match(r'^ok .+', t) and not state.get('pending_approvals'):
        return 'approve_validar'
    if re.match(r'^correcciones .+:.+', t, re.DOTALL):
        return 'correct_validar'
    if any(w in t for w in ['campaña', 'campañas', 'performance', 'resultados', 'leads', 'gastaron', 'profundiza', 'cómo están']) or detect_client(t):
        return 'campaigns'
    if any(w in t for w in ['tarea', 'gráfica', 'diseño', 'stefania', 'anuncio', 'pieza', 'necesito crear']):
        return 'create_task'
    if any(w in t for w in ['proyección', 'proyectame', 'cuánto necesito', 'forecast', 'estimación']):
        return 'projection'
    if any(w in t for w in ['competencia', 'competidores', 'benchmark']):
        return 'research'
    if any(w in t for w in ['copy', 'copies', 'redactame', 'escribime', 'variantes', 'texto para']):
        return 'copies'
    if any(w in t for w in ['tendencias', 'novedades', 'qué hay de nuevo', 'actualización']):
        return 'trends'
    if any(w in t for w in ['crear campaña', 'nueva campaña', 'draft en meta']):
        return 'draft_meta'
    return 'unknown'

# --- Handlers ---
def h_campaigns(text, state):
    client = detect_client(text)
    is_deep = any(w in text.lower() for w in ['profundiza', 'detalle', 'ad set', 'conjunto'])

    if not client:
        tg_send('¿Para qué cliente?\n\n• BHU/UIN\n• EBDS\n• Goya\n• Somostec')
        return state

    if 'meta' not in client:
        tg_send(f'❌ {client["name"]} no tiene Meta Ads disponible.')
        return state

    level = 'adset' if is_deep else 'campaign'
    url = (f'https://graph.facebook.com/v21.0/{client["meta"]}/insights'
           f'?fields=campaign_name,adset_name,spend,impressions,clicks,ctr,cpm,cpc,reach,actions,cost_per_action_type'
           f'&date_preset=last_30d&level={level}&access_token={META_TOKEN}')
    data = http_req(url)
    campaigns = data.get('data', [])

    if not campaigns:
        tg_send(f'No hay datos de campañas para {client["name"]} en los últimos 30 días.')
        return state

    prompt = f"""Analizá estos datos de Meta Ads para {client['name']} (últimos 30 días, nivel {level}).
Datos: {json.dumps(campaigns[:12])}

Generá un resumen conciso para Telegram en español con Markdown:
- Encabezado: "📊 *{client['name']} — últimos 30 días*"
- Gasto total
- Performance de cada campaña/adset: gasto, leads (si hay), CPL, CTR
- Alertas si hay problemas (CPL alto, sin conversiones, CTR bajo)
- Cierre: "¿Querés profundizar en alguna campaña?"
- Máximo 350 palabras"""

    tg_send(claude(prompt))
    return state

def h_create_task(text, state):
    state['active_conversation'] = {
        'topic': 'crear_tarea', 'step': 'cliente',
        'data': {'cliente': None, 'list_id': None, 'objetivo': None, 'formato': None, 'deadline': None}
    }
    tg_send('¿Para qué cliente es la pieza?\n\n• BHU / UIN\n• EBDS\n• Tivenos\n• Sibila\n• ZoWeAre\n• Goya\n• Somostec')
    return state

def h_create_task_step(text, state, conv):
    step = conv['step']
    data = conv['data']

    if step == 'cliente':
        client = detect_client(text)
        if not client:
            tg_send('No reconocí el cliente. ¿Es BHU, EBDS, Tivenos, Sibila, ZoWeAre, Goya o Somostec?')
            return state
        data['cliente'] = client['name']
        data['list_id'] = client.get('list_id')
        conv['step'] = 'objetivo'
        tg_send('¿Cuál es el objetivo del anuncio?\n_(ej: generar leads, vender producto X, tráfico al sitio, awareness)_')

    elif step == 'objetivo':
        data['objetivo'] = text
        conv['step'] = 'formato'
        tg_send('¿Qué formato necesitás?\n\n• Historia (1080x1920)\n• Feed cuadrado (1080x1080)\n• Feed horizontal (1200x628)\n• Carrusel\n• Varios formatos')

    elif step == 'formato':
        data['formato'] = text
        conv['step'] = 'deadline'
        tg_send('¿Para cuándo lo necesitás?\n_(Si no tenés fecha fija, te sugiero 3 días hábiles)_')

    elif step == 'deadline':
        data['deadline'] = text
        conv['step'] = 'aprobacion'

        prompt = f"""Generá copy y brief visual para un anuncio de Meta Ads:
- Cliente: {data['cliente']}
- Objetivo: {data['objetivo']}
- Formato: {data['formato']}

Devolvé SOLO JSON válido:
{{"nombre_tarea": "nombre corto descriptivo (máx 60 chars)", "copy": "Headline: ...\\nCuerpo: ...\\nCTA: ...", "brief_visual": "concepto visual, colores, estilo, referencia"}}"""

        try:
            result = claude(prompt)
            match = re.search(r'\{.*\}', result, re.DOTALL)
            gen = json.loads(match.group()) if match else {}
            data['nombre_tarea'] = gen.get('nombre_tarea', f'Anuncio {data["cliente"]}')
            data['copy'] = gen.get('copy', 'Copy pendiente')
            data['brief_visual'] = gen.get('brief_visual', 'Brief pendiente')
        except Exception:
            data['nombre_tarea'] = f'Anuncio {data["cliente"]}'
            data['copy'] = 'Copy pendiente de generación'
            data['brief_visual'] = 'Brief visual pendiente'

        msg = (f'📋 *Resumen de tarea para Stefania*\n\n'
               f'🏢 Cliente: {data["cliente"]}\n'
               f'🎯 Objetivo: {data["objetivo"]}\n'
               f'📐 Formato: {data["formato"]}\n'
               f'📅 Deadline: {data["deadline"]}\n\n'
               f'✍️ *Copy sugerido:*\n{data["copy"]}\n\n'
               f'🎨 *Brief visual:*\n{data["brief_visual"]}\n\n'
               f'¿La subo tal cual o querés cambiar algo?\n'
               f'_("ok" para crear | "cambios: [descripción]" para ajustar)_')
        tg_send(msg)
        state['pending_approvals'] = [{'type': 'crear_tarea', 'data': data}]

    state['active_conversation'] = conv
    return state

def h_projection(text, state):
    state['active_conversation'] = {'topic': 'proyeccion', 'step': 'cliente', 'data': {}}
    tg_send('¿Para qué cliente y cuál es el objetivo?\n_(leads / ventas / tráfico / awareness)_')
    return state

def h_projection_step(text, state, conv):
    step = conv['step']
    data = conv['data']

    if step == 'cliente':
        data['cliente_objetivo'] = text
        conv['step'] = 'presupuesto'
        tg_send('¿Cuál es el presupuesto mensual disponible en USD?')
    elif step == 'presupuesto':
        data['presupuesto'] = text
        prompt = f"""Proyección de campaña Meta Ads:
- Cliente/Objetivo: {data['cliente_objetivo']}
- Presupuesto mensual: {data['presupuesto']} USD

Benchmarks: Educación CPL $15-40 CTR 0.8-1.5% CPM $20-35 | B2B CPL $25-60 CTR 0.5-1% CPM $30-50 | eCommerce ROAS 2-4x CTR 1-2% CPM $15-25 | SaaS CPL $30-80 CTR 0.6-1.2% CPM $25-45

Respondé en español con Markdown:
📈 *Proyección — [CLIENTE]*
💰 Presupuesto: $X/mes | 🎯 Objetivo: [obj]

*Basado en benchmarks del sector [sector]:*
📉 Conservador: X leads | CPL $X | CTR X%
📊 Esperado: X leads | CPL $X | CTR X%
📈 Optimista: X leads | CPL $X | CTR X%

*Supuestos:* CPM $X | CTR X% | Conv X%
¿Querés ajustar algún parámetro?"""
        tg_send(claude(prompt))
        state['active_conversation'] = None
    state['active_conversation'] = conv if step == 'cliente' else None
    return state

def h_draft_meta(text, state):
    state['active_conversation'] = {'topic': 'draft_meta', 'step': 'cliente', 'data': {}}
    tg_send('¿Para qué cliente?\n\n• BHU/UIN\n• EBDS\n• Goya\n• Somostec')
    return state

def h_draft_meta_step(text, state, conv):
    step = conv['step']
    data = conv['data']
    steps = ['cliente', 'objetivo', 'nombre', 'presupuesto', 'audiencia']
    questions = {
        'objetivo': '¿Cuál es el objetivo?\n\n• LEAD_GENERATION\n• LINK_CLICKS\n• BRAND_AWARENESS\n• OUTCOME_LEADS',
        'nombre': '¿Cuál es el nombre de la campaña?',
        'presupuesto': '¿Cuál es el presupuesto diario en USD?',
        'audiencia': '¿Para qué audiencia? (país, edad, intereses)'
    }

    if step == 'cliente':
        client = detect_client(text)
        if not client or 'meta' not in client:
            tg_send('No encontré ese cliente con Meta Ads. ¿Es BHU, EBDS, Goya o Somostec?')
            return state
        data['client'] = client
        conv['step'] = 'objetivo'
        tg_send(questions['objetivo'])
    elif step in questions:
        data[step] = text
        next_step = steps[steps.index(step) + 1] if step != 'audiencia' else None
        if next_step:
            conv['step'] = next_step
            tg_send(questions.get(next_step, ''))
        else:
            conv['step'] = 'aprobacion'
            c = data['client']
            msg = (f'📋 *Resumen del draft*\n\n'
                   f'🏢 Cliente: {c["name"]}\n'
                   f'🎯 Objetivo: {data["objetivo"]}\n'
                   f'📋 Nombre: {data["nombre"]}\n'
                   f'💰 Presupuesto diario: ${data["presupuesto"]}\n'
                   f'👥 Audiencia: {data["audiencia"]}\n\n'
                   f'⏸️ Se creará *PAUSADA* (vos la activás cuando esté lista)\n\n'
                   f'¿Creo el draft?\n_("ok" para crear)_')
            tg_send(msg)
            state['pending_approvals'] = [{'type': 'draft_meta', 'data': data}]

    state['active_conversation'] = conv
    return state

def h_continue(text, state):
    conv = state.get('active_conversation', {})
    topic = conv.get('topic')
    if topic == 'crear_tarea':
        return h_create_task_step(text, state, conv)
    elif topic == 'proyeccion':
        return h_projection_step(text, state, conv)
    elif topic == 'draft_meta':
        return h_draft_meta_step(text, state, conv)
    state['active_conversation'] = None
    return state

def h_approve_own(text, state):
    approvals = state.get('pending_approvals', [])
    if not approvals:
        tg_send('No hay propuestas pendientes.')
        return state

    approval = approvals[0]
    t = text.lower().strip()

    if t.startswith('cambios:'):
        changes = text[8:].strip()
        data = approval['data']
        prompt = f"""Ajustá este copy/brief según las correcciones:
Copy actual: {data.get('copy', '')}
Brief actual: {data.get('brief_visual', '')}
Correcciones: {changes}
Devolvé SOLO JSON: {{"copy": "...", "brief_visual": "..."}}"""
        try:
            result = claude(prompt)
            match = re.search(r'\{.*\}', result, re.DOTALL)
            if match:
                adj = json.loads(match.group())
                data['copy'] = adj.get('copy', data.get('copy'))
                data['brief_visual'] = adj.get('brief_visual', data.get('brief_visual'))
        except Exception:
            pass
        tg_send(f'📋 *Resumen actualizado*\n\n✍️ *Copy:*\n{data["copy"]}\n\n🎨 *Brief:*\n{data["brief_visual"]}\n\n_("ok" para crear)_')
        approval['data'] = data
        state['pending_approvals'] = [approval]
        return state

    if approval['type'] == 'crear_tarea':
        data = approval['data']
        list_id = data.get('list_id')
        if not list_id:
            tg_send(f'❌ {data["cliente"]} no tiene lista de ClickUp configurada.')
        else:
            try:
                result = cu_post(f'list/{list_id}/task', {
                    'name': data['nombre_tarea'],
                    'description': (f"🎯 Objetivo: {data['objetivo']}\n\n"
                                    f"✍️ Copy:\n{data['copy']}\n\n"
                                    f"📐 Formato: {data['formato']}\n\n"
                                    f"🎨 Brief visual:\n{data['brief_visual']}\n\n"
                                    f"📅 Deadline: {data['deadline']}\n\n"
                                    f"📊 Parrilla:\n{PARRILLA}"),
                    'assignees': [STEFANIA_ID],
                    'status': 'diseño'
                })
                tg_send(f'✅ *Tarea creada para Stefania*\n\n📋 {data["nombre_tarea"]}\n📅 Deadline: {data["deadline"]}\n🔗 {result.get("url", "")}')
            except Exception as e:
                tg_send(f'❌ Error al crear tarea: {str(e)}')

    elif approval['type'] == 'draft_meta':
        data = approval['data']
        client = data['client']
        try:
            result = http_req(
                f'https://graph.facebook.com/v21.0/{client["meta"]}/campaigns',
                'POST',
                {'name': data['nombre'], 'objective': data['objetivo'],
                 'status': 'PAUSED', 'special_ad_categories': [],
                 'access_token': META_TOKEN}
            )
            tg_send(f'✅ *Draft creado en Meta Ads*\n\n📋 {data["nombre"]}\n🆔 ID: {result.get("id", "")}\n⏸️ Estado: PAUSADA')
        except Exception as e:
            tg_send(f'❌ Error al crear draft: {str(e)}')

    state['pending_approvals'] = []
    state['active_conversation'] = None
    return state

def h_approve_validar(text, state):
    task_name = re.sub(r'^ok\s+', '', text, flags=re.IGNORECASE).strip()
    notified = state.get('notified_validar_tasks', [])
    task = next((t for t in notified if isinstance(t, dict) and task_name.lower() in t.get('name', '').lower()), None)
    if not task:
        tg_send(f'No encontré la tarea "{task_name}" en los pendientes.')
        return state
    try:
        cu_put(f'task/{task["task_id"]}', {'status': task.get('done_status', 'done')})
        tg_send(f'✅ *{task["name"]}* marcada como {task.get("done_status", "done")}.')
    except Exception as e:
        tg_send(f'❌ Error: {str(e)}')
    return state

def h_correct_validar(text, state):
    match = re.match(r'correcciones\s+(.+?):\s*(.+)', text, re.IGNORECASE | re.DOTALL)
    if not match:
        tg_send('Formato: "correcciones [nombre tarea]: [descripción]"')
        return state
    task_name, corrections = match.group(1).strip(), match.group(2).strip()
    notified = state.get('notified_validar_tasks', [])
    task = next((t for t in notified if isinstance(t, dict) and task_name.lower() in t.get('name', '').lower()), None)
    if not task:
        tg_send(f'No encontré la tarea "{task_name}".')
        return state
    try:
        cu_post(f'task/{task["task_id"]}/comment', {'comment_text': f'🔄 Correcciones de Sofia:\n{corrections}'})
        cu_put(f'task/{task["task_id"]}', {'status': 'diseño'})
        tg_send(f'🔄 Correcciones enviadas. *{task["name"]}* vuelve a diseño.')
        state['notified_validar_tasks'] = [t for t in notified if t.get('task_id') != task['task_id']]
    except Exception as e:
        tg_send(f'❌ Error: {str(e)}')
    return state

def h_copies(text, state):
    prompt = f"""El usuario pidió copies para Meta Ads: "{text}"

Generá 3 variantes con ángulos distintos. Formato Telegram Markdown en español:

✍️ *Copies para [cliente] — [formato]*

*Variante 1 — [ángulo]:*
[headline]
[cuerpo]
[CTA]

*Variante 2 — [ángulo]:*
[headline]
[cuerpo]
[CTA]

*Variante 3 — [ángulo]:*
[headline]
[cuerpo]
[CTA]

¿Usás alguna tal cual o querés ajustes?"""
    tg_send(claude(prompt))
    return state

def h_research(text, state):
    prompt = f"""Research de competencia solicitado: "{text}"

Respondé en español con Markdown para Telegram:

🔍 *Research: [competidor/sector]*

🏢 *Posicionamiento:* [descripción]

📢 *Estrategia publicitaria típica:*
• [punto 1]
• [punto 2]

💡 *Ángulos creativos más usados:*
• [ángulo 1]
• [ángulo 2]

🎯 *Oportunidades de diferenciación:*
• [diferenciador 1]
• [diferenciador 2]

¿Querés que profundice en algún punto?"""
    tg_send(claude(prompt))
    return state

def h_trends(text, state):
    prompt = f"""Tendencias de publicidad digital solicitadas: "{text}"

Respondé en español con Markdown para Telegram:

📡 *Tendencias [Meta/Google Ads] — {datetime.now().strftime("%B %Y")}*

1️⃣ [tendencia]: [explicación + impacto práctico]
2️⃣ [tendencia]: [explicación + impacto práctico]
3️⃣ [tendencia]: [explicación + impacto práctico]
4️⃣ [tendencia]: [explicación + impacto práctico]

¿Querés aplicar alguna a un cliente específico?"""
    tg_send(claude(prompt))
    return state

def check_validar(state):
    seen = notified_ids(state)
    for ws_id, ws_info in WORKSPACES.items():
        try:
            result = cu_get(f'team/{ws_id}/task?statuses[]=validar&subtasks=true')
            for task in result.get('tasks', []):
                task_id = task.get('id')
                if task_id in seen:
                    continue
                comments = cu_get(f'task/{task_id}/comment').get('comments', [])
                last_comment = comments[-1].get('comment_text', '') if comments else ''
                wd_match = re.search(r'https?://\S*zoho\S+', last_comment)
                wd_link = wd_match.group() if wd_match else 'No hay link de archivos'
                task_name = task.get('name', '')
                tg_send(
                    f'🔔 *Nueva tarea para revisar*\n\n'
                    f'📋 Tarea: {task_name}\n'
                    f'🏢 Cliente: {ws_info["name"]}\n'
                    f'💬 Comentario: "{last_comment[:200] or "Sin comentarios"}"\n'
                    f'🔗 ClickUp: {task.get("url", "")}\n'
                    f'📂 Archivos: {wd_link}\n\n'
                    f'¿La aprobás o tiene correcciones?\n'
                    f'_("ok {task_name}" para aprobar | "correcciones {task_name}: [desc]" para corregir)_'
                )
                state['notified_validar_tasks'].append({
                    'task_id': task_id, 'name': task_name,
                    'cliente': ws_info['name'], 'done_status': ws_info['done']
                })
                seen.add(task_id)
        except Exception as e:
            print(f'Error workspace {ws_id}: {e}')
    return state

def process(text, state):
    intent = classify(text, state)
    handlers = {
        'campaigns':     h_campaigns,
        'create_task':   h_create_task,
        'continue':      h_continue,
        'approve_own':   h_approve_own,
        'approve_validar': h_approve_validar,
        'correct_validar': h_correct_validar,
        'copies':        h_copies,
        'research':      h_research,
        'trends':        h_trends,
        'projection':    h_projection,
        'draft_meta':    h_draft_meta,
    }
    if intent in handlers:
        return handlers[intent](text, state)
    tg_send('No entendí bien. ¿Qué necesitás?\n\n1️⃣ Análisis de campañas\n2️⃣ Crear tarea para Stefania\n3️⃣ Proyección de campaña\n4️⃣ Research de competencia\n5️⃣ Redactar copies\n6️⃣ Tendencias Meta/Google\n7️⃣ Crear draft en Meta Ads')
    return state

# --- Vercel handler ---
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
            msg = body.get('message', {})
            if not msg or msg.get('chat', {}).get('id') != SOFIA_CHAT_ID:
                return
            text = msg.get('text', '').strip()
            if not text:
                return
            state = read_state()
            state = process(text, state)
            save_state(state)
        except Exception as e:
            print(f'Error: {e}')

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Marketing Agent Bot running!')

    def log_message(self, format, *args):
        pass
