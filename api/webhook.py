import json, os, re, csv, tempfile, base64
import urllib.request, urllib.error, urllib.parse
from datetime import datetime
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, Response, jsonify

app = Flask(__name__)

# --- Config ---
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
CLICKUP_TOKEN = os.environ['CLICKUP_TOKEN']
META_TOKEN = os.environ['META_TOKEN']
ANTHROPIC_KEY = os.environ['ANTHROPIC_API_KEY']
ZOHO_CLIENT_ID     = os.environ.get('ZOHO_CLIENT_ID', '')
ZOHO_CLIENT_SECRET = os.environ.get('ZOHO_CLIENT_SECRET', '')
ZOHO_REFRESH_TOKEN = os.environ.get('ZOHO_REFRESH_TOKEN', '')
# EBDS — datacenter EU (zoho.eu / zohoapis.eu)
ZOHO_EBDS_CLIENT_ID     = os.environ.get('ZOHO_EBDS_CLIENT_ID', '')
ZOHO_EBDS_CLIENT_SECRET = os.environ.get('ZOHO_EBDS_CLIENT_SECRET', '')
ZOHO_EBDS_REFRESH_TOKEN = os.environ.get('ZOHO_EBDS_REFRESH_TOKEN', '')
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
    'somostec': {'name': 'Somostec','meta': 'act_2001890360733504', 'done': 'done'},
    'pediapartner': {'name': 'Pediapartner', 'meta': 'act_882383240407303', 'done': 'done'},
    'pedia':     {'name': 'Pediapartner', 'meta': 'act_882383240407303', 'done': 'done'},
    'tivenos':  {'name': 'Tivenos', 'list_id': '901324496237', 'done': 'done'},
    'sibila':   {'name': 'Sibila',  'list_id': '901324495956', 'done': 'done'},
    'zoweare':  {'name': 'ZoWeAre', 'done': 'done'},
}

CAMPAIGN_CLIENTS = {
    'bhu':          {'name': 'BHU/UIN',     'account': 'act_2249213495344845', 'page': '329482500949627'},
    'uin':          {'name': 'BHU/UIN',     'account': 'act_2249213495344845', 'page': '329482500949627'},
    'behind':       {'name': 'BHU/UIN',     'account': 'act_2249213495344845', 'page': '329482500949627'},
    'ebds':         {'name': 'EBDS',        'account': 'act_2249213495344845', 'page': '102439669276120'},
    'somostec':     {'name': 'Somostec',    'account': 'act_2001890360733504', 'page': '100114645473318'},
    'pediapartner': {'name': 'Pediapartner','account': 'act_882383240407303',  'page': '61562531372652'},
    'pedia':        {'name': 'Pediapartner','account': 'act_882383240407303',  'page': '61562531372652'},
}

COUNTRY_CODES = {
    'argentina': 'AR', 'ar': 'AR',
    'españa': 'ES', 'spain': 'ES', 'es': 'ES',
    'mexico': 'MX', 'méxico': 'MX', 'mx': 'MX',
    'colombia': 'CO', 'co': 'CO',
    'chile': 'CL', 'cl': 'CL',
    'peru': 'PE', 'perú': 'PE', 'pe': 'PE',
    'uruguay': 'UY', 'uy': 'UY',
    'brasil': 'BR', 'brazil': 'BR', 'br': 'BR',
    'estados unidos': 'US', 'usa': 'US',
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

def tg_send_document(filepath, filename, caption='', mimetype='text/csv'):
    boundary = 'boundary7MA4YWxkTr'
    with open(filepath, 'rb') as f:
        file_data = f.read()
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{SOFIA_CHAT_ID}\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\nContent-Type: {mimetype}\r\n\r\n'
    ).encode() + file_data + f'\r\n--{boundary}--\r\n'.encode()
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument',
        data=body, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, method='POST'
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def cu_get(path):
    return http_req(f'https://api.clickup.com/api/v2/{path}', headers={'Authorization': CLICKUP_TOKEN})

def cu_post(path, data):
    return http_req(f'https://api.clickup.com/api/v2/{path}', 'POST', data, {'Authorization': CLICKUP_TOKEN})

def cu_put(path, data):
    return http_req(f'https://api.clickup.com/api/v2/{path}', 'PUT', data, {'Authorization': CLICKUP_TOKEN})

# --- Zoho CRM ---
_zoho_tokens = {'bhu': {'token': '', 'expires': 0}, 'ebds': {'token': '', 'expires': 0}}

def zoho_get_token(client='bhu'):
    """Obtiene access token de Zoho. BHU usa zoho.com, EBDS usa zoho.eu."""
    cache = _zoho_tokens[client]
    now = datetime.utcnow().timestamp()
    if cache['token'] and now < cache['expires']:
        return cache['token']
    if client == 'ebds':
        cid, csec, rtok = ZOHO_EBDS_CLIENT_ID, ZOHO_EBDS_CLIENT_SECRET, ZOHO_EBDS_REFRESH_TOKEN
        auth_url = 'https://accounts.zoho.eu/oauth/v2/token'
    else:
        cid, csec, rtok = ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN
        auth_url = 'https://accounts.zoho.com/oauth/v2/token'
    params = urllib.parse.urlencode({'grant_type': 'refresh_token', 'client_id': cid, 'client_secret': csec, 'refresh_token': rtok})
    req = urllib.request.Request(f'{auth_url}?{params}', data=b'', method='POST')
    with urllib.request.urlopen(req, timeout=15) as r:
        resp = json.loads(r.read())
    token = resp.get('access_token', '')
    cache['token'] = token
    cache['expires'] = now + 3300
    return token

def zoho_get(path, params=None, client='bhu'):
    token = zoho_get_token(client)
    api_domain = 'https://www.zohoapis.eu' if client == 'ebds' else 'https://www.zohoapis.com'
    url = f'{api_domain}/crm/v2/{path}'
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': f'Zoho-oauthtoken {token}'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def _zoho_get_all(module, params, client='bhu', max_pages=10):
    """Pagina automáticamente hasta obtener todos los registros de un módulo Zoho."""
    all_data = []
    for page in range(1, max_pages + 1):
        params['page'] = page
        params['per_page'] = 200
        resp = zoho_get(module, params, client=client)
        batch = resp.get('data', [])
        all_data.extend(batch)
        info = resp.get('info', {})
        if not info.get('more_records', False) or len(batch) < 200:
            break
    return all_data

def zoho_crm_funnel(month_date=None):
    """
    Funnel completo BHU/UIN — con paginación completa.
    Stages: 1.Contactado / 2.Interesado / 3.Evaluando / 4.Promesa de Pago /
            6.Inscrito(a) / 8.Validado para facturar comisión / 99.Perdido
    mql_mes:    deals creados en el mes (Created_Time).
    ventas_mes: deals con Fecha_Matriculado en el mes, institución Universidad Insurgentes.
    leads_por_fuente: filtrado por Created_Time del mes (no histórico).
    """
    from collections import Counter, defaultdict
    if month_date is None:
        month_date = dt.date.today()
    try:
        month_start = month_date.replace(day=1).isoformat()[:10]
        month_end   = month_date.isoformat()[:10]

        # --- Leads (no contactados aún) — paginado ---
        leads_data = _zoho_get_all('Leads', {
            'fields': 'Lead_Status,Lead_Source,Created_Time,Programa_UIN,Owner'
        })

        leads_por_estado = Counter(l.get('Lead_Status') or 'Sin gestión' for l in leads_data)
        # leads_por_fuente filtrado por el mes (no histórico) — se completa con Deals más abajo
        leads_mes_fuente = [l for l in leads_data
                            if month_start <= (l.get('Created_Time') or '')[:10] <= month_end]
        leads_por_fuente = Counter(l.get('Lead_Source') or 'Sin fuente' for l in leads_mes_fuente)

        # --- Deals (pipeline) — paginado ---
        deals_data = _zoho_get_all('Deals', {
            'fields': 'Stage,Programa_UIN,Lead_Source,Unidad_de_Negocio,Instituci_n,Created_Time,Modified_Time,Fecha_Matriculado,Owner'
        })

        # Clasificar stages
        ESTUDIANTE_STAGES = {
            '8. validado para facturar comisión', '8. validado para facturar comision',
            '6. inscripto', '6. inscrito',
            '5. estudiante', '7. validado para comision',
            'estudiante', 'inscripto', 'inscrito', 'validado para facturar',
        }
        PERDIDO_STAGES = {'99. perdido', 'perdido', '99.perdido'}

        stages = Counter(d.get('Stage') or 'Sin etapa' for d in deals_data)
        programas = Counter(d.get('Programa_UIN') or 'Sin programa' for d in deals_data
                            if d.get('Stage', '').lower() not in PERDIDO_STAGES)

        # Agrupar en funnel (all-time, para la vista de pipeline)
        funnel = {
            'leads_sin_contactar': sum(leads_por_estado.values()),
            'contactados': 0, 'interesados': 0, 'evaluando': 0,
            'promesa_pago': 0, 'estudiantes': 0, 'perdidos': 0,
        }
        for stage, count in stages.items():
            sl = stage.lower()
            if '1.' in sl or ('contactado' in sl and '5.' not in sl): funnel['contactados']   += count
            elif '2.' in sl or 'interesado' in sl: funnel['interesados']  += count
            elif '3.' in sl or 'evaluando'  in sl: funnel['evaluando']    += count
            elif '4.' in sl or 'promesa'    in sl: funnel['promesa_pago'] += count
            elif any(s in sl for s in ESTUDIANTE_STAGES): funnel['estudiantes'] += count
            elif any(s in sl for s in PERDIDO_STAGES):    funnel['perdidos']    += count

        # --- MQL del mes: deals creados en el mes ---
        deals_mes = [d for d in deals_data
                     if month_start <= (d.get('Created_Time') or '')[:10] <= month_end]
        mql_mes = len(deals_mes)
        # Sumar Deals del mes a leads_por_fuente (leads convertidos ya no están en módulo Leads)
        leads_por_fuente += Counter(d.get('Lead_Source') or 'Sin fuente' for d in deals_mes)

        # --- Ventas del mes: deals con Fecha_Matriculado en el mes (Universidad Insurgentes) ---
        ventas_mes = sum(
            1 for d in deals_data
            if (d.get('Fecha_Matriculado') or '')[:10] != ''
            and month_start <= (d.get('Fecha_Matriculado') or '')[:10] <= month_end
            and (d.get('Instituci_n') or '').lower() in ('universidad insurgentes', '')
        )

        # --- Leads del mes (para asesor breakdown) ---
        leads_mes = [l for l in leads_data
                     if month_start <= (l.get('Created_Time') or '')[:10] <= month_end]

        def _owner_name(obj):
            o = obj.get('Owner') or {}
            if isinstance(o, dict):
                return o.get('name') or o.get('Name') or 'Sin asignar'
            return str(o) or 'Sin asignar'

        # Asesor: leads del mes por estado
        asesor_leads = defaultdict(lambda: {'leads': 0, 'estados': Counter()})
        for l in leads_mes:
            nm = _owner_name(l)
            asesor_leads[nm]['leads'] += 1
            asesor_leads[nm]['estados'][l.get('Lead_Status') or 'Sin gestión'] += 1

        # Asesor: deals del mes (opps creadas en el mes)
        asesor_opps = defaultdict(int)
        for d in deals_mes:
            asesor_opps[_owner_name(d)] += 1

        # Asesor: ventas del mes (Fecha_Matriculado en el mes, Universidad Insurgentes)
        asesor_ventas = defaultdict(int)
        for d in deals_data:
            fm = (d.get('Fecha_Matriculado') or '')[:10]
            if fm and month_start <= fm <= month_end:
                asesor_ventas[_owner_name(d)] += 1

        all_names = set(list(asesor_leads.keys()) + list(asesor_opps.keys()) + list(asesor_ventas.keys()))
        # Agrupar estados de leads en categorías
        def _cat_estado(estado):
            e = (estado or '').lower()
            if 'sin gestión' in e or 'sin gestion' in e: return 'sin_gestion'
            if 'intento' in e: return 'intentos'
            if 'duplicado' in e or 'ya existe' in e: return 'duplicado'
            if 'inválido' in e or 'invalido' in e or 'errón' in e: return 'invalido'
            if 'no contactable' in e: return 'no_contactable'
            if 'múltiple' in e or 'multiple' in e: return 'multiple_interes'
            return 'otros'

        asesores = []
        for nm in sorted(all_names):
            li = asesor_leads.get(nm, {'leads': 0, 'estados': Counter()})
            total_leads = li['leads']
            opps = asesor_opps.get(nm, 0)
            ventas = asesor_ventas.get(nm, 0)
            cats = defaultdict(int)
            for estado, cnt in li['estados'].items():
                cats[_cat_estado(estado)] += cnt
            asesores.append({
                'nombre': nm,
                'leads': total_leads,
                'opps': opps,
                'ventas': ventas,
                'conv_pct': round(ventas / total_leads * 100, 1) if total_leads else 0,
                'sin_gestion': cats['sin_gestion'],
                'intentos': cats['intentos'],
                'duplicado': cats['duplicado'],
                'invalido': cats['invalido'],
                'no_contactable': cats['no_contactable'],
                'multiple_interes': cats['multiple_interes'],
            })
        asesores.sort(key=lambda x: -(x['leads'] + x['opps']))

        total_deals = len(deals_data)
        return {
            'leads_total':      sum(leads_por_estado.values()),
            'leads_por_estado': dict(leads_por_estado.most_common()),
            'leads_por_fuente': dict(leads_por_fuente.most_common(6)),
            'deals_total':      total_deals,
            'stages_raw':       dict(stages.most_common()),
            'funnel':           funnel,
            'mql_mes':          mql_mes,
            'ventas_mes':       ventas_mes,
            'top_programas':    dict(programas.most_common(6)),
            'asesores':         asesores,
        }
    except Exception as e:
        print(f'Zoho funnel error: {e}')
        return None

def zoho_crm_funnel_ebds():
    """Funnel EBDS CRM — datacenter EU, pipeline propio."""
    from collections import Counter
    try:
        leads_data = zoho_get('Leads', {
            'per_page': 200,
            'fields': 'Lead_Status,Lead_Source,Created_Time'
        }, client='ebds').get('data', [])
        leads_por_estado = Counter(l.get('Lead_Status') or 'Sin gestión' for l in leads_data)
        leads_por_fuente = Counter(l.get('Lead_Source') or 'Sin fuente'  for l in leads_data)

        deals_data = zoho_get('Deals', {
            'per_page': 200,
            'fields': 'Stage,Programa_Academico,Programa_largo,Lead_Source,Created_Time'
        }, client='ebds').get('data', [])

        INSCRITO_STAGES  = {'inscrito / pendiente de otorgar accesos', 'estudiante', 'inscrito'}
        PERDIDO_STAGES   = {'no interesado', 'perdido', 'no interesado/perdido'}

        stages   = Counter(d.get('Stage') or 'Sin etapa' for d in deals_data)
        programas = Counter()
        for d in deals_data:
            if (d.get('Stage') or '').lower() in PERDIDO_STAGES:
                continue
            prog = d.get('Programa_largo') or ''
            if not prog:
                prog_obj = d.get('Programa_Academico')
                if isinstance(prog_obj, dict):
                    prog = prog_obj.get('name', '')
            if prog:
                programas[prog] += 1

        funnel = {
            'leads_sin_contactar': sum(leads_por_estado.values()),
            'contactados': 0, 'interesados': 0, 'evaluando': 0,
            'promesa_pago': 0, 'estudiantes': 0, 'perdidos': 0,
        }
        for stage, count in stages.items():
            sl = stage.lower()
            if 'contactado'  in sl: funnel['contactados']  += count
            elif 'interesado' in sl: funnel['interesados']  += count
            elif 'evaluando'  in sl: funnel['evaluando']    += count
            elif 'promesa'    in sl: funnel['promesa_pago'] += count
            elif any(s in sl for s in INSCRITO_STAGES): funnel['estudiantes'] += count
            elif any(s in sl for s in PERDIDO_STAGES):  funnel['perdidos']    += count

        return {
            'leads_total':      funnel['leads_sin_contactar'],
            'leads_por_estado': dict(leads_por_estado.most_common()),
            'leads_por_fuente': dict(leads_por_fuente.most_common(6)),
            'deals_total':      len(deals_data),
            'funnel':           funnel,
            'stages_raw':       dict(stages.most_common()),
            'top_programas':    dict(programas.most_common(6)),
        }
    except Exception as e:
        print(f'Zoho EBDS funnel error: {e}')
        return None

def web_search(query):
    """DuckDuckGo Instant Answers — no API key needed"""
    try:
        params = urllib.parse.urlencode({'q': query, 'format': 'json', 'no_html': '1', 'skip_disambig': '1'})
        req = urllib.request.Request(
            f'https://api.duckduckgo.com/?{params}',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        parts = []
        if data.get('Abstract'):
            parts.append(data['Abstract'])
        for t in data.get('RelatedTopics', [])[:5]:
            if isinstance(t, dict) and t.get('Text'):
                parts.append(t['Text'])
        return ' | '.join(parts)[:2500] if parts else ''
    except Exception as e:
        print(f'DDG error: {e}')
        return ''

def meta_ads_library(competitor, country='AR'):
    """Busca anuncios activos de un competidor en Meta Ads Library"""
    try:
        params = urllib.parse.urlencode({
            'search_terms': competitor,
            'ad_reached_countries': country,
            'ad_type': 'ALL',
            'fields': 'ad_creative_bodies,page_name,ad_creative_link_titles,ad_creative_link_descriptions,ad_delivery_start_time,impressions',
            'limit': '8',
            'access_token': META_TOKEN
        })
        data = http_req(f'https://graph.facebook.com/v21.0/ads_archive?{params}')
        return data.get('data', [])
    except Exception as e:
        print(f'Ads Library error: {e}')
        return []

def claude(prompt, system=None, max_tokens=1024):
    data = {
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': prompt}]
    }
    if system:
        data['system'] = system
    h = {'Content-Type': 'application/json', 'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2023-06-01'}
    body = json.dumps(data).encode()
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=body, headers=h, method='POST')
    with urllib.request.urlopen(req, timeout=90) as r:
        result = json.loads(r.read())
    return result['content'][0]['text']

# --- State ---
STATE_DEFAULTS = {
    'last_offset': 0,
    'notified_validar_tasks': [],
    'active_conversation': None,
    'pending_approvals': [],
    'last_post_ids': {},
}

# Tareas dedicadas al calendario — una por marca para mantener payloads pequeños (~20KB c/u)
# Nunca se tocan desde crons/webhook
CALENDAR_TASK_ID        = '86ahv938h'   # tarea legacy / fallback
CALENDAR_BACKUP_TASK_ID = '86ahva45t'   # backup de la tarea legacy
CALENDAR_BRAND_TASKS = {
    'EBDS':    '86ahvcnc2',
    'Sibila':  '86ahvcnd9',
    'ZoWeAre': '86ahvcneg',
    'Tivenos': '86ahvcp1w',
    'BHU':     '86ahvcpcx',
}
BRANDS_CONFIG_TASK_ID = '86ahyrq9c'   # config dinámica de marcas [NO BORRAR]

# Config inicial de marcas hardcodeada como fallback — se migra a ClickUp en primera carga
_BRANDS_DEFAULT = {
    'EBDS':    {'color':'#1e3a8a','task_id':'86ahvcnc2'},
    'Sibila':  {'color':'#7c3aed','task_id':'86ahvcnd9'},
    'ZoWeAre': {'color':'#059669','task_id':'86ahvcneg'},
    'Tivenos': {'color':'#dc2626','task_id':'86ahvcp1w'},
    'BHU':     {'color':'#d97706','task_id':'86ahvcpcx'},
}

def _decode_task_desc(desc):
    """Decodifica base64 o JSON plano desde el campo description de una tarea ClickUp."""
    if not desc or not desc.strip():
        return {}
    try:
        return json.loads(base64.b64decode(desc.strip().encode()).decode('utf-8'))
    except Exception:
        try:
            return json.loads(desc)
        except Exception:
            return {}

def _encode_for_clickup(data):
    """Serializa dict a base64 para guardar en ClickUp."""
    return base64.b64encode(json.dumps(data, ensure_ascii=False).encode('utf-8')).decode('ascii')

def read_state():
    """Lee SOLO el estado del bot (last_offset, validar, etc.).
    El calendario está en CALENDAR_TASK_ID — nunca se mezcla aquí."""
    loaded = {}
    try:
        task = cu_get(f'task/{STATE_TASK_ID}')
        loaded = _decode_task_desc(task.get('description', '') or '')
    except Exception:
        pass
    state = dict(STATE_DEFAULTS)
    # Nunca importar 'calendar' en el estado del bot
    state.update({k: v for k, v in loaded.items() if k != 'calendar'})
    return state

def save_state(state):
    """Guarda SOLO el estado del bot en ClickUp. Nunca incluye el calendario."""
    state.pop('calendar', None)          # garantía extra: nunca entra el calendario
    state['last_run'] = datetime.utcnow().isoformat() + 'Z'
    cu_put(f'task/{STATE_TASK_ID}', {'markdown_description': _encode_for_clickup(state)})

def _brand_task(brand):
    """Devuelve el task_id de ClickUp para una marca.
    Marcas hardcodeadas → dict en memoria. Marcas creadas dinámicamente → config en ClickUp
    (necesario porque en un cold start de Vercel CALENDAR_BRAND_TASKS no las tiene).
    Fallback final: tarea legacy."""
    if brand in CALENDAR_BRAND_TASKS:
        return CALENDAR_BRAND_TASKS[brand]
    try:
        cfg = get_brands_config()
        task_id = cfg.get(brand, {}).get('task_id')
        if task_id:
            CALENDAR_BRAND_TASKS[brand] = task_id  # cachear para el resto de esta invocación
            return task_id
    except Exception as e:
        print(f'_brand_task config lookup {brand}: {e}')
    return CALENDAR_TASK_ID

def read_calendar_brand(brand, month_str=None):
    """Lee los posts de UNA marca desde su tarea dedicada. Rápido (~15KB por marca)."""
    try:
        task = cu_get(f'task/{_brand_task(brand)}')
        data = _decode_task_desc(task.get('description', '') or '')
        if month_str:
            return data.get(month_str, [])
        return data   # {month_str: [posts]}
    except Exception:
        return {} if month_str is None else []

def save_calendar_brand(brand, month_str, posts):
    """Escribe los posts de UNA marca en su tarea dedicada.
    Payload pequeño (~15KB) → rápido y sin timeouts."""
    task_id = _brand_task(brand)
    # Leer el estado actual de esa marca para no perder otros meses
    try:
        task = cu_get(f'task/{task_id}')
        current = _decode_task_desc(task.get('description', '') or '')
    except Exception:
        current = {}
    current[month_str] = posts
    # Mantener máximo 3 meses por marca
    months = sorted(current.keys())
    if len(months) > 3:
        for old in months[:-3]:
            del current[old]
    cu_put(f'task/{task_id}', {'markdown_description': _encode_for_clickup(current)})

def read_calendar():
    """Lee el calendario completo (todas las marcas) para /calendar/data.
    Hace una llamada por marca — se usa solo en carga de página."""
    result = {}
    for brand in get_all_brand_tasks():
        try:
            data = read_calendar_brand(brand)
            result[brand] = data   # {month_str: [posts]}
        except Exception:
            pass
    return result

def save_calendar(calendar_data, backup=False):
    """Compatibilidad con replace-brand: calendar_data = {month_str: {brand: [posts]}}.
    Distribuye cada marca a su tarea dedicada."""
    for month_str, month_brands in calendar_data.items():
        if not isinstance(month_brands, dict):
            continue
        for brand, posts in month_brands.items():
            try:
                save_calendar_brand(brand, month_str, posts)
            except Exception as e:
                print(f'save_calendar brand={brand}: {e}')

# --- Brands config (dinámico) ---
def read_brands_config():
    """Lee la config de marcas desde ClickUp. Fallback a _BRANDS_DEFAULT."""
    try:
        task = cu_get(f'task/{BRANDS_CONFIG_TASK_ID}')
        data = _decode_task_desc(task.get('description', '') or '')
        if data:
            return data
    except Exception as e:
        print(f'read_brands_config: {e}')
    return dict(_BRANDS_DEFAULT)

def save_brands_config(config):
    """Guarda la config de marcas en ClickUp."""
    cu_put(f'task/{BRANDS_CONFIG_TASK_ID}', {'markdown_description': _encode_for_clickup(config)})

def get_brands_config():
    """Lee config, si está vacía migra desde defaults y guarda."""
    cfg = read_brands_config()
    if not cfg:
        cfg = dict(_BRANDS_DEFAULT)
        save_brands_config(cfg)
    return cfg

def get_all_brand_tasks():
    """Devuelve {brand: task_id} combinando las marcas hardcodeadas con las creadas
    dinámicamente desde la UI (guardadas en ClickUp vía save_brands_config).
    Usar esto — no CALENDAR_BRAND_TASKS directo — en cualquier lugar que necesite
    iterar TODAS las marcas, porque CALENDAR_BRAND_TASKS no sobrevive un cold start."""
    tasks = dict(CALENDAR_BRAND_TASKS)
    try:
        cfg = get_brands_config()
        for name, info in cfg.items():
            if info.get('task_id'):
                tasks[name] = info['task_id']
    except Exception as e:
        print(f'get_all_brand_tasks: {e}')
    return tasks

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
    if re.match(r'^correcciones .+:.+', t, re.DOTALL):
        return 'correct_validar'
    # Aprobación de tarea validar — formato "ok [nombre]" o lenguaje natural
    notified = state.get('notified_validar_tasks', [])
    if notified:
        if re.match(r'^ok .+', t):
            return 'approve_validar'
        if any(w in t for w in ['aprobado', 'aprobá', 'aprobar', 'pásala a done', 'pasá a done', 'mandala a done', 'marcar como done', 'está ok', 'dale con']):
            return 'approve_validar'
        # Si el nombre de alguna tarea notificada aparece en el mensaje
        for task in notified:
            if isinstance(task, dict):
                name = task.get('name', '').lower()
                if name and name in t:
                    return 'approve_validar'
    # Calendario tiene prioridad sobre campaigns (el texto puede contener nombre de cliente)
    if any(w in t for w in ['calendario', 'armame el contenido', 'armá el contenido', 'generar contenido del mes',
                             'planificar mes', 'contenido de', 'contenido orgánico', 'contenido organico',
                             'armame el calendario', 'armá el calendario', 'genera el contenido', 'generá el contenido',
                             'generame contenido', 'genérame contenido', 'parrilla de contenido',
                             'posteos de', 'posts de', 'redes sociales de', 'genera contenido']):
        return 'calendar'
    if any(w in t for w in ['rehaceme', 'rehace', 'rehacer', 'regenera', 'regenerame', 'otra versión', 'otra version', 'nueva versión', 'nueva version', 'volvé a generar', 'vuelve a generar', 'cambiá el post', 'cambia el post', 'no me gusta']):
        return 'regen_post'
    if any(w in t for w in ['crear campaña', 'nueva campaña', 'draft en meta', 'armame una campaña', 'armá una campaña', 'campaña para', 'quiero una campaña', 'lanzar campaña']):
        return 'draft_meta'
    if any(w in t for w in ['reporte semanal', 'reporte paid', 'reporte mensual', 'genera el reporte',
                             'generá el reporte', 'dame el reporte', 'reporte html', 'reporte de paid',
                             'reporte bhu', 'reporte ebds', 'reporte uin']):
        return 'paid_report'
    if any(w in t for w in ['crm', 'leads del crm', 'pipeline', 'inscriptos', 'inscripciones', 'conversiones crm', 'cuántos leads', 'estado de leads']):
        return 'crm_report'
    # detect_client solo dispara campaigns si hay palabras de Meta/performance; si no, puede ser otra intención
    meta_words = ['campaña', 'campañas', 'performance', 'resultados', 'leads', 'gastaron', 'profundiza', 'cómo están', 'meta ads', 'inversión', 'gasto', 'cpl', 'ctr', 'roas']
    if any(w in t for w in meta_words) or (detect_client(t) and any(w in t for w in meta_words + ['cómo va', 'anuncios', 'pauta', 'paid'])):
        return 'campaigns'
    if any(w in t for w in ['tarea', 'gráfica', 'diseño', 'stefania', 'anuncio', 'pieza', 'necesito crear']):
        return 'create_task'
    if any(w in t for w in ['proyección', 'proyectame', 'cuánto necesito', 'forecast', 'estimación']):
        return 'projection'
    if any(w in t for w in ['evaluación de marca', 'salud de marca', 'cómo está la marca', 'análisis de marca', 'evaluar marca', 'evaluá la marca']):
        return 'brand_eval'
    if any(w in t for w in ['competencia', 'competidores', 'benchmark', 'competidor']):
        return 'research'
    if any(w in t for w in ['copy', 'copies', 'redactame', 'escribime', 'variantes', 'texto para']):
        return 'copies'
    if any(w in t for w in ['tendencias', 'novedades', 'qué hay de nuevo', 'actualización']):
        return 'trends'
    return 'unknown'

# --- Handlers ---
def h_crm_report(text, state):
    """Reporte del CRM — BHU (zoho.com) o EBDS (zoho.eu)."""
    t = text.lower()
    is_ebds = 'ebds' in t
    client_name = 'EBDS' if is_ebds else 'BHU/UIN'
    meta_account = 'act_2249213495344845'

    tg_send(f'📊 Consultando CRM de {client_name}...')
    funnel = zoho_crm_funnel_ebds() if is_ebds else zoho_crm_funnel()
    if not funnel:
        tg_send('❌ No pude conectar con el CRM. Verificá las credenciales.')
        return state

    want_pdf = any(w in t for w in ['pdf', 'reporte', 'archivo', 'documento', 'informe', 'exporta'])

    # Siempre traer Meta Ads para cruzar con CRM
    meta_data = []
    try:
        url = (f'https://graph.facebook.com/v21.0/act_2249213495344845/insights'
               f'?fields=campaign_name,adset_name,spend,impressions,clicks,ctr,actions,cost_per_action_type'
               f'&date_preset=last_30d&level=adset&limit=100&access_token={META_TOKEN}')
        all_data = http_req(url).get('data', [])
        # Filtrar por cliente: EBDS → solo campañas con "EBDS" en el nombre; BHU → excluir "EBDS"
        if is_ebds:
            meta_data = [c for c in all_data if 'ebds' in c.get('campaign_name', '').lower()]
        else:
            meta_data = [c for c in all_data if 'ebds' not in c.get('campaign_name', '').lower()]
    except Exception as e:
        print(f'Meta for CRM cross: {e}')

    f = funnel['funnel']
    total_en_pipeline = f['contactados'] + f['interesados'] + f['evaluando'] + f['promesa_pago'] + f['estudiantes']
    conv_rate = round(f['estudiantes'] / total_en_pipeline * 100, 1) if total_en_pipeline else 0

    _meta_ads_section = ('META ADS — conjuntos activos últimos 30d (nivel adset):\n' + json.dumps([{"adset": c.get("adset_name",""), "campaign": c.get("campaign_name",""), "spend": c.get("spend",0), "leads": sum(int(a.get("value",0)) for a in (c.get("actions") or []) if a.get("action_type") == "onsite_conversion.lead_grouped"), "ctr": c.get("ctr",0)} for c in meta_data[:15]], ensure_ascii=False)) if meta_data else 'Meta Ads: sin datos'

    prompt = f"""Generá un reporte de CRM para {client_name} en español neutro para Telegram (Markdown).

FUNNEL COMPLETO:
- Leads sin contactar (Leads module): {f['leads_sin_contactar']}
- 1. Contactados (Deals): {f['contactados']}
- 2. Interesados: {f['interesados']}
- 3. Evaluando: {f['evaluando']}
- 4. Promesa de pago: {f['promesa_pago']}
- Inscriptos/Estudiantes (convertidos): {f['estudiantes']}
- Perdidos/No interesados: {f['perdidos']}
- Tasa de conversión (contactado → inscripto): {conv_rate}%

TOP PROGRAMAS (en pipeline activo):
{json.dumps(funnel['top_programas'], ensure_ascii=False)}

FUENTES DE LEADS:
{json.dumps(funnel['leads_por_fuente'], ensure_ascii=False)}

{_meta_ads_section}

Formato para Telegram con Markdown:
📊 *{client_name} — CRM + Meta Ads*

**Funnel CRM:**
[cada etapa con número y % sobre deals activos, flecha → entre etapas]

**Meta Ads — por campaña y conjunto:**
[agrupar por campaña; dentro de cada campaña listar sus conjuntos de anuncios con nombre, gasto, leads y CPL — el nombre del conjunto suele indicar el programa o audiencia]

**Top programas en pipeline:**
[los 4-5 más demandados]

**Fuentes de leads:**
[de dónde vienen]

**Cruce Meta → CRM:**
[leads generados en Meta vs contactados en CRM, calidad del tráfico, cuello de botella]

**Alertas:**
[1-2 acciones concretas]

Máximo 450 palabras."""

    if want_pdf:
        tg_send('📄 Generando PDF...')
        try:
            filepath = generate_paid_media_pdf(client_name, meta_data, funnel)
            fname = f'Reporte_{client_name.replace("/","_")}_CRM_{dt.date.today()}.pdf'
            tg_send_document(filepath, fname, caption=f'📊 Reporte BHU/UIN — CRM + Paid Media | {dt.date.today().strftime("%d/%m/%Y")}', mimetype='application/pdf')
        except Exception as e:
            print(f'PDF crm error: {e}')
            tg_send(f'❌ Error generando PDF: {str(e)[:80]}')
        return state

    tg_send(claude(prompt, max_tokens=700))
    return state

def h_campaigns(text, state):
    client   = detect_client(text)
    t        = text.lower()
    is_deep  = any(w in t for w in ['profundiza', 'detalle', 'ad set', 'conjunto'])
    want_pdf = any(w in t for w in ['pdf', 'reporte', 'archivo', 'documento', 'informe', 'exporta'])

    if not client:
        tg_send('¿Para qué cliente?\n\n• BHU/UIN\n• EBDS\n• Goya\n• Somostec')
        return state

    if 'meta' not in client:
        tg_send(f'❌ {client["name"]} no tiene Meta Ads disponible.')
        return state

    # BHU/UIN siempre a nivel adset para ver programas; comparte cuenta con EBDS → filtrar
    is_bhu = client['name'] in ('BHU/UIN', 'BHU')
    level = 'adset' if (is_deep or is_bhu) else 'campaign'
    url = (f'https://graph.facebook.com/v21.0/{client["meta"]}/insights'
           f'?fields=campaign_name,adset_name,spend,impressions,clicks,ctr,cpm,cpc,reach,actions,cost_per_action_type'
           f'&date_preset=last_30d&level={level}&limit=50&access_token={META_TOKEN}')
    data = http_req(url)
    campaigns = data.get('data', [])

    # Para BHU/UIN: filtrar adsets cuya campaña NO es de EBDS (comparten misma ad account)
    if is_bhu and campaigns:
        campaigns = [
            c for c in campaigns
            if 'ebds' not in c.get('campaign_name', '').lower()
        ]

    if not campaigns:
        tg_send(f'No hay datos de campañas para {client["name"]} en los últimos 30 días.')
        return state

    # Enriquecer con CRM según cliente
    crm_funnel = None
    if client['name'] in ('BHU/UIN', 'BHU') and ZOHO_REFRESH_TOKEN:
        try: crm_funnel = zoho_crm_funnel()
        except Exception: pass
    elif client['name'] == 'EBDS' and ZOHO_EBDS_REFRESH_TOKEN:
        try: crm_funnel = zoho_crm_funnel_ebds()
        except Exception: pass

    crm_section = ''
    if crm_funnel:
        f = crm_funnel['funnel']
        total_pipeline = f['contactados'] + f['interesados'] + f['evaluando'] + f['promesa_pago'] + f['estudiantes']
        conv = round(f['estudiantes'] / total_pipeline * 100, 1) if total_pipeline else 0
        crm_section = f"""

CRM BHU/UIN — funnel actual:
- Leads sin contactar: {f['leads_sin_contactar']}
- Contactados: {f['contactados']} | Interesados: {f['interesados']} | Evaluando: {f['evaluando']}
- Promesa de pago: {f['promesa_pago']} | Estudiantes convertidos: {f['estudiantes']}
- Tasa conversión: {conv}% | Perdidos: {f['perdidos']}
- Top programas: {json.dumps(crm_funnel['top_programas'], ensure_ascii=False)}"""

    if want_pdf:
        tg_send(f'📄 Generando PDF de {client["name"]}...')
        try:
            filepath = generate_paid_media_pdf(client['name'], campaigns, crm_funnel, level=level)
            fname = f'Reporte_PaidMedia_{client["name"].replace("/","_")}_{dt.date.today()}.pdf'
            tg_send_document(filepath, fname, caption=f'📊 Reporte Paid Media — {client["name"]} | {dt.date.today().strftime("%d/%m/%Y")}', mimetype='application/pdf')
        except Exception as e:
            print(f'PDF campaigns error: {e}')
            tg_send(f'❌ Error generando PDF: {str(e)[:80]}')
        return state

    prompt = f"""Análisis de Meta Ads + CRM para {client['name']} (últimos 30 días).

Meta Ads {level}: {json.dumps(campaigns[:10], ensure_ascii=False)}
{crm_section}

Reporte para Telegram en español neutro con Markdown:
📊 *{client['name']} — Meta Ads + CRM*

**Meta Ads:**
- Gasto total, leads generados, CPL, CTR por campaña
- Alertas (CPL alto, CTR bajo, sin conversiones)

{'**CRM Pipeline:** Funnel leads → contactado → interesado → evaluando → promesa → estudiante. Conversion final, cuello de botella, cruce leads Meta vs CRM.' if crm_funnel else ''}

**Recomendaciones:** 2-3 acciones concretas

Máximo 420 palabras."""

    tg_send(claude(prompt, max_tokens=750))
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
    state['active_conversation'] = {'topic': 'campana_completa', 'step': 'cliente', 'data': {}}
    tg_send('💼 *Crear campaña en Meta Ads*\n\n¿Para qué cliente?\n\n• BHU/UIN\n• EBDS\n• Somostec\n• Pediapartner')
    return state

def h_draft_meta_step(text, state, conv):
    step = conv['step']
    data = conv['data']

    if step == 'cliente':
        t = text.lower()
        client_data = next((v for k, v in CAMPAIGN_CLIENTS.items() if k in t), None)
        if not client_data:
            tg_send('No reconocí el cliente. ¿Es BHU/UIN, EBDS, Somostec o Pediapartner?')
            return state
        data['client'] = client_data
        conv['step'] = 'objetivo'
        tg_send('¿Cuál es el objetivo?\n\n• Leads (captar contactos)\n• Tráfico (visitas al sitio)\n• Awareness (reconocimiento de marca)\n• Ventas (conversiones)')

    elif step == 'objetivo':
        data['objetivo_raw'] = text
        t = text.lower()
        if 'lead' in t:
            data['objetivo_api'] = 'OUTCOME_LEADS';   data['optim_goal'] = 'LEAD_GENERATION'; data['cta_type'] = 'SIGN_UP'
        elif any(w in t for w in ['tráfico', 'trafico', 'visita', 'clic', 'click']):
            data['objetivo_api'] = 'OUTCOME_TRAFFIC';  data['optim_goal'] = 'LINK_CLICKS';      data['cta_type'] = 'LEARN_MORE'
        elif any(w in t for w in ['aware', 'reconoc', 'marca', 'alcance']):
            data['objetivo_api'] = 'OUTCOME_AWARENESS'; data['optim_goal'] = 'REACH';           data['cta_type'] = 'LEARN_MORE'
        else:
            data['objetivo_api'] = 'OUTCOME_SALES';   data['optim_goal'] = 'OFFSITE_CONVERSIONS'; data['cta_type'] = 'SHOP_NOW'
        conv['step'] = 'nombre'
        tg_send('¿Cuál es el nombre de la campaña?')

    elif step == 'nombre':
        data['nombre'] = text
        conv['step'] = 'presupuesto'
        tg_send('¿Cuál es el presupuesto diario en USD?')

    elif step == 'presupuesto':
        m = re.search(r'[\d.]+', text)
        data['presupuesto'] = float(m.group()) if m else 10.0
        conv['step'] = 'pais_edad'
        tg_send('¿País y rango de edad?\n_(ej: "Argentina, 25-45")_')

    elif step == 'pais_edad':
        t = text.lower()
        country = next((code for name, code in COUNTRY_CODES.items() if name in t), 'AR')
        age_m = re.search(r'(\d{2})\s*[-–]\s*(\d{2})', text)
        data['country']  = country
        data['age_min']  = int(age_m.group(1)) if age_m else 18
        data['age_max']  = int(age_m.group(2)) if age_m else 65
        conv['step'] = 'url_destino'
        tg_send('¿Cuál es la URL de destino? (landing page o sitio web)')

    elif step == 'url_destino':
        data['url_destino'] = text.strip()
        conv['step'] = 'imagen'
        tg_send('¿Link de la imagen?')

    elif step == 'imagen':
        data['imagen'] = text.strip()
        # Generate copy with Claude
        prompt = f"""Copy para Meta Ads.
Cliente: {data['client']['name']}
Objetivo: {data.get('objetivo_raw', '')}
URL destino: {data['url_destino']}
Devolvé SOLO JSON: {{"headline": "titular impactante (máx 40 chars)", "body": "texto principal persuasivo (2-3 oraciones en español)", "description": "texto secundario corto (máx 25 chars)"}}"""
        copy_data = {}
        try:
            r = claude(prompt)
            m = re.search(r'\{.*\}', r, re.DOTALL)
            if m: copy_data = json.loads(m.group())
        except Exception: pass
        data['copy'] = copy_data or {'headline': f'Conocé {data["client"]["name"]}', 'body': f'Descubrí todo lo que {data["client"]["name"]} tiene para vos.', 'description': 'Más información'}

        cop = data['copy']
        msg = (f'📋 *Resumen de campaña*\n\n'
               f'🏢 Cliente: {data["client"]["name"]}\n'
               f'🎯 Objetivo: {data["objetivo_raw"]}\n'
               f'📛 Nombre: {data["nombre"]}\n'
               f'💰 Presupuesto: ${data["presupuesto"]}/día\n'
               f'🌎 País: {data["country"]} | Edad: {data["age_min"]}-{data["age_max"]}\n'
               f'🔗 URL: {data["url_destino"]}\n'
               f'🖼️ Imagen: _{data["imagen"][:50]}..._\n\n'
               f'✍️ *Copy generado:*\n'
               f'• Headline: _{cop.get("headline", "")}_\n'
               f'• Texto: _{cop.get("body", "")}_\n'
               f'• Descripción: _{cop.get("description", "")}_\n\n'
               f'⏸️ Todo se creará *PAUSADO* en Meta Ads.\n\n'
               f'¿Creo la campaña completa?\n_("ok" para crear | "cambios: [desc]" para ajustar copy)_')
        tg_send(msg)
        state['pending_approvals'] = [{'type': 'campana_completa', 'data': data}]
        state['active_conversation'] = None
        return state

    state['active_conversation'] = conv
    return state

def h_continue(text, state):
    conv = state.get('active_conversation', {})
    topic = conv.get('topic')
    if topic == 'crear_tarea':
        return h_create_task_step(text, state, conv)
    elif topic == 'proyeccion':
        return h_projection_step(text, state, conv)
    elif topic in ('draft_meta', 'campana_completa'):
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
        if approval['type'] == 'campana_completa':
            cop = data.get('copy', {})
            prompt = f"""Ajustá este copy de Meta Ads según las correcciones:
Headline actual: {cop.get('headline', '')}
Texto actual: {cop.get('body', '')}
Descripción actual: {cop.get('description', '')}
Correcciones: {changes}
Devolvé SOLO JSON: {{"headline": "...", "body": "...", "description": "..."}}"""
            try:
                result = claude(prompt)
                m = re.search(r'\{.*\}', result, re.DOTALL)
                if m: data['copy'] = json.loads(m.group())
            except Exception: pass
            cop = data['copy']
            tg_send(f'📋 *Copy actualizado:*\n\n• Headline: _{cop.get("headline", "")}_\n• Texto: _{cop.get("body", "")}_\n• Descripción: _{cop.get("description", "")}_\n\n_("ok" para crear)_')
        else:
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
            except Exception: pass
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

    elif approval['type'] == 'campana_completa':
        data = approval['data']
        client = data['client']
        account = client['account']
        page_id = client['page']
        budget_cents = int(data['presupuesto'] * 100)
        cop = data['copy']
        try:
            tg_send('⏳ Creando campaña en Meta Ads...')
            # 1. Campaign
            camp = http_req(f'https://graph.facebook.com/v21.0/{account}/campaigns', 'POST', {
                'name': data['nombre'], 'objective': data['objetivo_api'],
                'status': 'PAUSED', 'special_ad_categories': [], 'access_token': META_TOKEN
            })
            campaign_id = camp.get('id')
            # 2. Ad Set
            adset = http_req(f'https://graph.facebook.com/v21.0/{account}/adsets', 'POST', {
                'name': f'{data["nombre"]} — Ad Set',
                'campaign_id': campaign_id,
                'daily_budget': budget_cents,
                'bid_strategy': 'LOWEST_COST_WITHOUT_CAP',
                'optimization_goal': data['optim_goal'],
                'billing_event': 'IMPRESSIONS',
                'targeting': {
                    'geo_locations': {'countries': [data['country']]},
                    'age_min': data['age_min'], 'age_max': data['age_max']
                },
                'status': 'PAUSED', 'access_token': META_TOKEN
            })
            adset_id = adset.get('id')
            # 3. Creative
            creative = http_req(f'https://graph.facebook.com/v21.0/{account}/adcreatives', 'POST', {
                'name': f'{data["nombre"]} — Creative',
                'object_story_spec': {
                    'page_id': page_id,
                    'link_data': {
                        'image_url': data['imagen'],
                        'message': cop.get('body', ''),
                        'link': data['url_destino'],
                        'name': cop.get('headline', ''),
                        'description': cop.get('description', ''),
                        'call_to_action': {'type': data.get('cta_type', 'LEARN_MORE'), 'value': {'link': data['url_destino']}}
                    }
                },
                'access_token': META_TOKEN
            })
            creative_id = creative.get('id')
            # 4. Ad
            ad = http_req(f'https://graph.facebook.com/v21.0/{account}/ads', 'POST', {
                'name': f'{data["nombre"]} — Ad',
                'adset_id': adset_id,
                'creative': {'creative_id': creative_id},
                'status': 'PAUSED', 'access_token': META_TOKEN
            })
            ad_id = ad.get('id')
            tg_send(
                f'✅ *Campaña creada en Meta Ads*\n\n'
                f'🏢 {client["name"]} — {data["nombre"]}\n\n'
                f'🆔 Campaign: `{campaign_id}`\n'
                f'🆔 Ad Set: `{adset_id}`\n'
                f'🆔 Creative: `{creative_id}`\n'
                f'🆔 Ad: `{ad_id}`\n\n'
                f'⏸️ Todo en estado PAUSADO.\n'
                f'Activá desde Meta Ads cuando el creativo esté listo.'
            )
        except Exception as e:
            tg_send(f'❌ Error al crear campaña: {str(e)[:200]}')

    state['pending_approvals'] = []
    state['active_conversation'] = None
    return state

def h_approve_validar(text, state):
    t_lower = text.lower()
    notified = state.get('notified_validar_tasks', [])
    task = None

    # 1. Formato exacto: "ok [nombre tarea]"
    if t_lower.startswith('ok '):
        search = re.sub(r'^ok\s+', '', text, flags=re.IGNORECASE).strip().lower()
        task = next((t for t in notified if isinstance(t, dict) and search in t.get('name', '').lower()), None)

    # 2. Nombre de la tarea aparece en el mensaje
    if not task:
        for t in notified:
            if isinstance(t, dict):
                name = t.get('name', '').lower()
                if name and name in t_lower:
                    task = t
                    break

    # 3. Solo hay una tarea pendiente → aprobarla directamente
    if not task and len([t for t in notified if isinstance(t, dict)]) == 1:
        task = next(t for t in notified if isinstance(t, dict))

    if not task:
        pending = '\n'.join(f'• {t["name"]}' for t in notified if isinstance(t, dict))
        tg_send(f'No identifiqué qué tarea aprobar. Pendientes:\n{pending or "Ninguna"}')
        return state

    try:
        cu_put(f'task/{task["task_id"]}', {'status': task.get('done_status', 'done')})
        tg_send(f'✅ *{task["name"]}* marcada como {task.get("done_status", "done")}.')
        state['notified_validar_tasks'] = [t for t in notified if t.get('task_id') != task['task_id']]
    except Exception as e:
        tg_send(f'❌ Error: {str(e)}')
    return state

def h_correct_validar(text, state):
    match = re.match(r'correcciones\s+(.+?):\s*(.+)', text, re.IGNORECASE | re.DOTALL)
    if not match:
        tg_send('Formato: correcciones NOMBRE DE TAREA: descripcion de los cambios')
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
    client = detect_client(text)
    client_name = client['name'] if client else 'Sin especificar'

    # Extract formato y medio from text, defaults to standard
    t = text.lower()
    if 'story' in t or 'historia' in t:
        formatos = 'Story'
    elif 'reel' in t:
        formatos = 'Reel'
    elif 'carrusel' in t:
        formatos = 'Carrusel'
    else:
        formatos = 'Feed/Story/network/reel'
    medio = 'FB/IG'

    prompt = f"""Copies para Meta Ads. Solicitud: "{text}"
Cliente: {client_name}

Generá 3 variantes de copy (ángulos: beneficio, dolor/problema, curiosidad/pregunta).
El copy de cada opción debe ser completo y listo para usar: headline + cuerpo + CTA, todo junto en un texto corrido.

Devolvé SOLO JSON válido:
{{
  "tematica": "tema o producto específico mencionado (ej: Máster en IA Aplicada)",
  "prompt_contexto": "1-2 frases del insight/ángulo general que guía los copies",
  "opcion1": "Headline: ...\\nCuerpo: ...\\nCTA: ...",
  "opcion2": "Headline: ...\\nCuerpo: ...\\nCTA: ...",
  "opcion3": "Headline: ...\\nCuerpo: ...\\nCTA: ..."
}}"""

    copies_data = None
    try:
        result = claude(prompt)
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            copies_data = json.loads(match.group())
    except Exception:
        pass

    if not copies_data:
        tg_send(claude(f'Generá 3 copies para Meta Ads en español: "{text}". Incluí headline, cuerpo y CTA para cada variante.'))
        return state

    tematica = copies_data.get('tematica', text[:60])
    contexto = copies_data.get('prompt_contexto', '')
    op1 = copies_data.get('opcion1', '')
    op2 = copies_data.get('opcion2', '')
    op3 = copies_data.get('opcion3', '')

    # Telegram text
    tg_send(
        f'✍️ *Copies — {client_name} · {tematica}*\n\n'
        f'*Opción 1:*\n{op1}\n\n'
        f'*Opción 2:*\n{op2}\n\n'
        f'*Opción 3:*\n{op3}\n\n'
        f'¿Usás alguna tal cual o querés ajustes?'
    )

    # CSV con las columnas exactas de la planilla de Stefania
    try:
        fecha = datetime.utcnow().strftime('%d/%m/%Y')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False,
                                         encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Fecha pedido', 'Diseñado', 'Formatos', 'Medio',
                'Institución', 'Temática', 'Parte de algunos prompt',
                'Opción 1', 'Opción 2', 'Opción 3'
            ])
            writer.writerow([
                fecha, '', formatos, medio,
                client_name, tematica, contexto,
                op1, op2, op3
            ])
            tmppath = f.name
        tg_send_document(tmppath, f'copies_{client_name.lower().replace("/","_")}_{datetime.utcnow().strftime("%Y%m%d")}.csv',
                         '📎 Listo para pegar en la planilla de Stefania')
        os.unlink(tmppath)
    except Exception as e:
        print(f'CSV error: {e}')

    return state

def h_research(text, state):
    # Extraer nombre del competidor del texto
    t = text.lower()
    # Remover palabras clave de activación para quedarnos con el tema
    competitor_raw = re.sub(r'\b(competencia|competidores|benchmark|analiza|investigá|research)\b', '', text, flags=re.IGNORECASE).strip()
    competitor = competitor_raw[:60] if competitor_raw else text[:60]

    tg_send('🔍 Buscando info... un segundo.')

    # 1. Meta Ads Library — anuncios reales del competidor
    ads = meta_ads_library(competitor)
    ads_context = ''
    if ads:
        ads_context = f'\n\nAnuncios reales encontrados en Meta Ads Library ({len(ads)}):\n'
        for ad in ads[:5]:
            page = ad.get('page_name', '')
            bodies = ad.get('ad_creative_bodies', [])
            titles = ad.get('ad_creative_link_titles', [])
            body_text = bodies[0] if bodies else ''
            title_text = titles[0] if titles else ''
            ads_context += f'- Página: {page} | Título: {title_text} | Copy: {body_text[:150]}\n'

    # 2. DuckDuckGo para contexto adicional
    web_ctx = web_search(f'{competitor} publicidad digital marketing estrategia')

    prompt = f"""Research de competencia. Solicitud original: "{text}"
Competidor/sector analizado: {competitor}
{ads_context}
Contexto web adicional: {web_ctx[:1000] if web_ctx else 'No disponible'}

Con esta información real (priorizar los datos de Meta Ads Library si están disponibles), generá un análisis accionable en español con Markdown para Telegram (máx 320 palabras):

🔍 *Research: {competitor}*

🏢 *Posicionamiento y mensaje central:* [basado en los ads reales si los hay]

📢 *Lo que están comunicando en sus anuncios:*
• [mensaje/ángulo real con ejemplo de copy]
• [mensaje/ángulo real con ejemplo de copy]
• [mensaje/ángulo real con ejemplo de copy]

💡 *Formatos y creatividades:* [qué están usando]

🎯 *Gaps — dónde se puede superar:*
• [oportunidad concreta]
• [oportunidad concreta]

¿Querés que arme ángulos específicos para alguno de tus clientes vs este competidor?"""

    tg_send(claude(prompt))
    return state

def h_trends(text, state):
    now = datetime.now()
    tg_send('📡 Buscando tendencias actuales...')

    # DuckDuckGo para contexto web reciente
    web_ctx = web_search(f'Meta Ads tendencias publicidad digital {now.strftime("%Y")}')
    web_ctx2 = web_search(f'Facebook Ads algorithm changes {now.strftime("%B %Y")}')

    prompt = f"""Tendencias de publicidad digital. Solicitud: "{text}"
Fecha actual: {now.strftime("%B %Y")}.

Contexto web reciente:
{(web_ctx + ' | ' + web_ctx2)[:2000] if (web_ctx or web_ctx2) else 'No disponible'}

Sos experta en Meta Ads y Google Ads. Usando el contexto web anterior Y tu conocimiento, compartí las tendencias más relevantes con impacto práctico real. Sé específica — mencioná formatos, cambios de algoritmo, tipos de campaña, estrategias concretas.

Respondé en español con Markdown para Telegram (máx 320 palabras):

📡 *Tendencias — {now.strftime("%B %Y")}*

1️⃣ *[tendencia específica]:* [qué está pasando + qué hacer]
2️⃣ *[tendencia específica]:* [qué está pasando + qué hacer]
3️⃣ *[tendencia específica]:* [qué está pasando + qué hacer]
4️⃣ *[tendencia específica]:* [qué está pasando + qué hacer]

⚡ *Acción rápida para esta semana:* [algo concreto y aplicable hoy]

¿Querés aplicar alguna a un cliente específico?"""

    tg_send(claude(prompt))
    return state

def h_brand_eval(text, state):
    client = detect_client(text)
    if not client:
        tg_send('¿Para qué cliente querés la evaluación de marca?\n\n• BHU/UIN\n• EBDS\n• Goya\n• Somostec\n• Pediapartner')
        return state
    if 'meta' not in client:
        tg_send(f'❌ {client["name"]} no tiene Meta Ads configurado.')
        return state

    tg_send(f'📊 Analizando {client["name"]}... un momento.')

    try:
        # 90 días con desglose mensual
        url_90 = (f'https://graph.facebook.com/v21.0/{client["meta"]}/insights'
                  f'?fields=spend,reach,impressions,clicks,ctr,cpc,cpm,frequency'
                  f'&date_preset=last_90d&level=account&time_increment=monthly'
                  f'&access_token={META_TOKEN}')
        data_90 = http_req(url_90).get('data', [])

        # Últimos 7 días para comparar con el mes anterior
        url_7 = (f'https://graph.facebook.com/v21.0/{client["meta"]}/insights'
                 f'?fields=spend,reach,impressions,clicks,ctr,cpc,cpm'
                 f'&date_preset=last_7d&level=account'
                 f'&access_token={META_TOKEN}')
        data_7 = http_req(url_7).get('data', [{}])

        prompt = f"""Evaluación de salud de marca en Meta Ads para {client['name']}.

Datos últimos 90 días (por mes): {json.dumps(data_90)}
Datos últimos 7 días: {json.dumps(data_7)}

Analizá la evolución de la marca. Identificá tendencias positivas y negativas. Comparar contra benchmarks: CTR bueno ≥1.5%, CPC eficiente, frecuencia ideal 1.5–3.0, CPM razonable para Argentina.

Respondé en español con Markdown para Telegram (máx 380 palabras):

🏷️ *Evaluación de marca — {client['name']}*
_Últimos 90 días · Meta Ads_

📈 *Evolución mensual:* [describe la tendencia — está creciendo, estancada, cayendo?]

✅ *Fortalezas detectadas:*
• [métrica buena con dato concreto]
• [métrica buena con dato concreto]

⚠️ *Alertas:*
• [problema con dato concreto + por qué importa]
• [problema con dato concreto + por qué importa]

🎯 *3 acciones prioritarias:*
1. [acción específica + impacto esperado]
2. [acción específica + impacto esperado]
3. [acción específica + impacto esperado]

¿Querés que profundice en alguna campaña específica?"""

        tg_send(claude(prompt, system='Sos una estratega de performance marketing con 10 años de experiencia en Meta Ads para el mercado latinoamericano.'))
    except Exception as e:
        tg_send(f'❌ Error al obtener datos: {str(e)}')

    return state

SOFIA_CLICKUP_EMAIL = 'sofia.colombo@tivenos.com'

# --- Social accounts ---
SOCIAL_ACCOUNTS = [
    {'client': 'Behind-U',  'fb': '329482500949627',  'ig': '17841409037631007', 'li': '33294267'},
    {'client': 'EBDS',      'fb': '102439669276120',  'ig': '17841455358314149', 'li': '81972160'},
    {'client': 'Sibila',    'fb': '100075997488468',  'ig': '50607705062',       'li': '77605671'},
    {'client': 'ZoWeAre',   'fb': '933257013195402',  'ig': '17841479150682279', 'li': '110340230'},
    {'client': 'Tivenos',   'fb': '100077396560752',   'ig': '52254063803',       'li': '9256248'},
]

# ─── CONTENT CALENDAR ───────────────────────────────────────────────
CALENDAR_BRANDS = ['EBDS', 'Sibila', 'ZoWeAre', 'Tivenos', 'BHU']

BRAND_CONTEXT = {
    'EBDS': """European Business & Digital School (EBDS). Formación profesional online: Diplomados (6 meses) y Másteres (12 meses) con diploma y certificado propio apostillado por la Convención de La Haya.

TERMINOLOGÍA OBLIGATORIA: SIEMPRE usar "Diplomado", "Máster", "certificado" o "diploma". NUNCA escribir "titulación" ni "título" — es diploma propio, no título universitario oficial.

PROGRAMAS REALES (úsalos exactamente así, no inventes otros):
Diplomado y Máster: Marketing, Transformación Digital, Data Analytics, Prevención y Gestión de Riesgos Laborales, Recursos Humanos, Administración de Empresas, Mindfulness, Programación / Diseño Web y Gestión IT, Customer Success, Contabilidad y Finanzas.
Solo Diplomado: Habilidades Gerenciales.
Solo Máster: Marketing Digital, Inteligencia Artificial, IA Generativa y Marketing Digital.

DIFERENCIADORES: certificación europea apostillada (Convención de La Haya), tutores que acompañan activamente (2-4 contactos/mes), 100% online y a tu ritmo, contenido aplicable desde el módulo 1, evaluaciones continuas (nota mínima 7/10), precio accesible con becas disponibles, inicio los días martes.

AUDIENCIA: profesionales activos 25-45 años de Latinoamérica y España que quieren crecer sin pausar su vida laboral.

TONO: aspiracional, empoderador, educativo, profesional. Español neutro — nunca voseo. Habla siempre del beneficio para el estudiante, no de la institución. Frases cortas, directas, con flechas → para beneficios, 1-2 emojis por bloque.

PILARES DE CONTENIDO: programas y especialidades reales, beneficios del estudio online flexible, tips profesionales por área (marketing, datos, RRHH, etc.), diferenciadores vs universidad tradicional, motivación y crecimiento profesional, el sistema de microcredenciales (se puede empezar con 4 semanas a USD 119).

HASHTAGS: #EBDS #FormaciónOnline #DesarrolloProfesional #CertificaciónEuropea #EstudiaOnline #EducaciónOnline
Web: ebds.online""",
    'Sibila': """Sibila: plataforma omnicanal de comunicación empresarial con IA (WhatsApp Business, Email, SMS, chatbots y más, desde una sola interfaz). Audiencia: gerentes y responsables de atención al cliente en empresas medianas/grandes que quieren modernizar cómo se comunican con sus clientes y mejorar tiempos de respuesta. Tono: innovador, confiable, tecnológico pero cercano. Pilares: funcionalidades de la plataforma, casos de uso reales, ROI/eficiencia operativa, integraciones con otros sistemas, atención omnicanal con IA.
Estilo de copies: enfocado en el problema del cliente (comunicación dispersa, lentitud), luego la solución (Sibila centraliza todo), siempre con dato o beneficio concreto. Emojis moderados. CTA al link de la bio. Hashtags: #Sibila #AtenciónAlCliente #Omnicanal #IA #Chatbot #CX
Web: sibila.app""",
    'ZoWeAre': """ZoWeAre: empresa de transformación digital, Advanced Partner certificado de Zoho. Implementan CRM, ERP, automatización de procesos y soluciones a medida con la suite Zoho. Audiencia: dueños y directores de empresas medianas que quieren digitalizar sus operaciones, dejar de usar hojas de cálculo y tener visibilidad total del negocio. Tono: experto pero accesible, orientado a resultados, práctico.
Pilares: casos de éxito con resultados medibles, herramientas Zoho (CRM, Books, Projects, Marketing Hub), metodología de implementación, ROI digital, problemas comunes que resuelven.
Estilo de copies: antes/después o problema/solución, datos concretos de ahorro de tiempo o aumento de ventas, CTA a consulta gratuita. Hashtags: #ZoWeAre #Zoho #TransformaciónDigital #CRM #AutomatizaciónDeProcesos #ERP
Web: zoweare.com""",
    'Tivenos': """Tivenos: empresa de tecnología y transformación digital. Desarrollo de software a medida, consultoría tech e integración de sistemas. Audiencia: empresas que necesitan soluciones tecnológicas hechas a su medida porque los productos genéricos no les alcanzan. Tono: profesional, innovador, confiable, orientado a resultados.
Pilares: proyectos de desarrollo a medida, consultoría tecnológica, integración de sistemas, metodología ágil, casos de éxito con impacto en el negocio.
Estilo de copies: enfocado en el problema técnico del cliente y cómo Tivenos lo resuelve con precisión, sin tecnicismos innecesarios. CTA a conversación inicial. Hashtags: #Tivenos #DesarrolloSoftware #TechConsulting #TransformaciónDigital #SoftwareAMedida
Web: tivenos.com""",
    'BHU': """Behind-U / UIN: institución educativa con programas online de grado y posgrado. Audiencia: jóvenes y adultos que buscan formación universitaria flexible, accesible desde cualquier lugar. Tono: motivacional, cercano, inclusivo, esperanzador. Pilares: programas disponibles, modalidad 100% online, acompañamiento personalizado, historias de alumnos que lograron sus metas, precio accesible, titulación válida.
Estilo de copies: emotivo y directo, habla de sueños y oportunidades, celebra el logro de estudiar siendo adulto o con vida laboral. CTA a inscribirse o conocer programas. Hashtags: #BehindU #UIN #EducaciónOnline #FormaciónProfesional #EstudiaOnline
Web: behind-u.net""",
}

CALENDAR_BRAND_COLORS = {
    'EBDS': '#1e3a8a', 'Sibila': '#7c3aed', 'ZoWeAre': '#059669',
    'Tivenos': '#dc2626', 'BHU': '#d97706',
}
CALENDAR_TYPE_COLORS = {
    'Reel': '#16a34a', 'Carrusel': '#9333ea', 'Post': '#2563eb', 'Story': '#db2777',
    'LinkedIn': '#0284c7', 'Blog': '#ea580c', 'Email': '#dc2626',
}

# Rotation pattern: each row = one posting day, each column = brand index
# Rules: max 1 Reel/day, max 1 Carrusel/day
CALENDAR_FORMAT_ROTATION = [
    ['Carrusel', 'Post',     'Post',     'Reel',     'Post'],
    ['Reel',     'Post',     'Carrusel', 'Post',     'Post'],
    ['Post',     'Carrusel', 'Reel',     'Post',     'Post'],
    ['Post',     'Reel',     'Post',     'Carrusel', 'Post'],
    ['Carrusel', 'Post',     'Post',     'Reel',     'Post'],
    ['Reel',     'Post',     'Carrusel', 'Post',     'Post'],
    ['Post',     'Carrusel', 'Reel',     'Post',     'Post'],
    ['Post',     'Post',     'Reel',     'Post',     'Carrusel'],
    ['Reel',     'Carrusel', 'Post',     'Post',     'Post'],
    ['Post',     'Post',     'Post',     'Carrusel', 'Reel'],
    ['Carrusel', 'Reel',     'Post',     'Post',     'Post'],
    ['Post',     'Post',     'Carrusel', 'Reel',     'Post'],
    ['Reel',     'Post',     'Post',     'Post',     'Carrusel'],
]

def check_validar(state):
    if dt.date.today().weekday() >= 5:  # sábado=5, domingo=6
        return state
    seen = notified_ids(state)
    for ws_id, ws_info in WORKSPACES.items():
        try:
            result = cu_get(f'team/{ws_id}/task?statuses[]=validar&subtasks=true')
            for task in result.get('tasks', []):
                task_id = task.get('id')
                if task_id in seen:
                    continue
                # Notificar todas las tareas en validar (sin filtro de assignee)
                # — son tareas de diseño de Stefania que Sofia debe revisar
                comments = cu_get(f'task/{task_id}/comment').get('comments', [])
                last_comment = comments[-1].get('comment_text', '') if comments else ''
                task_desc = task.get('description', '') or ''
                # Buscar link WorkDrive/Zoho en comentarios y descripción
                search_text = last_comment + ' ' + task_desc
                wd_match = re.search(r'https?://\S*(?:workdrive|zohoexternal|zoho)\S+', search_text)
                if not wd_match:
                    # También buscar en todos los comentarios
                    all_comments_text = ' '.join(c.get('comment_text','') for c in comments)
                    wd_match = re.search(r'https?://\S*(?:workdrive|zohoexternal|zoho)\S+', all_comments_text)
                wd_link = wd_match.group() if wd_match else 'No hay link de archivos'
                task_name = task.get('name', '')
                tg_send(
                    f'🔔 *Nueva tarea para revisar*\n\n'
                    f'📋 Tarea: {task_name}\n'
                    f'🏢 Cliente: {ws_info["name"]}\n'
                    f'💬 Comentario: "{last_comment[:200] or "Sin comentarios"}"\n'
                    f'🔗 ClickUp: {task.get("url", "")}\n'
                    f'📂 Archivos: {wd_link}\n\n'
                    f'Responde *ok {task_name}* para aprobar\n'
                    f'o *correcciones {task_name}: tu descripcion* para pedir cambios'
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
        'brand_eval':    h_brand_eval,
        'calendar':      h_calendar,
        'regen_post':    h_regen_post,
        'crm_report':    h_crm_report,
        'paid_report':   h_paid_report,
    }
    if intent in handlers:
        return handlers[intent](text, state)
    tg_send('No entendí bien. ¿Qué necesitás?\n\n1️⃣ Análisis de campañas\n2️⃣ Crear tarea para Stefania\n3️⃣ Proyección de campaña\n4️⃣ Research de competencia\n5️⃣ Redactar copies\n6️⃣ Tendencias Meta/Google\n7️⃣ Crear draft en Meta Ads\n8️⃣ Evaluación de marca')
    return state

# ─────────────────────────────────────────────
# SEO / AEO MONTHLY REPORT
# ─────────────────────────────────────────────
GOOGLE_CLIENT_ID     = '75867073584-qof2qcdtmcppgookbkft3qvp8gp4vnq6.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = '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'
GOOGLE_REFRESH_TOKEN = '1//0hRZcfML6JUGyCgYIARAAGBESNwF-L9IrnL5pqeyZCiUwUi68SMdFT3OvFCyzH9N8G-WEnQCSfFRBfhb3rV3S_b-QC--pW2ohw3Q'

SEO_CLIENTS = [
    {'name': 'EBDS',    'url': 'https://ebds.online',  'sc_url': 'sc-domain:ebds.online',  'ga4': '426749533'},
    {'name': 'Sibila',  'url': 'https://sibila.app',   'sc_url': 'sc-domain:sibila.app',   'ga4': '426775519'},
    {'name': 'Tivenos', 'url': 'https://tivenos.com',  'sc_url': 'sc-domain:tivenos.com',  'ga4': '438322787'},
    {'name': 'BehindU', 'url': 'https://behind-u.net', 'sc_url': 'sc-domain:behind-u.net', 'ga4': '420486833'},
    {'name': 'ZoWeAre',      'url': 'https://zoweare.com',      'sc_url': None,                          'ga4': '521287190'},
    {'name': 'Pediapartner', 'url': 'https://pediapartner.com', 'sc_url': None,                          'ga4': '456852321'},
]

def is_first_business_day():
    today = dt.date.today()
    day = today.replace(day=1)
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    return day == today

def get_google_token():
    data = urllib.parse.urlencode({
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'refresh_token': GOOGLE_REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    return resp.get('access_token')

def sc_query(token, site_url, start, end, dimensions=None, row_limit=15):
    encoded = urllib.parse.quote(site_url, safe='')
    url = f'https://www.googleapis.com/webmasters/v3/sites/{encoded}/searchAnalytics/query'
    body = {'startDate': start, 'endDate': end, 'rowLimit': row_limit}
    if dimensions:
        body['dimensions'] = dimensions
    req = urllib.request.Request(url,
        data=json.dumps(body).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=12).read())

def get_sc_data(token, site_url):
    today = dt.date.today()
    e1 = today.replace(day=1) - dt.timedelta(days=1)
    s1 = e1.replace(day=1)
    e2 = s1 - dt.timedelta(days=1)
    s2 = e2.replace(day=1)
    month_label = s1.strftime('%B %Y')

    def safe(fn):
        try: return fn()
        except: return {}

    overall_cur  = safe(lambda: sc_query(token, site_url, s1.isoformat(), e1.isoformat()))
    overall_prev = safe(lambda: sc_query(token, site_url, s2.isoformat(), e2.isoformat()))
    keywords     = safe(lambda: sc_query(token, site_url, s1.isoformat(), e1.isoformat(), ['query'], 15))
    pages        = safe(lambda: sc_query(token, site_url, s1.isoformat(), e1.isoformat(), ['page'], 10))
    opps_raw     = safe(lambda: sc_query(token, site_url, s1.isoformat(), e1.isoformat(), ['query'], 200))

    def row0(r): return r.get('rows', [{}])[0] if r.get('rows') else {}
    cur  = row0(overall_cur)
    prev = row0(overall_prev)

    def delta(a, b, key):
        av, bv = a.get(key, 0), b.get(key, 0)
        if bv: return f'{((av-bv)/bv*100):+.0f}%'
        return 'N/A'

    opp_rows = [r for r in opps_raw.get('rows', [])
                if r.get('impressions', 0) > 50 and r.get('ctr', 1) < 0.03 and r.get('position', 99) < 20]
    opp_rows.sort(key=lambda x: -x.get('impressions', 0))

    return {
        'month': month_label,
        'clicks':      cur.get('clicks', 0),
        'impressions': cur.get('impressions', 0),
        'ctr':         cur.get('ctr', 0) * 100,
        'position':    cur.get('position', 0),
        'd_clicks':    delta(cur, prev, 'clicks'),
        'd_impressions': delta(cur, prev, 'impressions'),
        'd_ctr':       delta(cur, prev, 'ctr'),
        'd_position':  delta(cur, prev, 'position'),
        'keywords':    keywords.get('rows', [])[:10],
        'pages':       pages.get('rows', [])[:10],
        'opps':        opp_rows[:5],
    }

def get_ga4_data(token, property_id):
    today = dt.date.today()
    e1 = today.replace(day=1) - dt.timedelta(days=1)
    s1 = e1.replace(day=1)
    e2 = s1 - dt.timedelta(days=1)
    s2 = e2.replace(day=1)

    url = f'https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport'
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    def ga4_req(body):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        return json.loads(urllib.request.urlopen(req, timeout=12).read())

    def val(resp, metric_idx=0, row_idx=0):
        try:
            return float(resp['rows'][row_idx]['metricValues'][metric_idx]['value'])
        except: return 0.0

    def delta(a, b):
        return f'{((a-b)/b*100):+.0f}%' if b else 'N/A'

    # Métricas globales mes anterior vs mes anterior anterior
    body_cur = {
        'dateRanges': [{'startDate': s1.isoformat(), 'endDate': e1.isoformat()}],
        'metrics': [
            {'name': 'sessions'}, {'name': 'totalUsers'},
            {'name': 'engagementRate'}, {'name': 'averageSessionDuration'},
            {'name': 'conversions'}
        ]
    }
    body_prev = {
        'dateRanges': [{'startDate': s2.isoformat(), 'endDate': e2.isoformat()}],
        'metrics': [{'name': 'sessions'}, {'name': 'totalUsers'}]
    }
    # Canales de tráfico
    body_channels = {
        'dateRanges': [{'startDate': s1.isoformat(), 'endDate': e1.isoformat()}],
        'dimensions': [{'name': 'sessionDefaultChannelGroup'}],
        'metrics': [{'name': 'sessions'}],
        'orderBys': [{'metric': {'metricName': 'sessions'}, 'desc': True}],
        'limit': 6
    }

    try: r_cur = ga4_req(body_cur)
    except: r_cur = {}
    try: r_prev = ga4_req(body_prev)
    except: r_prev = {}
    try: r_ch = ga4_req(body_channels)
    except: r_ch = {}

    sessions_cur  = val(r_cur, 0)
    users_cur     = val(r_cur, 1)
    eng_rate      = val(r_cur, 2) * 100
    avg_duration  = val(r_cur, 3)
    conversions   = val(r_cur, 4)
    sessions_prev = val(r_prev, 0)
    users_prev    = val(r_prev, 1)

    channels = []
    for row in r_ch.get('rows', []):
        ch_name = row['dimensionValues'][0]['value']
        ch_sess = float(row['metricValues'][0]['value'])
        channels.append((ch_name, int(ch_sess)))

    mins = int(avg_duration // 60)
    secs = int(avg_duration % 60)

    return {
        'month':        s1.strftime('%B %Y'),
        'sessions':     int(sessions_cur),
        'users':        int(users_cur),
        'eng_rate':     eng_rate,
        'avg_duration': f'{mins}m {secs}s',
        'conversions':  int(conversions),
        'd_sessions':   delta(sessions_cur, sessions_prev),
        'd_users':      delta(users_cur, users_prev),
        'channels':     channels,
    }

def get_pagespeed(url):
    api = (f'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'
           f'?url={urllib.parse.quote(url, safe="")}&strategy=mobile'
           f'&category=performance&category=seo')
    data = json.loads(urllib.request.urlopen(api, timeout=20).read())
    cats   = data.get('lighthouseResult', {}).get('categories', {})
    audits = data.get('lighthouseResult', {}).get('audits', {})
    perf = int(cats.get('performance', {}).get('score', 0) * 100)
    seo  = int(cats.get('seo',         {}).get('score', 0) * 100)
    lcp  = audits.get('largest-contentful-paint', {}).get('displayValue', 'N/A')
    cls_ = audits.get('cumulative-layout-shift',  {}).get('displayValue', 'N/A')
    tbt  = audits.get('total-blocking-time',       {}).get('displayValue', 'N/A')
    fcp  = audits.get('first-contentful-paint',    {}).get('displayValue', 'N/A')
    opps = [(a.get('title', ''), a.get('details', {}).get('overallSavingsMs', 0))
            for a in audits.values()
            if a.get('score') is not None and a.get('score', 1) < 0.9 and a.get('title')]
    opps.sort(key=lambda x: -x[1])
    return {'perf': perf, 'seo': seo, 'lcp': lcp, 'cls': cls_, 'tbt': tbt, 'fcp': fcp,
            'opps': [o[0] for o in opps[:3]]}

def crawl_seo(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; SEOBot/1.0)'})
    html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')

    def rx(pattern, default='AUSENTE'):
        m = re.search(pattern, html, re.I | re.S)
        return m.group(1).strip() if m else default

    title = rx(r'<title[^>]*>(.*?)</title>')
    desc  = rx(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)')
    if desc == 'AUSENTE':
        desc = rx(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']description')
    h1s   = [re.sub(r'<[^>]+>', '', h).strip() for h in re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.I|re.S)]
    h2s   = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.I|re.S)
    can   = rx(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)')
    ld    = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I|re.S)
    schemas = []
    for s in ld:
        m = re.search(r'"@type"\s*:\s*"([^"]+)"', s)
        if m: schemas.append(m.group(1))
    og_t  = rx(r'property=["\']og:title["\'][^>]+content=["\']([^"\']*)')
    og_i  = bool(re.search(r'property=["\']og:image["\']', html, re.I))
    all_h = [re.sub(r'<[^>]+>', '', h).strip() for h in re.findall(r'<h[2-4][^>]*>(.*?)</h[2-4]>', html, re.I|re.S)]
    q_h   = [h for h in all_h if '?' in h]

    def head_ok(path):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url.rstrip('/')+path, method='HEAD'), timeout=5)
            return r.status < 400
        except: return False

    return {
        'title': title, 'title_len': len(title),
        'desc': desc,   'desc_len': len(desc),
        'h1s': h1s, 'h2_count': len(h2s),
        'canonical': can,
        'schemas': schemas,
        'has_faq': 'FAQPage' in schemas,
        'has_howto': 'HowTo' in schemas,
        'og_title': og_t, 'og_image': og_i,
        'q_headings': len(q_h),
        'sitemap': head_ok('/sitemap.xml'),
        'robots': head_ok('/robots.txt'),
    }

def sem(value, good, ok):
    return '🟢' if value <= good else ('🟡' if value <= ok else '🔴')

def sem_score(s):
    return '🟢' if s >= 90 else ('🟡' if s >= 50 else '🔴')

def build_seo_report(client_name, ps, tech, sc, ga4=None):
    # --- Performance section ---
    lcp_num = float(re.sub(r'[^\d.]', '', ps['lcp']) or 9) if ps else 9
    cls_num = float(re.sub(r'[^\d.]', '', ps['cls']) or 9) if ps else 9
    tbt_num = float(re.sub(r'[^\d.]', '', ps['tbt']) or 999) if ps else 999

    perf_block = ''
    if ps:
        perf_block = (
            f"\n⚡ *PERFORMANCE (mobile)*\n"
            f"• Score: {ps['perf']}/100 {sem_score(ps['perf'])}\n"
            f"• LCP: {ps['lcp']} {sem(lcp_num, 2.5, 4.0)}\n"
            f"• CLS: {ps['cls']} {sem(cls_num, 0.1, 0.25)}\n"
            f"• TBT: {ps['tbt']} {sem(tbt_num, 200, 600)}\n"
            f"• FCP: {ps['fcp']}\n"
            f"• SEO Lighthouse: {ps['seo']}/100\n"
        )

    # --- Technical section ---
    t_title  = '🟢' if 50 <= tech['title_len'] <= 60 else '🟡'
    t_desc   = '🟢' if 140 <= tech['desc_len'] <= 165 else ('🔴' if tech['desc'] == 'AUSENTE' else '🟡')
    t_h1     = '🟢' if len(tech['h1s']) == 1 else '🔴'
    schemas_str = ', '.join(tech['schemas']) if tech['schemas'] else 'Ninguno'
    aeo_score = 'Rico' if len(tech['schemas']) >= 3 else ('Básico' if tech['schemas'] else 'Vacío')

    tech_block = (
        f"\n🔍 *SEO TÉCNICO*\n"
        f"• Title: _{tech['title'][:50]}_ ({tech['title_len']} chars) {t_title}\n"
        f"• Meta desc: {tech['desc_len']} chars {t_desc}\n"
        f"• H1: {len(tech['h1s'])} {t_h1}"
        + (f" — _{tech['h1s'][0][:40]}_" if tech['h1s'] else '') + "\n"
        f"• H2s: {tech['h2_count']} | Canonical: {'✅' if tech['canonical'] != 'AUSENTE' else '❌'}\n"
        f"• Schema.org: {schemas_str}\n"
        f"• Sitemap: {'✅' if tech['sitemap'] else '❌'} | Robots: {'✅' if tech['robots'] else '❌'}\n"
        f"• OG tags: {'OK' if tech['og_image'] else 'Sin imagen'}\n"
        f"\n🤖 *AEO — Optimización para IA*\n"
        f"• FAQ schema: {'✅' if tech['has_faq'] else '❌'}\n"
        f"• HowTo schema: {'✅' if tech['has_howto'] else '❌'}\n"
        f"• Encabezados-pregunta: {tech['q_headings']}\n"
        f"• Structured data: {aeo_score}\n"
    )

    # --- Search Console section ---
    sc_block = ''
    if sc:
        kw_lines = '\n'.join(
            f"  `{r['keys'][0][:35]}` {r['clicks']:.0f} clics · pos {r['position']:.1f}"
            for r in sc['keywords'][:5]
        ) or '  Sin datos'
        opp_lines = '\n'.join(
            f"  `{r['keys'][0][:35]}` {r['impressions']:.0f} impr · CTR {r['ctr']*100:.1f}% · pos {r['position']:.1f}"
            for r in sc['opps'][:3]
        ) or '  Sin oportunidades detectadas'
        sc_block = (
            f"\n📈 *SEARCH CONSOLE — {sc['month']}*\n"
            f"• Clics: {sc['clicks']:.0f} ({sc['d_clicks']})\n"
            f"• Impresiones: {sc['impressions']:.0f} ({sc['d_impressions']})\n"
            f"• CTR: {sc['ctr']:.1f}% ({sc['d_ctr']})\n"
            f"• Posición media: {sc['position']:.1f} ({sc['d_position']})\n"
            f"\n🔑 *Top keywords:*\n{kw_lines}\n"
            f"\n💡 *Oportunidades (alta impr, bajo CTR):*\n{opp_lines}\n"
        )
    else:
        sc_block = "\n📈 *SEARCH CONSOLE*\n_Sin Search Console configurado_\n"

    # --- GA4 section ---
    ga4_block = ''
    if ga4:
        ch_lines = '\n'.join(f"  • {ch}: {n:,} sesiones" for ch, n in ga4['channels'][:5]) or '  Sin datos'
        eng_icon = '🟢' if ga4['eng_rate'] >= 60 else ('🟡' if ga4['eng_rate'] >= 40 else '🔴')
        ga4_block = (
            f"\n📊 *ANALYTICS — {ga4['month']}*\n"
            f"• Sesiones: {ga4['sessions']:,} ({ga4['d_sessions']})\n"
            f"• Usuarios: {ga4['users']:,} ({ga4['d_users']})\n"
            f"• Engagement rate: {ga4['eng_rate']:.1f}% {eng_icon}\n"
            f"• Duración media: {ga4['avg_duration']}\n"
            + (f"• Conversiones: {ga4['conversions']:,}\n" if ga4['conversions'] else '')
            + f"\n🌐 *Canales de tráfico:*\n{ch_lines}\n"
        )

    # --- Acciones with Claude ---
    prompt = f"""Sos experta en SEO y AEO. Generá 5 acciones prioritarias ordenadas por impacto para {client_name}.

Datos disponibles:
- Performance mobile: score {ps['perf'] if ps else 'N/A'}, LCP {ps['lcp'] if ps else 'N/A'}, TBT {ps['tbt'] if ps else 'N/A'}
- Title: {tech['title_len']} chars {'(OK)' if 50 <= tech['title_len'] <= 60 else '(fuera de rango)'}
- Meta desc: {tech['desc_len']} chars {'(OK)' if 140 <= tech['desc_len'] <= 165 else '(fuera de rango)'}
- H1: {len(tech['h1s'])} {'(OK)' if len(tech['h1s']) == 1 else '(problema)'}
- Schemas: {tech['schemas'] or 'ninguno'}
- FAQ schema: {'sí' if tech['has_faq'] else 'NO'}
- Sitemap: {'OK' if tech['sitemap'] else 'NO EXISTE'}
{'- Clics SC: ' + str(int(sc['clicks'])) + ' (' + sc['d_clicks'] + ')' if sc else ''}
{'- Sesiones GA4: ' + str(ga4['sessions']) + ' (' + ga4['d_sessions'] + '), eng: ' + str(round(ga4['eng_rate'])) + '%' if ga4 else ''}
{'- Oportunidades top: ' + (sc['opps'][0]['keys'][0] if sc and sc['opps'] else 'ninguna') if sc else ''}

Devolvé SOLO JSON: {{"acciones": ["[ALTO] acción concreta 1", "[ALTO] acción concreta 2", "[MEDIO] acción 3", "[MEDIO] acción 4", "[BAJO] acción 5"]}}
Cada acción: específica, máx 80 chars, en español, sin genéricos."""

    acciones = ['Error al generar acciones'] * 5
    try:
        r = claude(prompt)
        m = re.search(r'\{.*\}', r, re.DOTALL)
        if m:
            acciones = json.loads(m.group()).get('acciones', acciones)
    except Exception:
        pass

    actions_block = "\n🎯 *5 ACCIONES PRIORITARIAS*\n" + '\n'.join(f"{i+1}. {a}" for i, a in enumerate(acciones[:5]))

    header = f"📊 *REPORTE SEO/AEO — {client_name}*\n📅 {dt.date.today().strftime('%d/%m/%Y')} | 🌐 {client_name.lower()}"
    return header + ga4_block + sc_block + perf_block + tech_block + actions_block

def generate_paid_media_pdf(client_name, meta_campaigns, crm_funnel=None, level='campaign'):
    """PDF de reporte paid media + CRM. Estilo dashboard: portada, KPIs, funnel, campañas."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    C_DARK   = (15, 23, 42)    # slate-900
    C_BLUE   = (37, 99, 235)   # blue-600
    C_LIGHT  = (241, 245, 249) # slate-100
    C_WHITE  = (255, 255, 255)
    C_GRAY   = (100, 116, 139) # slate-500
    C_GREEN  = (22, 163, 74)   # green-600
    C_ORANGE = (234, 88, 12)   # orange-600
    C_RED    = (220, 38, 38)   # red-600

    def safe(s):
        return str(s or '').encode('latin-1', 'replace').decode('latin-1')

    def row(pdf, h, txt, bold=False, color=None, size=10):
        pdf.set_font('Helvetica', 'B' if bold else '', size)
        if color:
            pdf.set_text_color(*color)
        pdf.multi_cell(0, h, safe(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def section_header(pdf, title):
        pdf.ln(4)
        pdf.set_fill_color(*C_BLUE)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 8, f'  {safe(title)}', fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*C_DARK)
        pdf.ln(2)

    def kpi_card(pdf, x, y, w, label, value, sub='', color=C_BLUE):
        pdf.set_fill_color(*C_LIGHT)
        pdf.rect(x, y, w, 22, 'F')
        pdf.set_fill_color(*color)
        pdf.rect(x, y, 3, 22, 'F')
        pdf.set_xy(x + 5, y + 3)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(*color)
        pdf.cell(w - 8, 7, safe(str(value)))
        pdf.set_xy(x + 5, y + 11)
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(*C_GRAY)
        pdf.cell(w - 8, 5, safe(label))
        if sub:
            pdf.set_xy(x + 5, y + 16)
            pdf.set_font('Helvetica', '', 7)
            pdf.cell(w - 8, 5, safe(sub))

    def funnel_bar(pdf, label, value, total, color=C_BLUE):
        pct = (value / total * 100) if total else 0
        bar_w = 90
        fill_w = max(2, bar_w * pct / 100)
        y = pdf.get_y()
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(*C_DARK)
        pdf.cell(55, 7, safe(label))
        pdf.set_fill_color(*C_LIGHT)
        pdf.rect(pdf.get_x(), y + 1, bar_w, 5, 'F')
        pdf.set_fill_color(*color)
        pdf.rect(pdf.get_x(), y + 1, fill_w, 5, 'F')
        pdf.set_x(pdf.get_x() + bar_w + 3)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(20, 7, f'{value}  ({pct:.0f}%)')
        pdf.ln(8)

    # ─── Aggregate Meta data ───────────────────────────────────────────
    total_spend   = sum(float(c.get('spend', 0)) for c in meta_campaigns)
    total_clicks  = sum(int(c.get('clicks', 0)) for c in meta_campaigns)
    total_impr    = sum(int(c.get('impressions', 0)) for c in meta_campaigns)
    total_leads   = 0
    for c in meta_campaigns:
        for a in c.get('actions', []) or []:
            if a.get('action_type') == 'onsite_conversion.lead_grouped':
                total_leads += int(a.get('value', 0))
    cpl  = round(total_spend / total_leads, 2) if total_leads else 0
    ctr  = round(total_clicks / total_impr * 100, 2) if total_impr else 0
    cpm  = round(total_spend / total_impr * 1000, 2) if total_impr else 0

    today_str = dt.date.today().strftime('%d/%m/%Y')
    filepath  = f'/tmp/reporte_paid_{client_name.replace("/","_").replace(" ","_")}_{dt.date.today()}.pdf'
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(18, 18, 18)

    # ─── PORTADA ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_fill_color(*C_DARK)
    pdf.rect(0, 0, 210, 297, 'F')
    # Accent bar
    pdf.set_fill_color(*C_BLUE)
    pdf.rect(0, 120, 210, 4, 'F')
    pdf.set_text_color(*C_WHITE)
    pdf.set_font('Helvetica', 'B', 36)
    pdf.set_y(65)
    pdf.cell(0, 18, 'PAID MEDIA', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font('Helvetica', 'B', 28)
    pdf.cell(0, 14, 'REPORT', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_y(132)
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(147, 197, 253)  # blue-300
    pdf.cell(0, 10, safe(client_name), align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(148, 163, 184)  # slate-400
    pdf.cell(0, 8, 'Ultimos 30 dias   |   Meta Ads' + (' + CRM' if crm_funnel else ''), align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_y(260)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f'Generado: {today_str}   |   Marketing Agent Bot', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ─── PÁGINA 1: KPIs + CAMPAÑAS ────────────────────────────────────
    pdf.add_page()
    pdf.set_text_color(*C_DARK)

    # KPI cards row 1
    section_header(pdf, 'KPIs GLOBALES — ULTIMOS 30 DIAS')
    y0 = pdf.get_y()
    card_w = 39
    gap = 3
    kpi_card(pdf, 18,          y0, card_w, 'Gasto total',  f'${total_spend:,.0f}',  'USD',          C_BLUE)
    kpi_card(pdf, 18+card_w+gap, y0, card_w, 'Leads Meta',   str(total_leads),       'ultimos 30d',  C_GREEN)
    kpi_card(pdf, 18+(card_w+gap)*2, y0, card_w, 'CPL',       f'${cpl:,.2f}',         'costo por lead', C_ORANGE)
    kpi_card(pdf, 18+(card_w+gap)*3, y0, card_w, 'CTR',       f'{ctr:.2f}%',          f'CPM ${cpm:.2f}', C_BLUE)
    pdf.set_y(y0 + 28)

    # Campaigns / Adsets table
    is_adset = (level == 'adset')
    section_header(pdf, 'DETALLE POR CONJUNTO DE ANUNCIO' if is_adset else 'DETALLE POR CAMPANA')
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(*C_LIGHT)
    pdf.set_text_color(*C_GRAY)
    col_label = 'Conjunto de anuncio' if is_adset else 'Campana'
    cols = [(col_label, 78), ('Gasto', 22), ('Leads', 18), ('CPL', 22), ('CTR', 18), ('Estado', 16)]
    for label, w in cols:
        pdf.cell(w, 6, safe(label), fill=True, border=0)
    pdf.ln(6)
    for camp in meta_campaigns[:15]:
        c_leads = 0
        for a in camp.get('actions', []) or []:
            if a.get('action_type') == 'onsite_conversion.lead_grouped':
                c_leads += int(a.get('value', 0))
        c_spend  = float(camp.get('spend', 0))
        c_clicks = int(camp.get('clicks', 0))
        c_impr   = int(camp.get('impressions', 0))
        c_cpl    = round(c_spend / c_leads, 2) if c_leads else 0
        c_ctr    = round(c_clicks / c_impr * 100, 2) if c_impr else 0
        status_color = C_GREEN if c_leads > 0 else C_RED
        # Para adset level: mostrar nombre del adset + campaña padre resumida
        name = (camp.get('adset_name', camp.get('campaign_name', '?')) if is_adset
                else camp.get('campaign_name', '?'))[:42]
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(*C_DARK)
        pdf.cell(78, 6, safe(name), border='B')
        pdf.cell(22, 6, f'${c_spend:,.0f}', border='B')
        pdf.cell(18, 6, str(c_leads), border='B')
        pdf.set_text_color(*status_color)
        pdf.cell(22, 6, f'${c_cpl:,.0f}' if c_cpl else '-', border='B')
        pdf.set_text_color(*C_DARK)
        pdf.cell(18, 6, f'{c_ctr:.1f}%', border='B')
        pdf.set_text_color(*status_color)
        dot = 'OK' if c_leads > 0 else 'SIN CONV'
        pdf.cell(16, 6, dot, border='B')
        pdf.set_text_color(*C_DARK)
        pdf.ln(6)

    # ─── PÁGINA 2: CRM FUNNEL (si hay datos) ─────────────────────────
    if crm_funnel:
        pdf.add_page()
        pdf.set_text_color(*C_DARK)
        section_header(pdf, 'PIPELINE CRM — BHU/UIN')

        f = crm_funnel['funnel']
        total_pipe = f['contactados'] + f['interesados'] + f['evaluando'] + f['promesa_pago'] + f['estudiantes']
        conv = round(f['estudiantes'] / total_pipe * 100, 1) if total_pipe else 0

        # CRM KPIs
        y0 = pdf.get_y()
        kpi_card(pdf, 18,    y0, 55, 'Leads sin contactar', f['leads_sin_contactar'], 'pendientes de gestion', C_ORANGE)
        kpi_card(pdf, 76,    y0, 55, 'En pipeline activo',  total_pipe,                 'deals abiertos',         C_BLUE)
        kpi_card(pdf, 134,   y0, 55, 'Estudiantes',         f['estudiantes'],           f'Conv. {conv}%',         C_GREEN)
        pdf.set_y(y0 + 28)

        # Funnel bars
        section_header(pdf, 'EMBUDO DE CONVERSION')
        stages_display = [
            ('1. Contactados',    f['contactados'],   C_BLUE),
            ('2. Interesados',    f['interesados'],   (99, 102, 241)),
            ('3. Evaluando',      f['evaluando'],     C_ORANGE),
            ('4. Promesa de pago',f['promesa_pago'],  (234, 179, 8)),
            ('Estudiantes [ok]',  f['estudiantes'],   C_GREEN),
            ('Perdidos [x]',      f['perdidos'],      C_RED),
        ]
        ref = max(f['contactados'], 1)
        for label, val, color in stages_display:
            funnel_bar(pdf, label, val, ref, color)

        # Top programs
        section_header(pdf, 'TOP PROGRAMAS EN PIPELINE')
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(*C_DARK)
        for prog, cnt in list(crm_funnel['top_programas'].items())[:6]:
            pct = round(cnt / total_pipe * 100) if total_pipe else 0
            pdf.cell(130, 6, safe(f'  {prog}'))
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(20, 6, str(cnt))
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(20, 6, f'{pct}%')
            pdf.ln(6)

        # Lead sources
        section_header(pdf, 'FUENTES DE LEADS')
        pdf.set_font('Helvetica', '', 9)
        for src, cnt in list(crm_funnel['leads_por_fuente'].items())[:6]:
            pct = round(cnt / crm_funnel['leads_total'] * 100) if crm_funnel['leads_total'] else 0
            pdf.cell(120, 6, safe(f'  {src}'))
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(20, 6, str(cnt))
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(20, 6, f'{pct}%')
            pdf.ln(6)

    # ─── FOOTER en cada página ────────────────────────────────────────
    pdf.set_y(-14)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(*C_GRAY)
    pdf.cell(0, 5, safe(f'Marketing Agent Bot  |  {today_str}  |  {client_name}'), align='C')

    pdf.output(filepath)
    return filepath


def generate_seo_pdf(reports, month_str):
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    EMOJI_MAP = {
        '📊': '', '⚡': '', '🔍': '', '🤖': '', '📈': '', '🎯': '',
        '🔑': '', '💡': '', '📅': '', '🌐': '', '🏷️': '',
        '🟢': '[OK]', '🟡': '[~]', '🔴': '[!]',
        '✅': 'SI', '❌': 'NO', '•': '-', '↑': '+', '↓': '-',
        '*': '', '_': '', '`': '',
    }

    def clean(text):
        for k, v in EMOJI_MAP.items():
            text = text.replace(k, v)
        text = re.sub(r'[^\x00-\x7F\xc0-\xff\n]', '', text)
        return text.strip()

    def safe_str(s):
        return s.encode('latin-1', 'replace').decode('latin-1')

    def cell(pdf, h, txt, **kw):
        pdf.cell(0, h, safe_str(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT, **kw)

    filepath = f'/tmp/reporte_seo_{month_str.replace(" ", "_")}.pdf'
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(20, 20, 20)

    # ── Portada ──
    pdf.add_page()
    pdf.set_fill_color(30, 60, 120)
    pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 32)
    pdf.set_y(90)
    cell(pdf, 16, 'Reporte SEO / AEO', align='C')
    pdf.set_font('Helvetica', '', 20)
    cell(pdf, 12, month_str, align='C')
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(180, 200, 240)
    pdf.ln(6)
    cell(pdf, 8, '6 clientes analizados', align='C')
    cell(pdf, 8, 'Generado por Marketing Agent', align='C')
    cell(pdf, 8, dt.date.today().strftime('%d/%m/%Y'), align='C')

    SECTION_MARKERS = ['PERFORMANCE', 'SEO TECNICO', 'SEO T', 'AEO', 'SEARCH CONSOLE',
                       'ACCIONES', 'Top keywords', 'Oportunidades', 'REPORTE']

    for report_text in reports:
        pdf.add_page()
        pdf.set_text_color(0, 0, 0)
        lines = clean(report_text).split('\n')
        first = True
        for line in lines:
            line = line.strip()
            if not line:
                pdf.ln(2)
                continue
            # Title of each client report
            if first:
                pdf.set_fill_color(30, 60, 120)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font('Helvetica', 'B', 13)
                pdf.multi_cell(0, 9, safe_str(line), fill=True,
                               new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(3)
                first = False
            # Section headers
            elif any(m in line for m in SECTION_MARKERS):
                pdf.set_font('Helvetica', 'B', 10)
                pdf.set_text_color(30, 60, 120)
                pdf.set_fill_color(235, 240, 255)
                pdf.multi_cell(0, 7, '  ' + safe_str(line), fill=True,
                               new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(1)
            # Data lines
            else:
                pdf.set_font('Helvetica', '', 9)
                pdf.multi_cell(0, 5.5, safe_str(line),
                               new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(filepath)
    return filepath

def run_seo_reports():
    tg_send('🔍 Iniciando análisis SEO/AEO mensual...\n\nClientes: EBDS · Sibila · Tivenos · BehindU · ZoWeAre · Pediapartner\n\nEstimado: ~2 minutos')

    # Get Google token once
    try:
        token = get_google_token()
    except Exception as e:
        token = None
        print(f'Google token error: {e}')

    # Parallel data fetching per client
    def fetch_all(client):
        name = client['name']
        ps, tech, sc, ga4 = None, None, None, None
        with ThreadPoolExecutor(max_workers=4) as ex:
            f_ps   = ex.submit(get_pagespeed, client['url'])
            f_tech = ex.submit(crawl_seo, client['url'])
            f_sc   = ex.submit(get_sc_data, token, client['sc_url']) if (token and client['sc_url']) else None
            f_ga4  = ex.submit(get_ga4_data, token, client['ga4']) if (token and client.get('ga4')) else None
            try: ps   = f_ps.result(timeout=25)
            except Exception as e: print(f'PageSpeed {name}: {e}')
            try: tech = f_tech.result(timeout=15)
            except Exception as e: print(f'Crawl {name}: {e}')
            if f_sc:
                try: sc = f_sc.result(timeout=20)
                except Exception as e: print(f'SC {name}: {e}')
            if f_ga4:
                try: ga4 = f_ga4.result(timeout=20)
                except Exception as e: print(f'GA4 {name}: {e}')
        return ps, tech, sc, ga4

    all_reports = []
    for client in SEO_CLIENTS:
        try:
            ps, tech, sc, ga4 = fetch_all(client)
            if not tech:
                tg_send(f'⚠️ {client["name"]}: no se pudo analizar el sitio.')
                continue
            report = build_seo_report(client['name'], ps, tech, sc, ga4)
            all_reports.append(report)
            # Send via Telegram (split if too long)
            if len(report) > 3800:
                mid = report.find('\n🎯')
                if mid > 0:
                    tg_send(report[:mid])
                    tg_send(report[mid:])
                else:
                    tg_send(report[:3800])
                    tg_send(report[3800:])
            else:
                tg_send(report)
        except Exception as e:
            tg_send(f'❌ Error analizando {client["name"]}: {str(e)[:100]}')

    # Generate and send PDF
    if all_reports:
        try:
            month_str = dt.date.today().replace(day=1).__sub__(dt.timedelta(days=1)).strftime('%B %Y')
            pdf_path = generate_seo_pdf(all_reports, month_str)
            tg_send_document(
                pdf_path,
                f'reporte_seo_aeo_{month_str.replace(" ", "_").lower()}.pdf',
                caption=f'📄 Reporte SEO/AEO completo — {month_str}',
                mimetype='application/pdf'
            )
            os.unlink(pdf_path)
        except Exception as e:
            print(f'PDF error: {e}')
            tg_send(f'⚠️ PDF no pudo generarse: {str(e)[:100]}')

    tg_send('✅ Análisis SEO/AEO completo.\n6 sitios analizados.\nPróximo reporte: 1er día hábil del mes que viene.')


# --- Social post checker ---
def check_new_posts(state):
    last_ids = state.get('last_post_ids', {})

    for acc in SOCIAL_ACCOUNTS:
        client = acc['client']
        new_posts = []  # acumular por cliente para agrupar en un solo mensaje

        # ── Facebook ──
        if acc.get('fb'):
            key = f'fb_{acc["fb"]}'
            try:
                url = (f'https://graph.facebook.com/v21.0/{acc["fb"]}/posts'
                       f'?fields=id,message,story,created_time,permalink_url'
                       f'&limit=3&access_token={META_TOKEN}')
                posts = http_req(url).get('data', [])
                if posts:
                    latest = posts[0]
                    pid = latest.get('id')
                    if pid and pid != last_ids.get(key):
                        text = (latest.get('message') or latest.get('story') or 'Sin texto')[:200]
                        link = latest.get('permalink_url', f'https://facebook.com/{acc["fb"]}')
                        new_posts.append({'red': '📘 Facebook', 'text': text, 'link': link})
                        last_ids[key] = pid
            except Exception as e:
                print(f'FB check {client}: {e}')

        # ── Instagram ──
        if acc.get('ig'):
            key = f'ig_{acc["ig"]}'
            try:
                url = (f'https://graph.facebook.com/v21.0/{acc["ig"]}/media'
                       f'?fields=id,caption,media_type,timestamp,permalink'
                       f'&limit=3&access_token={META_TOKEN}')
                posts = http_req(url).get('data', [])
                if posts:
                    latest = posts[0]
                    pid = latest.get('id')
                    if pid and pid != last_ids.get(key):
                        caption = (latest.get('caption') or 'Sin caption')[:200]
                        link = latest.get('permalink', 'https://instagram.com/')
                        mtype = latest.get('media_type', '')
                        icon = '🎥' if mtype in ['VIDEO', 'REEL'] else '📸'
                        new_posts.append({'red': f'{icon} Instagram', 'text': caption, 'link': link})
                        last_ids[key] = pid
            except Exception as e:
                print(f'IG check {client}: {e}')

        # LinkedIn — requiere token separado (paso 2)

        # ── Enviar UN solo mensaje agrupado por cliente ──
        if new_posts:
            if len(new_posts) == 1:
                p = new_posts[0]
                tg_send(
                    f'{p["red"]} *Nueva publicación*\n\n'
                    f'🏢 {client}\n'
                    f'💬 _{p["text"]}_\n'
                    f'🔗 {p["link"]}'
                )
            else:
                # crosspost FB + IG → un solo mensaje
                lines = f'📣 *Nueva publicación — {client}*\n\n'
                for p in new_posts:
                    lines += f'{p["red"]}: {p["link"]}\n'
                lines += f'\n💬 _{new_posts[0]["text"]}_'
                tg_send(lines)

    state['last_post_ids'] = last_ids
    return state


# ─── CALENDAR HELPERS ──────────────────────────────────────────────────────────

def get_calendar_data(month_str=None):
    """Lee datos del calendario (todas las marcas) desde las tareas dedicadas.
    Devuelve {brand: [posts]} para un mes, o {month: {brand: [posts]}} sin mes."""
    try:
        brands_data = {}
        for brand in get_all_brand_tasks():
            brand_months = read_calendar_brand(brand)  # {month_str: [posts]}
            if month_str:
                posts = brand_months.get(month_str, [])
                if posts:
                    brands_data[brand] = posts
            else:
                for m, posts in brand_months.items():
                    if m not in brands_data:
                        brands_data[m] = {}
                    brands_data[m][brand] = posts
        return brands_data
    except Exception as e:
        print(f'Cal get error: {e}')
        return {}

def update_calendar_month(month_str, month_data):
    """Actualiza un mes: escribe cada marca en su tarea dedicada."""
    for brand, posts in month_data.items():
        try:
            save_calendar_brand(brand, month_str, posts)
        except Exception as e:
            print(f'update_calendar_month {brand}: {e}')
    return month_data

# Alias de compatibilidad para calendar/generate
def merge_calendar_into_state(state, month_str, month_data):
    """Actualiza el calendario por marca. El state arg se ignora."""
    update_calendar_month(month_str, month_data)
    return state


def get_posting_dates(year, month):
    first = dt.date(year, month, 1)
    next_m = month + 1 if month < 12 else 1
    next_y = year if month < 12 else year + 1
    last = dt.date(next_y, next_m, 1) - dt.timedelta(days=1)
    dates = []
    d = first
    while d <= last:
        if d.weekday() in [0, 2, 4]:  # Mon=0, Wed=2, Fri=4
            dates.append(d)
        d += dt.timedelta(days=1)
    return dates

def assign_formats(brands_list, posting_dates):
    assignments = {}
    slot_idx = 0
    zoweare_count = 0
    for date in posting_dates:
        day = {}
        rotation = CALENDAR_FORMAT_ROTATION[slot_idx % len(CALENDAR_FORMAT_ROTATION)]
        for i, brand in enumerate(brands_list):
            if brand == 'ZoWeAre':
                if zoweare_count < 5:
                    day[brand] = rotation[i % len(rotation)]
                    zoweare_count += 1
            else:
                day[brand] = rotation[i % len(rotation)]
        assignments[date.isoformat()] = day
        slot_idx += 1
    return assignments

CONTENT_STYLE_GUIDE = """
IDIOMA OBLIGATORIO: Español neutro — sin conjugaciones de "vos" (prohibido: hacés/tenés/querés/podés/mirá/descubrí/aprendé/usá/dale). Usar "tú/te/tu" o formas impersonales. Esto es innegociable.

REGLAS DE FORMATO texto_imagen:
- Post (imagen fija): titular impactante máx 12 palabras + subtítulo opcional + "(logo [MARCA])" al final
- Carrusel (mínimo 5 slides): "S1: [tema de apertura]\\nS2: [punto clave → beneficio concreto]\\nS3: [punto clave → beneficio concreto]\\nS4: [punto clave → beneficio concreto]\\nS5: [punto clave → beneficio concreto]\\nS6: [CTA + web de la marca]" — cada slide tiene texto corto, impactante
- Reel (guion completo, NO dejar incompleto):
  "Gancho (0-3s): [descripción exacta de la escena de apertura — qué se ve en pantalla]\\nEscena 1 (3-10s): [qué se muestra/hace]\\nEscena 2 (10-20s): [qué se muestra/hace]\\nEscena 3 (20-28s): [qué se muestra/hace]\\nNarración completa: \\'[guion hablado completo de 40-60 palabras, español neutro]\'\\nTexto superpuesto: \\'[frase clave que aparece en pantalla]\'\\nCTA final (28-35s): \\'[texto del CTA visible en pantalla + acción concreta]\'"
- Story (1 sola placa vertical, formato efímero — más directo e informal que un Post): "[Frase corta tipo pregunta o dato, máx 10 palabras]\\nSticker: [encuesta/quiz/deslizador o \\'Link en bio\\' si aplica]\\n(logo [MARCA])"

REGLAS DE COPY: máx 120 palabras, tono directo y aspiracional, usa → para listar beneficios, 1-2 emojis por bloque, siempre terminar con CTA al link de la bio y 3-5 hashtags. Para Story el copy es opcional y breve (máx 20 palabras) — la placa es autoexplicativa.
Sin saltos de línea literales en el JSON (usar \\n dentro del string).
"""

BRAND_STYLE_EXAMPLES = {
    'EBDS': """
EJEMPLOS DE CONTENIDO EBDS (estilo correcto de marca):

POST:
texto_imagen: "¿Quieres crecer profesionalmente sin pausar tu vida?\\nTu formación, tu ritmo.\\n(logo EBDS)"
copy: "📚 Diplomados y Másteres online diseñados para profesionales que no se detienen.\\n→ Certificado europeo apostillado\\n→ Tutor que te acompaña cada semana\\n→ Contenido aplicable desde el módulo 1\\n→ 100% online, a tu ritmo\\nDa el próximo paso. 🔗 Link en la bio.\\n#EBDS #FormaciónOnline #DesarrolloProfesional #CertificaciónEuropea"

CARRUSEL:
texto_imagen: "S1: ¿Por qué los profesionales eligen EBDS?\\nS2: Flexibilidad total → estudias cuando puedes, desde donde estás\\nS3: Tutor real → te acompaña 2 a 4 veces por mes\\nS4: Aplicás desde el módulo 1 → sin esperar al final\\nS5: Certificado europeo → apostillado por la Convención de La Haya\\nS6: Empezá el próximo martes → ebds.online"
copy: "La formación que se adapta a tu vida — no al revés. 🎯\\nEstos son los 5 motivos por los que miles de profesionales eligen EBDS →\\n→ Flexible\\n→ Con tutor\\n→ Aplicable desde el día 1\\n→ Certificado europeo\\n→ Precio con beca\\n🔗 Conoce los programas — Link en la bio.\\n#EBDS #EstudiaOnline #FormaciónProfesional #EducaciónOnline"

REEL:
texto_imagen: "Gancho (0-3s): Persona trabajando en laptop, recibe notificación: \\'Módulo 1 completado\\'\\nEscena 1 (3-10s): Muestra el campus virtual con el material del Máster en Data Analytics en pantalla\\nEscena 2 (10-20s): Videollamada breve con tutor — feedback personalizado\\nEscena 3 (20-28s): Diploma digital con sello europeo, persona sonriendo\\nNarración completa: \\'En EBDS aprendes a tu ritmo, pero no estás solo. Desde el primer módulo aplicas lo que aprendes. Con un tutor que te acompaña y un certificado europeo al finalizar. Todo online, sin pausar tu vida.\\'\\nTexto superpuesto: \\'Tu ritmo. Tu carrera. Tu momento.\\'\\nCTA final (28-35s): \\'Conoce los Diplomados y Másteres — Link en la bio\\'"
copy: "Estudiar no tiene que ser sinónimo de sacrificar todo. 🎓\\nEn EBDS aprendes a tu ritmo, con tutor real y certificado europeo.\\n→ 100% online\\n→ Aplicás desde el módulo 1\\n→ Diploma apostillado\\n🔗 Diplomados y Másteres en el link de la bio.\\n#EBDS #FormaciónOnline #MásterOnline #CertificaciónEuropea"
""",
    'Sibila': """
EJEMPLOS DE CONTENIDO SIBILA:

POST:
texto_imagen: "¿Tu equipo atiende por WhatsApp, email y teléfono por separado?\\nHay una mejor forma.\\n(logo Sibila)"
copy: "💬 Cada canal desconectado es un cliente frustrado.\\nSibila centraliza WhatsApp, Email, SMS y más en una sola plataforma con IA.\\n→ Respuestas más rápidas\\n→ Historial unificado del cliente\\n→ Menos errores, más satisfacción\\nTransforma tu atención al cliente hoy. 🔗 Link en la bio.\\n#Sibila #Omnicanal #AtenciónAlCliente #IA"

CARRUSEL:
texto_imagen: "S1: El problema: comunicación dispersa\\nS2: Canal 1 — WhatsApp sin control centralizado\\nS3: Canal 2 — Email sin seguimiento real\\nS4: Canal 3 — Teléfono sin historial\\nS5: La solución — Sibila unifica todo con IA\\nS6: Resultado: 40% menos tiempo de respuesta → sibila.app"
copy: "¿Cuántos canales de atención tiene tu empresa? 📊\\nWhatsApp, email, teléfono, redes... sin un hub central, la experiencia del cliente sufre.\\nSibila lo resuelve en una sola plataforma.\\n→ Un lugar, todos los canales\\n→ IA que automatiza respuestas frecuentes\\n→ Métricas en tiempo real\\nConoce cómo funciona → 🔗 Link en la bio.\\n#Sibila #CX #Chatbot #AutomatizaciónEmpresarial"

REEL:
texto_imagen: "Gancho (0-3s): Notificaciones llegando de todos lados — WhatsApp, email, teléfono — en caos\\nEscena 1 (3-10s): Agente de atención al cliente abrumado saltando entre pantallas\\nEscena 2 (10-20s): Corte — mismo agente ahora en Sibila: todos los canales en una sola pantalla, con respuestas sugeridas por IA\\nEscena 3 (20-28s): Métrica en pantalla: -40% tiempo de respuesta, clientes satisfechos\\nNarración completa: \\'Tu equipo no debería perder tiempo saltando entre canales. Sibila centraliza WhatsApp, email, SMS y más en una sola plataforma con IA. Menos caos, más clientes satisfechos. Empieza hoy.\\'\\nTexto superpuesto: \\'Todos tus canales. Una sola plataforma.\\'\\nCTA final (28-35s): \\'Pide tu demo — Link en la bio\\'"
copy: "¿Cuánto tiempo pierde tu equipo saltando entre canales? ⏱️\\nCon Sibila, WhatsApp, Email y SMS se gestionan desde un solo lugar con IA.\\n→ Respuestas automáticas para preguntas frecuentes\\n→ Historial unificado por cliente\\n→ Métricas en tiempo real\\n🔗 Demo gratuita en el link de la bio.\\n#Sibila #AtenciónAlCliente #CX #Omnicanal"
""",
    '_generic': """
FORMATO DE REFERENCIA:

POST:
texto_imagen: "[Titular impactante que resume el valor principal de la marca]\\n[Subtítulo opcional con dato o beneficio]\\n(logo [MARCA])"
copy: "[Emoji] [Frase de apertura que conecta con el problema del cliente].\\n[Desarrollo con flechas →]\\n→ Beneficio 1\\n→ Beneficio 2\\n→ Beneficio 3\\n[CTA]. 🔗 Link en la bio.\\n#[hashtag1] #[hashtag2] #[hashtag3]"

CARRUSEL:
texto_imagen: "S1: [Tema de apertura — el problema o la promesa]\\nS2: [Punto clave 1 → beneficio]\\nS3: [Punto clave 2 → beneficio]\\nS4: [Punto clave 3 → beneficio]\\nS5: [Punto clave 4 → beneficio]\\nS6: [CTA + web de la marca]"
copy: "[Pregunta o afirmación que conecta con el dolor del cliente] 🎯\\n[Desarrollo breve de la propuesta de valor]\\n→ Beneficio 1\\n→ Beneficio 2\\n→ Beneficio 3\\n[CTA]. 🔗 Link en la bio.\\n#[hashtag1] #[hashtag2] #[hashtag3]"

REEL:
texto_imagen: "Gancho (0-3s): [escena de apertura visual impactante]\\nEscena 1 (3-10s): [qué se muestra]\\nEscena 2 (10-20s): [qué se muestra]\\nEscena 3 (20-28s): [qué se muestra]\\nNarración completa: \\'[guion hablado completo de 40-60 palabras]\'\\nTexto superpuesto: \\'[frase clave en pantalla]\'\\nCTA final (28-35s): \\'[texto del CTA visible]\'"
""",
}

def generate_social_posts(brand, month_label, slots):
    """Genera social posts en batches de 4 (límite de tokens por request a Claude).
    Los batches se disparan en PARALELO — antes eran secuenciales y para un mes con
    ~13 slots (4 batches) la suma de latencias superaba fácil los 29s de abort del
    frontend / el timeout de la función serverless. En paralelo el tiempo total
    queda acotado por el batch más lento, no por la suma de todos."""
    if not slots:
        return []
    context = BRAND_CONTEXT.get(brand, brand)
    days_es = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
    examples = BRAND_STYLE_EXAMPLES.get(brand, BRAND_STYLE_EXAMPLES['_generic'])
    batch_size = 4
    batches = [slots[i:i+batch_size] for i in range(0, len(slots), batch_size)]

    def gen_one(batch):
        slots_info = [{'date': s[0].isoformat() if hasattr(s[0],'isoformat') else s[0],
                       'day': days_es[dt.date.fromisoformat(str(s[0])).weekday()],
                       'type': s[1]} for s in batch]
        prompt = f"""Genera {len(slots_info)} posts para {brand} — {month_label}.

MARCA: {context}

{CONTENT_STYLE_GUIDE}
{examples}
SLOTS A GENERAR:
{json.dumps(slots_info, ensure_ascii=False)}

IMPORTANTE: Los Reels deben tener el guion COMPLETO — todas las escenas, la narración entera y el CTA. No dejar nada incompleto.

SOLO JSON array, sin texto extra antes ni después:
[{{"date":"YYYY-MM-DD","day":"Dia","type":"Reel/Carrusel/Post","pilar":"categoria","objetivo":"awareness/educacion/conversion","titulo":"max 60 chars","texto_imagen":"estructura visual del contenido COMPLETA","copy":"caption para redes max 120 palabras","hashtags":"#tag1 #tag2 #tag3"}}]"""
        r = claude(prompt, max_tokens=3000)
        m = re.search(r'\[.*?\]', r, re.DOTALL)
        batch_posts = json.loads(m.group()) if m else []
        if len(batch_posts) != len(slots_info):
            print(f'Social gen {brand}: esperaba {len(slots_info)} posts, el modelo devolvió {len(batch_posts)}')
        for j, p in enumerate(batch_posts):
            # Nunca confiar en el date/day/type que "recuerda" el modelo — forzar
            # los valores reales calculados por get_posting_dates para que el post
            # quede en el día correcto del calendario.
            if j < len(slots_info):
                p['date'] = slots_info[j]['date']
                p['day']  = slots_info[j]['day']
                p['type'] = slots_info[j]['type']
            p.update({'id': f'{brand.lower()}-{p.get("date", j)}', 'brand': brand,
                      'status': 'pendiente', 'comments': '', 'networks': ['Instagram','Facebook']})
        return batch_posts

    results = [[] for _ in batches]
    with ThreadPoolExecutor(max_workers=min(4, len(batches))) as ex:
        futures = {ex.submit(gen_one, b): idx for idx, b in enumerate(batches)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results[idx] = fut.result()
            except Exception as e:
                print(f'Social gen {brand} batch {idx}: {e}')

    all_posts = []
    for r in results:
        all_posts.extend(r)
    return all_posts

def generate_linkedin_posts(brand, month_label, count):
    context = BRAND_CONTEXT.get(brand, brand)
    prompt = f"""Genera {count} publicaciones de LinkedIn para {brand} — {month_label}.

MARCA: {context}

IDIOMA: Español neutro — sin conjugaciones de vos (no hacés/tenés/querés). Usar tú o formas impersonales.

Estilo: thought leadership, educativo o caso de éxito. Párrafos cortos (2-3 líneas máx), gancho fuerte en la primera línea, datos concretos cuando aplica, CTA al final.

Devuelve SOLO JSON:
[{{"titulo":"titulo max 70 chars","pilar":"categoria","objetivo":"thought leadership/educacion/caso de exito","copy":"texto 200-250 palabras listo para LinkedIn, con saltos de linea como \\n"}}]"""
    try:
        r = claude(prompt, max_tokens=3000)
        m = re.search(r'\[.*\]', r, re.DOTALL)
        if m:
            posts = json.loads(m.group())
            for i, p in enumerate(posts):
                p.update({'id': f'{brand.lower()}-li-{i+1}', 'brand': brand, 'type': 'LinkedIn', 'date': '', 'status': 'pendiente', 'comments': ''})
            return posts
    except Exception as e:
        print(f'LinkedIn gen {brand}: {e}')
    return []

def generate_blog_posts(brand, month_label, count):
    context = BRAND_CONTEXT.get(brand, brand)
    prompt = f"""Genera {count} artículos de blog para {brand} — {month_label}.

MARCA: {context}

IDIOMA: Español neutro — sin conjugaciones de vos (no hacés/tenés/querés). Usar tú o formas impersonales.

SEO-friendly, informativos, orientados a resolver una duda del cliente ideal. Devuelve SOLO JSON:
[{{"titulo":"titulo SEO max 70 chars","pilar":"categoria","objetivo":"SEO/educacion/conversion","copy":"intro (2 párrafos) + 3 secciones con H2 + conclusión con CTA (max 300 palabras total, saltos de linea como \\n)"}}]"""
    try:
        r = claude(prompt, max_tokens=2500)
        m = re.search(r'\[.*\]', r, re.DOTALL)
        if m:
            posts = json.loads(m.group())
            for i, p in enumerate(posts):
                p.update({'id': f'{brand.lower()}-blog-{i+1}', 'brand': brand, 'type': 'Blog', 'date': '', 'status': 'pendiente', 'comments': ''})
            return posts
    except Exception as e:
        print(f'Blog gen {brand}: {e}')
    return []

def generate_email_posts(brand, month_label, count):
    context = BRAND_CONTEXT.get(brand, brand)
    prompt = f"""Genera {count} emails de marketing para {brand} — {month_label}.

MARCA: {context}

IDIOMA: Español neutro — sin conjugaciones de vos (no hacés/tenés/querés). Usar tú o formas impersonales.

Objetivo: nutrir leads, convertir o fidelizar. Devuelve SOLO JSON:
[{{"titulo":"asunto del email max 50 chars","pilar":"categoria","objetivo":"nurturing/conversion/fidelizacion","copy":"asunto + preheader (1 línea) + cuerpo (3 párrafos cortos) + CTA (max 200 palabras, saltos de linea como \\n)"}}]"""
    try:
        r = claude(prompt, max_tokens=2000)
        m = re.search(r'\[.*\]', r, re.DOTALL)
        if m:
            posts = json.loads(m.group())
            for i, p in enumerate(posts):
                p.update({'id': f'{brand.lower()}-email-{i+1}', 'brand': brand, 'type': 'Email', 'date': '', 'status': 'pendiente', 'comments': ''})
            return posts
    except Exception as e:
        print(f'Email gen {brand}: {e}')
    return []


def regenerate_single_post(post, instruction=''):
    """Regenera un post individual. Mantiene brand/date/type, genera contenido nuevo."""
    brand     = post.get('brand', '')
    post_type = post.get('type', 'Post')
    date_str  = post.get('date', '')
    context   = BRAND_CONTEXT.get(brand, brand)
    examples  = BRAND_STYLE_EXAMPLES.get(brand, BRAND_STYLE_EXAMPLES['_generic'])
    days_es   = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
    day_name  = ''
    if date_str:
        try:
            day_name = days_es[dt.date.fromisoformat(date_str).weekday()]
        except Exception:
            pass
    instr_note = f'\nINSTRUCCIÓN ESPECIAL (aplicar obligatoriamente): {instruction}' if instruction else \
                 '\nGenera un ángulo completamente diferente al habitual — nuevo gancho, distinto pilar, enfoque alternativo.'
    slot = [{'date': date_str, 'day': day_name, 'type': post_type}]
    prompt = f"""Genera 1 post para {brand}.

MARCA: {context}
{CONTENT_STYLE_GUIDE}
{examples}
{instr_note}

SLOT: {json.dumps(slot, ensure_ascii=False)}

Los Reels deben tener el guion COMPLETO — todas las escenas, narración entera y CTA.

SOLO JSON array con 1 elemento:
[{{"date":"{date_str}","day":"{day_name}","type":"{post_type}","pilar":"categoria","objetivo":"awareness/educacion/conversion","titulo":"max 60 chars","texto_imagen":"estructura visual COMPLETA","copy":"caption max 120 palabras","hashtags":"#tag1 #tag2 #tag3"}}]"""
    r = claude(prompt, max_tokens=3000)
    m = re.search(r'\[.*?\]', r, re.DOTALL)
    if m:
        posts = json.loads(m.group())
        if posts:
            p = posts[0]
            p.update({
                'id':       post.get('id', f'{brand.lower()}-{date_str}'),
                'brand':    brand,
                'status':   'pendiente',
                'comments': post.get('comments', ''),
                'networks': post.get('networks', ['Instagram', 'Facebook']),
            })
            return p
    return None


def h_regen_post(text, state):
    """Regenera uno o más posts del calendario desde Telegram."""
    t = text.lower()

    # Brand
    brand_keys = {'ebds':'EBDS','sibila':'Sibila','zoweare':'ZoWeAre','tivenos':'Tivenos','bhu':'BHU','behind':'BHU'}
    brand = next((v for k,v in brand_keys.items() if k in t), None)
    if not brand:
        tg_send('¿Para qué marca regenero el contenido?\n\n• EBDS  • Sibila  • ZoWeAre  • Tivenos  • BHU')
        return state

    # Month
    months_map = {'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,
                  'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12}
    month_num = next((v for k,v in months_map.items() if k in t), None)
    today = dt.date.today()
    if not month_num:
        nxt = today.replace(day=1) + dt.timedelta(days=32)
        month_num, year = nxt.month, nxt.year
    else:
        year = today.year
        if month_num < today.month:
            year += 1
    month_str = f'{year}-{str(month_num).zfill(2)}'

    # Day number (e.g. "del 3", "el 15")
    day_match = re.search(r'\b(\d{1,2})\b', text)
    target_day = int(day_match.group(1)) if day_match else None

    # Type filter
    type_map = {'reel':'Reel','carrusel':'Carrusel','post':'Post','story':'Story','linkedin':'LinkedIn','blog':'Blog','email':'Email'}
    type_filter = next((v for k,v in type_map.items() if k in t), None)

    # Instruction (text after "que sea", "con enfoque", "sobre", "estilo", "hablando de", etc.)
    instr_match = re.search(
        r'(?:que sea|con enfoque(?: en)?|enfocado en|estilo|tono|hablando de|sobre|acerca de|instrucción:?)\s+(.+)',
        t, re.IGNORECASE
    )
    instruction = instr_match.group(1).strip() if instr_match else ''

    # Find matching posts
    month_data = get_calendar_data(month_str)
    brand_posts = month_data.get(brand, [])

    to_regen = []
    for p in brand_posts:
        if target_day:
            try:
                if dt.date.fromisoformat(p.get('date', '')).day != target_day:
                    continue
            except Exception:
                pass
        if type_filter and p.get('type') != type_filter:
            continue
        to_regen.append(p)

    if not to_regen:
        key = os.environ.get('CALENDAR_KEY', 'sofia2026mkt')
        tg_send(
            f'No encontré posts de *{brand}* que coincidan en {month_str}.\n\n'
            f'Verifica el calendario: https://vercel-deploy-tan-one.vercel.app/calendar?key={key}&month={month_str}'
        )
        return state

    if len(to_regen) > 4:
        tg_send(
            f'Eso son {len(to_regen)} posts — sé más específica.\n'
            f'Ej: _"rehaceme el reel del 3 de junio de EBDS"_ o _"regenera el carrusel del 10 de junio de EBDS que sea sobre empleabilidad"_'
        )
        return state

    tg_send(f'🔄 Regenerando {len(to_regen)} post{"s" if len(to_regen)>1 else ""} de *{brand}*...')

    regenerated = 0
    for post in to_regen:
        try:
            new_post = regenerate_single_post(post, instruction)
            if new_post:
                for i, p in enumerate(month_data[brand]):
                    if p.get('id') == post.get('id'):
                        month_data[brand][i] = new_post
                        break
                regenerated += 1
        except Exception as e:
            print(f'Regen post error: {e}')

    if regenerated > 0:
        save_calendar_data(month_str, month_data)
        key = os.environ.get('CALENDAR_KEY', 'sofia2026mkt')
        tg_send(
            f'✅ {regenerated} post{"s" if regenerated>1 else ""} regenerado{"s" if regenerated>1 else ""} para *{brand}*\n\n'
            f'🔗 https://vercel-deploy-tan-one.vercel.app/calendar?key={key}&month={month_str}'
        )
    else:
        tg_send('❌ No pude regenerar los posts. Intentá de nuevo.')
    return state


def h_calendar(text, state):
    """Encola la generación de contenido. El endpoint /calendar/generate procesa de a 1 marca."""
    t = text.lower()
    months_map = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    month_num = next((v for k, v in months_map.items() if k in t), None)
    today = dt.date.today()
    if not month_num:
        next_m = today.replace(day=1) + dt.timedelta(days=32)
        month_num = next_m.month
        year = next_m.year
    else:
        year = today.year
        if month_num < today.month:
            year += 1
    month_str = f'{year}-{str(month_num).zfill(2)}'
    month_names = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    month_label = f'{month_names[month_num]} {year}'

    brand_keys = {'ebds': 'EBDS', 'sibila': 'Sibila', 'zoweare': 'ZoWeAre', 'tivenos': 'Tivenos', 'bhu': 'BHU', 'behind': 'BHU'}
    if 'todas' in t or 'todo' in t:
        brands_to_gen = list(get_all_brand_tasks())
    else:
        brands_to_gen = list({v for k, v in brand_keys.items() if k in t})

    if not brands_to_gen:
        tg_send('¿Para qué marca genero el calendario?\n\n• EBDS\n• Sibila\n• ZoWeAre\n• Tivenos\n• BHU\n• Todas')
        return state

    # Encolar — /calendar/generate procesa de a 1 marca para no exceder timeout de Vercel
    state['pending_calendar'] = {
        'brands': brands_to_gen,
        'month_str': month_str,
        'month_label': month_label,
        'idx': 0
    }
    n = len(brands_to_gen)
    tg_send(
        f'📅 *Generando calendario...*\n\n'
        f'📆 {month_label}\n'
        f'🏢 {", ".join(brands_to_gen)}\n\n'
        f'⏳ {n} marca{"s" if n > 1 else ""}... (~{n*2} min)'
    )
    state['_trigger_calendar'] = True  # señal para el webhook de disparar el generate
    return state


CALENDAR_HTML = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Calendario de Contenido</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;color:#1e293b;min-height:100vh}
header{background:white;border-bottom:1px solid #e2e8f0;padding:14px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;position:sticky;top:0;z-index:50}
h1{font-size:17px;font-weight:700;white-space:nowrap}
.month-nav{display:flex;align-items:center;gap:8px}
.month-nav button{background:#f1f5f9;border:none;width:30px;height:30px;border-radius:8px;cursor:pointer;font-size:14px;transition:background .2s}
.month-nav button:hover{background:#e2e8f0}
.month-nav span{font-weight:600;min-width:130px;text-align:center;font-size:14px}
.brand-tabs{display:flex;gap:5px;flex-wrap:wrap}
.new-brand-btn{background:white;color:#1e293b;border:1px solid #e2e8f0;padding:6px 12px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;transition:background .15s;white-space:nowrap}
.new-brand-btn:hover{background:#f8fafc}
.nb-color-opt{display:inline-block;width:26px;height:26px;border-radius:50%;cursor:pointer;border:2px solid transparent;transition:transform .15s,border-color .15s}
.nb-color-opt:hover{transform:scale(1.15)}
.nb-color-opt.selected{border-color:#1e293b;transform:scale(1.15)}
.gen-btn{background:#7c3aed;color:white;border:none;padding:6px 14px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;transition:opacity .2s;white-space:nowrap;margin-left:auto}
.gen-btn:hover{opacity:.85}
.gen-type-opt{display:flex;align-items:center;gap:6px;padding:7px 10px;border:1px solid #e2e8f0;border-radius:8px;cursor:pointer;font-size:12px;font-weight:500;transition:background .15s}
.gen-type-opt:hover{background:#f8f5ff}
.gen-type-opt input{accent-color:#7c3aed}
.brand-tab{padding:5px 12px;border-radius:20px;border:2px solid;cursor:pointer;font-size:12px;font-weight:600;transition:all .2s;background:white}
.main{padding:20px;max-width:1400px;margin:0 auto}
.cal-wrap{background:white;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0}
.cal-header{display:grid;grid-template-columns:48px repeat(5,minmax(0,1fr));background:#f8fafc;border-bottom:1px solid #e2e8f0}
.cal-header div{padding:10px 8px;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;text-align:center;letter-spacing:.5px;overflow:hidden}
.cal-body{display:grid;grid-template-columns:48px repeat(5,minmax(0,1fr));align-items:start}
.week-lbl{background:#f8fafc;border-right:1px solid #e2e8f0;display:flex;align-items:flex-start;justify-content:center;padding-top:12px;font-size:11px;color:#94a3b8;font-weight:600;min-height:110px}
.day-cell{border-right:1px solid #f1f5f9;border-bottom:1px solid #f1f5f9;padding:6px;min-height:110px;transition:background .15s;overflow:hidden;width:100%}
.day-cell:hover{background:#fafafa}
.day-cell.inactive{background:#fafafa;opacity:.55}
.day-num{font-size:11px;color:#94a3b8;margin-bottom:5px;font-weight:500}
.chip{display:flex;align-items:center;gap:3px;padding:4px 7px;border-radius:6px;margin-bottom:3px;cursor:pointer;transition:opacity .2s;font-size:11px;border:1px solid transparent}
.chip:hover{opacity:.8;transform:translateY(-1px)}
.chip-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.chip-title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;color:#1e293b}
.chip-icon{flex-shrink:0;font-size:10px}
.chip-status{width:5px;height:5px;border-radius:50%;flex-shrink:0}
.chip-mini{display:flex;align-items:center;gap:3px;padding:2px 6px;border-radius:4px;margin-bottom:2px;cursor:pointer;border:1px dashed;font-size:10px;transition:opacity .15s}
.chip-mini:hover{opacity:.75;transform:translateY(-1px)}
.chip-mini-lbl{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.add-btn{display:block;text-align:center;color:#cbd5e1;cursor:pointer;font-size:16px;padding:2px;border-radius:4px;transition:all .15s;line-height:1}
.add-btn:hover{background:#f1f5f9;color:#64748b}
.extras{margin-top:24px}
.extras h3{font-size:14px;font-weight:700;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-bottom:24px}
.card{background:white;border-radius:10px;padding:14px;border-left:4px solid;cursor:pointer;transition:transform .2s,box-shadow .2s;border:1px solid #e2e8f0;border-left-width:4px}
.card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.08)}
.card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:7px}
.card-brand{font-size:11px;font-weight:700}
.status-pill{font-size:10px;font-weight:600;padding:2px 8px;border-radius:12px}
.card-title{font-size:13px;font-weight:600;margin-bottom:5px;line-height:1.3}
.card-meta{font-size:11px;color:#94a3b8}
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;z-index:100;padding:16px}
.modal{background:white;border-radius:14px;padding:22px;width:100%;max-width:580px;max-height:88vh;overflow-y:auto}
.modal-hd{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}
.modal-hd h3{font-size:15px;font-weight:700;line-height:1.3}
.close-btn{background:none;border:none;font-size:20px;cursor:pointer;color:#94a3b8;flex-shrink:0;padding:0 4px}
label{display:block;font-size:11px;font-weight:700;color:#64748b;margin:12px 0 4px;text-transform:uppercase;letter-spacing:.4px}
input,textarea,select{width:100%;border:1px solid #e2e8f0;border-radius:8px;padding:8px 11px;font-size:13px;font-family:inherit;transition:border .2s;outline:none}
input:focus,textarea:focus,select:focus{border-color:#94a3b8}
textarea{min-height:90px;resize:vertical}
.modal-actions{display:flex;gap:8px;margin-top:16px}
.btn-save{background:#1e293b;color:white;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;transition:background .2s}
.btn-save:hover{background:#334155}
.btn-cancel{background:#f1f5f9;color:#64748b;border:none;padding:10px 20px;border-radius:8px;cursor:pointer;font-size:13px}
.btn-regen{background:none;border:none;cursor:pointer;font-size:15px;padding:2px 5px;border-radius:5px;opacity:.6;transition:opacity .2s,background .2s;line-height:1}
.btn-regen:hover{opacity:1;background:#f0fdf4}
.btn-del{background:none;border:none;cursor:pointer;font-size:11px;padding:1px 3px;border-radius:4px;opacity:.45;color:#dc2626;transition:opacity .2s,background .2s;line-height:1;flex-shrink:0}
.btn-del:hover{opacity:1;background:#fee2e2}
.btn-check{background:none;border:1px solid #cbd5e1;cursor:pointer;font-size:9px;padding:1px 3px;border-radius:3px;color:#94a3b8;font-weight:700;line-height:1;flex-shrink:0;transition:all .15s}
.btn-check:hover{border-color:#22c55e;color:#22c55e;background:#f0fdf4}
.btn-check.checked{background:#dcfce7;border-color:#22c55e;color:#16a34a}
.btn-delete{background:#fee2e2;color:#dc2626;border:none;padding:10px 16px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;transition:background .2s;margin-left:auto}
.btn-delete:hover{background:#fecaca}
.regen-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1001;align-items:center;justify-content:center}
.regen-overlay.show{display:flex}
.regen-modal{background:white;border-radius:14px;padding:28px;width:min(420px,92vw);box-shadow:0 20px 60px rgba(0,0,0,.25)}
.regen-modal h3{margin:0 0 6px;font-size:16px;color:#1e293b}
.regen-modal p{margin:0 0 16px;font-size:13px;color:#64748b}
.regen-modal textarea{width:100%;box-sizing:border-box;padding:10px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:13px;resize:vertical;min-height:70px;font-family:inherit}
.regen-modal textarea:focus{outline:none;border-color:#6366f1}
.regen-actions{display:flex;gap:10px;margin-top:14px}
.btn-regen-go{flex:1;background:#6366f1;color:white;border:none;padding:11px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;transition:background .2s}
.btn-regen-go:hover{background:#4f46e5}
.btn-regen-go:disabled{background:#a5b4fc;cursor:default}
.regen-spinner{display:none;text-align:center;font-size:22px;margin:10px 0}
.regen-spinner.show{display:block}
.hidden{display:none!important}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.legend-item{display:flex;align-items:center;gap:4px;font-size:11px;color:#64748b}
.legend-dot{width:10px;height:10px;border-radius:3px}
.cal-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.empty-msg{text-align:center;padding:60px 20px;color:#94a3b8;font-size:14px}
/* Agenda view (mobile) */
.agenda{display:none}
.agenda-day{margin-bottom:16px;background:white;border-radius:10px;overflow:hidden;border:1px solid #e2e8f0}
.agenda-date{padding:8px 14px;background:#f8fafc;font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid #e2e8f0}
.agenda-row{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid #f1f5f9;cursor:pointer;border-left:3px solid transparent;transition:background .15s}
.agenda-row:last-child{border-bottom:none}
.agenda-row:hover{background:#f8fafc}
.agenda-type{font-size:11px;font-weight:700;white-space:nowrap;min-width:72px}
.agenda-brand{font-size:11px;font-weight:600;white-space:nowrap;min-width:50px}
.agenda-title{font-size:12px;color:#334155;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
@media(max-width:700px){
  .cal-wrap{display:none}
  .agenda{display:block}
  .main{padding:10px}
  header{padding:10px 12px;gap:8px}
  h1{font-size:15px}
  .month-nav span{min-width:100px;font-size:13px}
  .brand-tabs{gap:4px}
  .brand-tab{padding:4px 9px;font-size:11px}
  .legend{gap:6px}
  .legend-item{font-size:10px}
  .cards-grid{grid-template-columns:1fr}
}
</style>
</head>
<body>
<header>
  <h1>📅 Calendario</h1>
  <div class="month-nav">
    <button onclick="changeMonth(-1)">&#9664;</button>
    <span id="month-lbl">—</span>
    <button onclick="changeMonth(1)">&#9654;</button>
  </div>
  <div class="brand-tabs" id="brand-tabs"></div>
  <button class="new-brand-btn" onclick="openNewBrand()" title="Agregar nueva marca">+ Marca</button>
  <button class="gen-btn" onclick="openGenModal()" title="Generar contenido con IA">✨ Generar</button>
</header>

<!-- Modal Nueva Marca -->
<div class="overlay hidden" id="newbrand-overlay" onclick="if(event.target===this)closeNewBrand()">
  <div class="modal" style="max-width:420px">
    <div class="modal-hd">
      <h3>🏢 Nueva marca</h3>
      <button class="close-btn" onclick="closeNewBrand()">&#215;</button>
    </div>
    <div style="padding:16px;display:flex;flex-direction:column;gap:12px">
      <div>
        <label style="font-size:12px;font-weight:600;color:#64748b;display:block;margin-bottom:4px">NOMBRE DE LA MARCA</label>
        <input id="nb-name" type="text" maxlength="30" placeholder="Ej: MiMarca" style="width:100%;padding:8px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px">
      </div>
      <div>
        <label style="font-size:12px;font-weight:600;color:#64748b;display:block;margin-bottom:4px">COLOR</label>
        <div style="display:flex;gap:8px;flex-wrap:wrap" id="nb-colors">
          <span class="nb-color-opt" data-color="#6366f1" style="background:#6366f1" title="Índigo"></span>
          <span class="nb-color-opt" data-color="#0ea5e9" style="background:#0ea5e9" title="Cielo"></span>
          <span class="nb-color-opt" data-color="#10b981" style="background:#10b981" title="Esmeralda"></span>
          <span class="nb-color-opt" data-color="#f59e0b" style="background:#f59e0b" title="Ámbar"></span>
          <span class="nb-color-opt" data-color="#ef4444" style="background:#ef4444" title="Rojo"></span>
          <span class="nb-color-opt" data-color="#ec4899" style="background:#ec4899" title="Rosa"></span>
          <span class="nb-color-opt" data-color="#8b5cf6" style="background:#8b5cf6" title="Violeta"></span>
          <span class="nb-color-opt" data-color="#14b8a6" style="background:#14b8a6" title="Teal"></span>
        </div>
        <input id="nb-color-val" type="hidden" value="#6366f1">
      </div>
      <div>
        <label style="font-size:12px;font-weight:600;color:#64748b;display:block;margin-bottom:4px">BRIEF / DESCRIPCIÓN <span style="font-weight:400">(para que la IA genere contenido)</span></label>
        <textarea id="nb-brief" rows="5" placeholder="Describí la marca: qué hace, a quién le habla, tono, pilares de contenido, hashtags, web..." style="width:100%;padding:8px;border:1px solid #e2e8f0;border-radius:8px;font-size:12px;resize:vertical;font-family:inherit"></textarea>
      </div>
      <div id="nb-status" style="font-size:12px;color:#64748b;min-height:16px;text-align:center"></div>
      <button id="nb-submit" onclick="createBrand()" style="background:#1e293b;color:white;border:none;padding:10px 0;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer">Crear marca</button>
    </div>
  </div>
</div>

<!-- Modal Generación IA -->
<div class="overlay hidden" id="gen-overlay" onclick="if(event.target===this)closeGenModal()">
  <div class="modal" style="max-width:440px">
    <div class="modal-hd">
      <h3>✨ Generar contenido con IA</h3>
      <button class="close-btn" onclick="closeGenModal()">&#215;</button>
    </div>
    <div style="padding:16px;display:flex;flex-direction:column;gap:12px">
      <div>
        <label style="font-size:12px;font-weight:600;color:#64748b;display:block;margin-bottom:4px">MARCA</label>
        <select id="gen-brand" style="width:100%;padding:8px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px">
          <option value="">— Seleccioná —</option>
          <option value="EBDS">EBDS</option>
          <option value="Sibila">Sibila</option>
          <option value="ZoWeAre">ZoWeAre</option>
          <option value="Tivenos">Tivenos</option>
          <option value="BHU">BHU</option>
        </select>
      </div>
      <div>
        <label style="font-size:12px;font-weight:600;color:#64748b;display:block;margin-bottom:4px">MES</label>
        <input type="month" id="gen-month" style="width:100%;padding:8px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px">
      </div>
      <div>
        <label style="font-size:12px;font-weight:600;color:#64748b;display:block;margin-bottom:4px">TIPO DE CONTENIDO</label>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px" id="gen-types">
          <label class="gen-type-opt"><input type="radio" name="gen-type" value="social" checked> 📱 Posts sociales</label>
          <label class="gen-type-opt"><input type="radio" name="gen-type" value="linkedin"> 💼 LinkedIn</label>
          <label class="gen-type-opt"><input type="radio" name="gen-type" value="blog"> 📄 Blog</label>
          <label class="gen-type-opt"><input type="radio" name="gen-type" value="email"> ✉️ Email</label>
        </div>
      </div>
      <div>
        <label style="font-size:12px;font-weight:600;color:#64748b;display:block;margin-bottom:4px">INSTRUCCIONES EXTRA <span style="font-weight:400">(opcional)</span></label>
        <textarea id="gen-prompt" rows="3" placeholder="Ej: Esta semana hay una promo de 30% de descuento. Incluir urgencia y CTA a la landing de descuento." style="width:100%;padding:8px;border:1px solid #e2e8f0;border-radius:8px;font-size:12px;resize:vertical;font-family:inherit"></textarea>
      </div>
      <div id="gen-status" style="font-size:12px;color:#64748b;min-height:18px;text-align:center"></div>
      <button id="gen-submit-btn" onclick="runGenerate()" style="background:#7c3aed;color:white;border:none;padding:10px 0;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;transition:opacity .2s">✨ Generar ahora</button>
    </div>
  </div>
</div>
<div class="main">
  <div class="legend" id="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#16a34a"></div>Reel</div>
    <div class="legend-item"><div class="legend-dot" style="background:#9333ea"></div>Carrusel</div>
    <div class="legend-item"><div class="legend-dot" style="background:#2563eb"></div>Post</div>
    <div class="legend-item"><div class="legend-dot" style="background:#db2777"></div>Story</div>
    <div class="legend-item"><div class="legend-dot" style="background:#0284c7"></div>LinkedIn</div>
    <div class="legend-item"><div class="legend-dot" style="background:#ea580c"></div>Blog</div>
    <div class="legend-item"><div class="legend-dot" style="background:#dc2626"></div>Email</div>
    <div class="legend-item" style="margin-left:8px"><div class="chip-status" style="background:#22c55e;width:8px;height:8px;border-radius:50%"></div> Aprobado</div>
    <div class="legend-item"><div class="chip-status" style="background:#f59e0b;width:8px;height:8px;border-radius:50%"></div> Pendiente</div>
    <div class="legend-item"><div class="chip-status" style="background:#ef4444;width:8px;height:8px;border-radius:50%"></div> Con cambios</div>
  </div>
  <div class="cal-scroll">
    <div class="cal-wrap" style="min-width:520px">
      <div class="cal-header">
        <div></div><div>Lunes</div><div>Martes</div><div>Miércoles</div><div>Jueves</div><div>Viernes</div>
      </div>
      <div class="cal-body" id="cal-body"></div>
    </div>
  </div>
  <div class="agenda" id="agenda"></div>
  <div class="extras" id="extras"></div>
</div>
<div class="overlay hidden" id="overlay">
  <div class="modal" id="modal">
    <div class="modal-hd">
      <h3 id="modal-title"></h3>
      <button class="close-btn" onclick="closeModal()">&#215;</button>
    </div>
    <div id="modal-body"></div>
  </div>
</div>
<script>
const KEY=new URLSearchParams(location.search).get(\'key\')||\'\';
// BC se carga dinámicamente desde /calendar/brands; defaults como fallback
let BC={EBDS:\'#1e3a8a\',Sibila:\'#7c3aed\',ZoWeAre:\'#059669\',Tivenos:\'#dc2626\',BHU:\'#d97706\'};
const TC={Reel:\'#16a34a\',Carrusel:\'#9333ea\',Post:\'#2563eb\',Story:\'#db2777\',LinkedIn:\'#0284c7\',Blog:\'#ea580c\',Email:\'#dc2626\'};
const TI={Reel:\'\\uD83C\\uDFA5\',Carrusel:\'\\uD83D\\uDCF1\',Post:\'\\uD83D\\uDCDD\',Story:\'\\uD83D\\uDCF8\',LinkedIn:\'\\uD83D\\uDCBC\',Blog:\'\\uD83D\\uDCC4\',Email:\'\\u2709\\uFE0F\'};
const SC={pendiente:\'#f59e0b\',aprobado:\'#22c55e\',con_cambios:\'#ef4444\'};
const MN=[\'Enero\',\'Febrero\',\'Marzo\',\'Abril\',\'Mayo\',\'Junio\',\'Julio\',\'Agosto\',\'Septiembre\',\'Octubre\',\'Noviembre\',\'Diciembre\'];
let curMonth=\'\',data={},active=\'all\',curPost=null,designerChecks=new Set();

async function loadBrandsConfig(){
  try{
    const r=await fetch(\'/calendar/brands?key=\'+KEY);
    const d=await r.json();
    if(d.ok&&d.brands){
      Object.entries(d.brands).forEach(([b,v])=>BC[b]=v.color);
      // Actualizar select del modal Generar con marcas nuevas
      rebuildGenSelect(Object.keys(d.brands));
    }
  }catch(e){console.warn(\'loadBrandsConfig:\',e);}
}

function rebuildGenSelect(brands){
  const sel=document.getElementById(\'gen-brand\');
  if(!sel)return;
  const cur=sel.value;
  sel.innerHTML=\'<option value="">— Seleccioná —</option>\';
  brands.forEach(b=>{
    const o=document.createElement(\'option\');o.value=b;o.textContent=b;
    sel.appendChild(o);
  });
  if(cur)sel.value=cur;
}
const urlM=new URLSearchParams(location.search).get(\'month\');
const n=new Date();
curMonth=urlM||(n.getFullYear()+\'-\'+String(n.getMonth()+1).padStart(2,\'0\'));

async function load(autoAdvance){
  try{
    const r=await fetch(\'/calendar/data?key=\'+KEY+\'&month=\'+curMonth);
    const d=await r.json();
    data=d.posts||{};
    designerChecks=new Set(d.designer_checks||[]);
    const total=Object.values(data).reduce((s,a)=>s+(Array.isArray(a)?a.length:0),0);
    // Si no hay datos y no se especificó mes en la URL, avanzar automáticamente al siguiente mes (una sola vez)
    if(total===0&&!autoAdvance&&!new URLSearchParams(location.search).get(\'month\')){
      changeMonth(1,true);
      return;
    }
    renderTabs(d.brands||[]);
    renderCal();
    renderAgenda();
    renderExtras();
  }catch(e){console.error(e)}
}

function renderTabs(brands){
  const c=document.getElementById(\'brand-tabs\');
  c.innerHTML=\'\';
  const all=document.createElement(\'div\');
  all.className=\'brand-tab\';all.dataset.brand=\'all\';
  all.style.cssText=\'border-color:#1e293b;background:#1e293b;color:white\';
  all.textContent=\'Todas\';all.onclick=()=>filter(\'all\');c.appendChild(all);
  brands.forEach(b=>{
    const t=document.createElement(\'div\');
    t.className=\'brand-tab\';t.dataset.brand=b;
    t.style.cssText=\'border-color:\'+(BC[b]||\'#666\')+\';color:\'+(BC[b]||\'#666\');
    t.textContent=b;t.onclick=()=>filter(b);c.appendChild(t);
  });
}

function filter(b){
  active=b;
  document.querySelectorAll(\'.brand-tab\').forEach(t=>{
    const tb=t.dataset.brand,col=tb===\'all\'?\'#1e293b\':(BC[tb]||\'#666\');
    if(tb===b){t.style.background=col;t.style.color=\'white\';}
    else{t.style.background=\'white\';t.style.color=col;}
  });
  renderCal();renderAgenda();renderExtras();
}

function monthDates(){
  const[y,m]=curMonth.split(\'-\').map(Number);
  const dates=[];
  const last=new Date(y,m,0).getDate();
  for(let d=1;d<=last;d++){
    const dt2=new Date(y,m-1,d);
    if(dt2.getDay()>=1&&dt2.getDay()<=5)dates.push(dt2);
  }
  return dates;
}

function fmt(d){return d.getFullYear()+\'-\'+String(d.getMonth()+1).padStart(2,\'0\')+\'-\'+String(d.getDate()).padStart(2,\'0\')}

function renderCal(){
  const[y,m]=curMonth.split(\'-\').map(Number);
  document.getElementById(\'month-lbl\').textContent=MN[m-1]+\' \'+y;
  const body=document.getElementById(\'cal-body\');
  body.innerHTML=\'\';
  const dates=monthDates();
  // Agrupar por semana real (lunes de cada semana), no por Math.ceil(dia/7) —
  // eso rompía el grid cuando el mes no arranca en lunes (ej: si el 1 cae martes,
  // el lunes 7 quedaba agrupado con el martes 1 en la misma fila).
  const weekKeys=[];
  const weeks={};
  dates.forEach(d=>{
    const dow0=d.getDay();
    const diff=dow0===0?-6:1-dow0;
    const monDate=new Date(d.getFullYear(),d.getMonth(),d.getDate()+diff);
    const wk=fmt(monDate);
    if(!weeks[wk]){weeks[wk]={mon:monDate,days:{}};weekKeys.push(wk);}
    weeks[wk].days[dow0]=d;
  });
  weekKeys.forEach((wk,wi)=>{
    const w=weeks[wk];
    const lbl=document.createElement(\'div\');lbl.className=\'week-lbl\';lbl.textContent=\'S\'+(wi+1);
    body.appendChild(lbl);
    for(let dow=1;dow<=5;dow++){
      const cell=document.createElement(\'div\');cell.className=\'day-cell\';
      if(w.days[dow]){
        const d=w.days[dow];const ds=fmt(d);
        const dn=document.createElement(\'div\');dn.className=\'day-num\';dn.textContent=d.getDate();
        cell.appendChild(dn);
        getForDate(ds).forEach(p=>cell.appendChild(mkChip(p)));
        getExtrasForDate(ds).forEach(p=>cell.appendChild(mkMiniChip(p)));
        const ab=document.createElement(\'div\');ab.className=\'add-btn\';ab.innerHTML=\'+\';ab.title=\'Agregar\';ab.onclick=()=>openNew(ds);cell.appendChild(ab);
      }else{
        // Celda vacía: calcular qué día sería, usando el lunes real de esta semana.
        // Solo mostrar el número si cae dentro del mes que se está viendo (m) —
        // los días de relleno del mes anterior/siguiente quedan en blanco.
        cell.className+=\' inactive\';
        const emptyDate=new Date(w.mon.getTime()+(dow-1)*86400000);
        if(emptyDate.getMonth()===m-1){
          const dn=document.createElement(\'div\');dn.className=\'day-num\';dn.textContent=emptyDate.getDate();
          cell.appendChild(dn);
        }
      }
      body.appendChild(cell);
    }
  });
}

function getForDate(ds){
  const posts=[];
  for(const[brand,bp] of Object.entries(data)){
    if(active!==\'all\'&&brand!==active)continue;
    if(!Array.isArray(bp))continue;
    bp.filter(p=>p.date===ds&&![\'LinkedIn\',\'Blog\',\'Email\'].includes(p.type)).forEach(p=>posts.push({...p,brand}));
  }
  return posts;
}

function getExtrasForDate(ds){
  const posts=[];
  for(const[brand,bp] of Object.entries(data)){
    if(active!==\'all\'&&brand!==active)continue;
    if(!Array.isArray(bp))continue;
    bp.filter(p=>p.date===ds&&[\'LinkedIn\',\'Blog\',\'Email\'].includes(p.type)).forEach(p=>posts.push({...p,brand}));
  }
  return posts;
}

function mkMiniChip(p){
  const tc=TC[p.type]||\'#666\';
  const chip=document.createElement(\'div\');chip.className=\'chip-mini\';
  chip.style.background=tc+\'15\';chip.style.borderColor=tc+\'55\';
  const icon=TI[p.type]||\'\'
  const pKey=\'pRef_\'+p.id.replace(/[^a-z0-9]/gi,\'_\');window[pKey]={...p};
  chip.innerHTML=\'<span>\'+icon+\'</span>\'
    +\'<span class="chip-mini-lbl" style="color:\'+tc+\'">\'+p.type+\'</span>\'
    +\'<div class="chip-status" style="background:\'+(SC[p.status]||\'#94a3b8\')+\'"></div>\';
  chip.onclick=(e)=>{e.stopPropagation();openPost(p);};
  return chip;
}

function mkChip(p){
  const tc=TC[p.type]||\'#666\';const bc=BC[p.brand]||\'#888\';
  const chip=document.createElement(\'div\');chip.className=\'chip\';
  chip.style.background=tc+\'18\';chip.style.borderColor=tc+\'30\';
  const icon=TI[p.type]||\'\';
  const cpKey=\'pRef_\'+p.id.replace(/[^a-z0-9]/gi,\'_\');window[cpKey]={...p};
  const chk=designerChecks.has(p.id);
  chip.innerHTML=\'<div class="chip-dot" style="background:\'+bc+\'"></div>\'
    +\'<span class="chip-title">\'+(p.titulo||p.type)+\'</span>\'
    +\'<span class="chip-icon">\'+icon+\'</span>\'
    +\'<button class="btn-check\'+(chk?\' checked\':\'\')+\'" title="\'+(chk?\'Diseño listo ✓\':\'Marcar diseño como listo\')+\'">\'+(chk?\'✓\':\'○\')+\'</button>\'
    +\'<button class="btn-regen" style="font-size:11px;padding:1px 3px" title="Regenerar" onclick="openRegen(\'+cpKey+\',event)">🔄</button>\'
    +\'<button class="btn-del" title="Borrar" onclick="confirmDeleteChip(\'+cpKey+\',event)">✕</button>\'
    +\'<div class="chip-status" style="background:\'+(SC[p.status]||\'#94a3b8\')+\'"></div>\';
  const checkBtn=chip.querySelector(\'.btn-check\');
  if(checkBtn){checkBtn.addEventListener(\'click\',function(evt){toggleCheck(p.id,evt);});}
  chip.onclick=()=>openPost(p);return chip;
}

async function toggleCheck(postId,evt){
  evt.stopPropagation();
  try{
    const r=await fetch(\'/calendar/check-toggle?key=\'+KEY,{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({post_id:postId})});
    const d=await r.json();
    if(d.checked){designerChecks.add(postId);}else{designerChecks.delete(postId);}
    renderCal();renderAgenda();renderExtras();
  }catch(e){console.error(e);}
}

function renderExtras(){
  const c=document.getElementById(\'extras\');c.innerHTML=\'\';
  [\'LinkedIn\',\'Blog\',\'Email\'].forEach(type=>{
    const posts=[];
    for(const[brand,bp] of Object.entries(data)){
      if(active!==\'all\'&&brand!==active)continue;
      if(!Array.isArray(bp))continue;
      bp.filter(p=>p.type===type&&!p.date).forEach(p=>posts.push({...p,brand}));
    }
    if(!posts.length)return;
    const col=TC[type]||\'#666\';const icon=TI[type]||\'\';
    const h=document.createElement(\'h3\');h.innerHTML=icon+\' \'+type+\' sin fecha asignada\';h.style.color=col;
    c.appendChild(h);
    const grid=document.createElement(\'div\');grid.className=\'cards-grid\';
    posts.forEach(p=>{
      const bc=BC[p.brand]||\'#666\';const sc2=SC[p.status]||\'#94a3b8\';
      const card=document.createElement(\'div\');card.className=\'card\';
      card.style.borderLeftColor=col;
      card.innerHTML=\'<div class="card-top"><span class="card-brand" style="color:\'+bc+\'">\'+p.brand+\'</span>\'
        +\'<div style="display:flex;align-items:center;gap:6px">\'
        +\'<button class="btn-regen" title="Regenerar con IA" onclick="openRegen(pRef_\'+p.id.replace(/[^a-z0-9]/gi,\'_\')+\',event)">🔄</button>\'
        +\'<span class="status-pill" style="background:\'+sc2+\'20;color:\'+sc2+\'">\'+( p.status||\'pendiente\')+\'</span></div></div>\'
        +\'<div class="card-title">\'+(p.titulo||\'Sin título\')+\'</div>\'
        +\'<div class="card-meta">\'+(p.pilar||\'\')+\' \'+(p.objetivo?\'· \'+p.objetivo:\'\')+\'</div>\';
      // Store post ref so onclick in innerHTML can access it
      const pKey=\'pRef_\'+p.id.replace(/[^a-z0-9]/gi,\'_\');
      window[pKey]={...p};
      card.onclick=()=>openPost(p);grid.appendChild(card);
    });
    c.appendChild(grid);
  });
}

function renderAgenda(){
  const c=document.getElementById(\'agenda\');if(!c)return;
  c.innerHTML=\'\';
  const[y,m]=curMonth.split(\'-\').map(Number);
  const dates=monthDates();
  let hasAny=false;
  dates.forEach(d=>{
    const ds=fmt(d);
    const posts=getForDate(ds);
    if(!posts.length)return;
    hasAny=true;
    const block=document.createElement(\'div\');block.className=\'agenda-day\';
    const dow=[\'Dom\',\'Lun\',\'Mar\',\'Mié\',\'Jue\',\'Vie\',\'Sáb\'][d.getDay()];
    const dateDiv=document.createElement(\'div\');dateDiv.className=\'agenda-date\';
    dateDiv.textContent=dow+\' \'+d.getDate()+\'/\'+m;
    block.appendChild(dateDiv);
    posts.forEach(p=>{
      const tc=TC[p.type]||\'#666\';const bc=BC[p.brand]||\'#888\';
      const pKey=\'pRef_\'+p.id.replace(/[^a-z0-9]/gi,\'_\');window[pKey]={...p};
      const row=document.createElement(\'div\');row.className=\'agenda-row\';
      row.style.borderLeftColor=tc;
      row.innerHTML=\'<span class="agenda-type" style="color:\'+tc+\'">\'+( TI[p.type]||\'\')+\' \'+p.type+\'</span>\'
        +\'<span class="agenda-brand" style="color:\'+bc+\'">\'+p.brand+\'</span>\'
        +\'<span class="agenda-title">\'+(p.titulo||\'\')+\'</span>\'
        +\'<div class="chip-status" style="background:\'+(SC[p.status]||\'#94a3b8\')+\';width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-right:4px"></div>\'
        +\'<button class="btn-regen" style="font-size:14px;padding:2px 4px;flex-shrink:0" title="Regenerar" onclick="event.stopPropagation();openRegen(\'+pKey+\',event)">🔄</button>\';
      row.onclick=()=>openPost(p);
      block.appendChild(row);
    });
    c.appendChild(block);
  });
  if(!hasAny){c.innerHTML=\'<div class="empty-msg">Sin contenido para este mes</div>\';}
}

function openPost(p){
  curPost={...p};
  const tc=TC[p.type]||\'#666\';const bc2=BC[p.brand]||\'#666\';
  document.getElementById(\'modal-title\').innerHTML=
    \'<span style="color:\'+bc2+\'">\'+p.brand+\'</span> &middot; \'
    +\'<span style="color:\'+tc+\'">\'+( TI[p.type]||\'\')+\' \'+p.type+\'</span>\'
    +(p.date?\' &middot; <span style="color:#94a3b8">\'+p.date+\'</span>\':\'\'  );
  const typeOpts=[\'Reel\',\'Post\',\'Carrusel\',\'Story\',\'LinkedIn\',\'Blog\',\'Email\'];
  const typeIcons={Reel:\'🎥\',Post:\'📝\',Carrusel:\'📱\',Story:\'📸\',LinkedIn:\'💼\',Blog:\'📄\',Email:\'✉️\'};
  const typeSelectOpts=typeOpts.map(t=>\'<option value="\'+t+\'"\'+(p.type===t?\' selected\':\'\')+\'>\'+( typeIcons[t]||\'\')+\' \'+t+\'</option>\').join(\'\');
  document.getElementById(\'modal-body\').innerHTML=
    \'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">\'
    +\'<div><label>Tipo de formato</label><select id="e-type" onchange="updateModalHeader()">\'+typeSelectOpts+\'</select></div>\'
    +\'<div><label>&#128197; Fecha (cambi&aacute; para mover)</label><input type="date" id="e-date"></div>\'
    +\'</div>\'
    +\'<label>T&iacute;tulo / Tema</label><input id="e-titulo" value="\'+esc(p.titulo||\'\')+\'">\'
    +\'<label>Pilar de contenido</label><input id="e-pilar" value="\'+esc(p.pilar||\'\')+\'">\'
    +\'<label>Objetivo</label><input id="e-objetivo" value="\'+esc(p.objetivo||\'\')+\'">\'
    +\'<label>&#127912; Texto de imagen / Descripci&oacute;n de pieza</label><textarea id="e-texto-imagen" style="min-height:90px;font-family:monospace;font-size:12px">\'+esc(p.texto_imagen||\'\')+\'</textarea>\'
    +\'<label>Copy (caption para redes)</label><textarea id="e-copy">\'+esc(p.copy||\'\')+\'</textarea>\'
    +(p.hashtags!==undefined?\'<label>Hashtags</label><input id="e-hashtags" value="\'+esc(p.hashtags||\'\')+\'">\':\'\')
    +\'<label>Estado</label><select id="e-status">\'
    +\'<option value="pendiente"\'+(p.status===\'pendiente\'?\' selected\':\'\')+\'>&#9203; Pendiente</option>\'
    +\'<option value="aprobado"\'+(p.status===\'aprobado\'?\' selected\':\'\')+\'>&#10003; Aprobado</option>\'
    +\'<option value="con_cambios"\'+(p.status===\'con_cambios\'?\' selected\':\'\')+\'>&#8635; Con cambios</option>\'
    +\'</select>\'
    +\'<label>Comentarios</label><textarea id="e-comments" style="min-height:60px">\'+esc(p.comments||\'\')+\'</textarea>\'
    +\'<div class="modal-actions"><button class="btn-save" onclick="savePost()">&#128190; Guardar</button>\'
    +\'<button class="btn-cancel" onclick="closeModal()">Cancelar</button>\'
    +\'<button class="btn-delete" onclick="deletePost()">&#128465; Borrar</button></div>\';
  document.getElementById(\'overlay\').classList.remove(\'hidden\');
  // Fix: input[type=date] value must be set via JS after innerHTML (HTML attribute is ignored by some browsers)
  const dateEl=document.getElementById(\'e-date\');
  if(dateEl)dateEl.value=p.date||\'\';
}

function openNew(ds){
  openPost({id:\'new-\'+Date.now(),brand:active!==\'all\'?active:\'EBDS\',date:ds,type:\'Post\',titulo:\'\',pilar:\'\',objetivo:\'\',texto_imagen:\'\',copy:\'\',hashtags:\'\',status:\'pendiente\',comments:\'\'});
}

function updateModalHeader(){
  if(!curPost)return;
  const t=document.getElementById(\'e-type\');
  if(!t)return;
  const typeIcons2={Reel:\'🎥\',Post:\'📝\',Carrusel:\'📱\',Story:\'📸\',LinkedIn:\'💼\',Blog:\'📄\',Email:\'✉️\'};
  const bc2=BC[curPost.brand]||\'#666\';const tc2=TC[t.value]||\'#666\';
  document.getElementById(\'modal-title\').innerHTML=
    \'<span style="color:\'+bc2+\'">\'+curPost.brand+\'</span> &middot; \'
    +\'<span style="color:\'+tc2+\'">\'+( typeIcons2[t.value]||\'\')+\' \'+t.value+\'</span>\';
}

async function savePost(){
  const p={...curPost,
    type:document.getElementById(\'e-type\').value,
    date:document.getElementById(\'e-date\').value,
    titulo:document.getElementById(\'e-titulo\').value,
    pilar:document.getElementById(\'e-pilar\').value,
    objetivo:document.getElementById(\'e-objetivo\').value,
    texto_imagen:document.getElementById(\'e-texto-imagen\').value,
    copy:document.getElementById(\'e-copy\').value,
    status:document.getElementById(\'e-status\').value,
    comments:document.getElementById(\'e-comments\').value
  };
  const eh=document.getElementById(\'e-hashtags\');if(eh)p.hashtags=eh.value;
  const btn=document.querySelector(\'.btn-save\');
  const orig=btn?btn.innerHTML:\'\';
  if(btn){btn.disabled=true;btn.style.opacity=\'0.7\';btn.innerHTML=\'⏳ Guardando...\';}
  try{
    const ctrl=new AbortController();
    const tid=setTimeout(()=>ctrl.abort(),25000);
    const r=await fetch(\'/calendar/save?key=\'+KEY,{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({month:curMonth,post:p}),signal:ctrl.signal});
    clearTimeout(tid);
    if(r.ok){
      if(!data[p.brand])data[p.brand]=[];
      const idx=data[p.brand].findIndex(x=>x.id===p.id);
      if(idx>=0)data[p.brand][idx]=p;else data[p.brand].push(p);
      if(btn)btn.innerHTML=\'✅ Guardado\';
      setTimeout(()=>{closeModal();renderCal();renderAgenda();renderExtras();},350);
    }else{
      if(btn){btn.disabled=false;btn.style.opacity=\'1\';btn.innerHTML=orig;}
      alert(\'Error al guardar. Intentá de nuevo.\');
    }
  }catch(e){
    if(btn){btn.disabled=false;btn.style.opacity=\'1\';btn.innerHTML=orig;}
    if(e.name===\'AbortError\')alert(\'Tardó demasiado. El cambio puede haberse guardado — cerrá y verificá antes de reintentar.\');
    else alert(\'Error de conexión al guardar.\');
  }
}

async function deletePost(){
  if(!curPost)return;
  if(!confirm(\'¿Borrar este post? Esta acción no se puede deshacer.\'))return;
  try{
    const r=await fetch(\'/calendar/delete?key=\'+KEY,{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({month:curMonth,post_id:curPost.id,brand:curPost.brand})});
    if(r.ok){
      if(data[curPost.brand])data[curPost.brand]=data[curPost.brand].filter(x=>x.id!==curPost.id);
      closeModal();renderCal();renderAgenda();renderExtras();
    }else{alert(\'Error al borrar\');}
  }catch(e){alert(\'Error al borrar\');}
}

async function confirmDeleteChip(p,e){
  e.stopPropagation();
  if(!confirm(\'¿Borrar "\'+(p.titulo||p.type)+\'"?\'))return;
  try{
    const r=await fetch(\'/calendar/delete?key=\'+KEY,{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({month:curMonth,post_id:p.id,brand:p.brand})});
    if(r.ok){
      if(data[p.brand])data[p.brand]=data[p.brand].filter(x=>x.id!==p.id);
      renderCal();renderAgenda();renderExtras();
    }
  }catch(e){alert(\'Error al borrar\');}
}

function closeModal(){document.getElementById(\'overlay\').classList.add(\'hidden\');}
document.getElementById(\'overlay\').onclick=e=>{if(e.target.id===\'overlay\')closeModal();};

// ── Regenerate modal ────────────────────────────────────────────────────
let regenPost=null;
function openRegen(p,e){
  e.stopPropagation();
  regenPost={...p};
  const tc=TC[p.type]||\'#6366f1\';
  document.getElementById(\'regen-title\').textContent=\'🔄 Regenerar: \'+(p.titulo||p.type)+\' · \'+(p.date||\'\');
  document.getElementById(\'regen-subtitle\').textContent=p.brand+\' · \'+(p.type||\'\')+(p.pilar?\' · \'+p.pilar:\'\');
  document.getElementById(\'regen-instr\').value=\'\';
  document.getElementById(\'regen-go\').disabled=false;
  document.getElementById(\'regen-go\').textContent=\'🔄 Regenerar\';
  document.getElementById(\'regen-spinner\').classList.remove(\'show\');
  document.getElementById(\'regen-overlay\').classList.add(\'show\');
}
function closeRegen(){document.getElementById(\'regen-overlay\').classList.remove(\'show\');}
document.addEventListener(\'click\',function(e){if(e.target.id===\'regen-overlay\')closeRegen();});

async function doRegen(){
  if(!regenPost)return;
  const instr=document.getElementById(\'regen-instr\').value.trim();
  const btn=document.getElementById(\'regen-go\');
  btn.disabled=true;btn.textContent=\'Generando...\';
  document.getElementById(\'regen-spinner\').classList.add(\'show\');
  try{
    const r=await fetch(\'/calendar/regenerate-post?key=\'+KEY,{
      method:\'POST\',
      headers:{\'Content-Type\':\'application/json\'},
      body:JSON.stringify({month:curMonth,post_id:regenPost.id,instruction:instr})
    });
    if(r.ok){
      const newPost=await r.json();
      // Update local data
      if(data[newPost.brand]){
        const idx=data[newPost.brand].findIndex(x=>x.id===newPost.id);
        if(idx>=0)data[newPost.brand][idx]=newPost;
      }
      closeRegen();
      renderCal();renderExtras();
      // Flash success
      btn.textContent=\'✅ Listo\';
    } else {
      btn.textContent=\'❌ Error — reintenta\';btn.disabled=false;
    }
  }catch(e){
    btn.textContent=\'❌ Error de red\';btn.disabled=false;
  }
  document.getElementById(\'regen-spinner\').classList.remove(\'show\');
}

function changeMonth(d,autoAdvance){
  const[y,m]=curMonth.split(\'-\').map(Number);
  const nd=new Date(y,m-1+d,1);
  curMonth=nd.getFullYear()+\'-\'+String(nd.getMonth()+1).padStart(2,\'0\');
  const url=new URL(location);url.searchParams.set(\'month\',curMonth);history.pushState({},\'\',url);
  load(autoAdvance);
}

function esc(s){return String(s).replace(/&/g,\'&amp;\').replace(/</g,\'&lt;\').replace(/>/g,\'&gt;\').replace(/"/g,\'&quot;\').replace(/\'/g,\'&#39;\');}

if(document.readyState===\'loading\'){
  document.addEventListener(\'DOMContentLoaded\',()=>{loadBrandsConfig();load();});
}else{
  loadBrandsConfig();load();
}

// ===== MODAL NUEVA MARCA =====
let nbSelectedColor=\'#6366f1\';

function openNewBrand(){
  document.getElementById(\'nb-name\').value=\'\';
  document.getElementById(\'nb-brief\').value=\'\';
  document.getElementById(\'nb-status\').textContent=\'\';
  document.getElementById(\'nb-submit\').disabled=false;
  document.getElementById(\'nb-submit\').textContent=\'Crear marca\';
  // Seleccionar primer color por defecto
  document.querySelectorAll(\'.nb-color-opt\').forEach((el,i)=>{
    el.classList.toggle(\'selected\',i===0);
    el.onclick=()=>{
      document.querySelectorAll(\'.nb-color-opt\').forEach(x=>x.classList.remove(\'selected\'));
      el.classList.add(\'selected\');
      nbSelectedColor=el.dataset.color;
      document.getElementById(\'nb-color-val\').value=nbSelectedColor;
    };
  });
  nbSelectedColor=\'#6366f1\';
  document.getElementById(\'newbrand-overlay\').classList.remove(\'hidden\');
  setTimeout(()=>document.getElementById(\'nb-name\').focus(),100);
}

function closeNewBrand(){
  document.getElementById(\'newbrand-overlay\').classList.add(\'hidden\');
}

async function createBrand(){
  const name=document.getElementById(\'nb-name\').value.trim();
  const color=document.getElementById(\'nb-color-val\').value||nbSelectedColor;
  const brief=document.getElementById(\'nb-brief\').value.trim();
  const status=document.getElementById(\'nb-status\');
  const btn=document.getElementById(\'nb-submit\');

  if(!name){alert(\'Ingresá el nombre de la marca\');return;}

  btn.disabled=true;btn.textContent=\'Creando...\';
  status.style.color=\'#64748b\';status.textContent=\'Creando tarea en ClickUp...\';

  try{
    const r=await fetch(\'/calendar/brands?key=\'+KEY,{
      method:\'POST\',
      headers:{\'Content-Type\':\'application/json\'},
      body:JSON.stringify({name,color,brief})
    });
    const d=await r.json();
    if(d.ok){
      BC[name]=color;
      status.style.color=\'#16a34a\';
      status.textContent=\'✅ Marca "\'+(name)+\'" creada. Recargando...\';
      // Agregar al select de Generar
      const sel=document.getElementById(\'gen-brand\');
      if(sel){const o=document.createElement(\'option\');o.value=name;o.textContent=name;sel.appendChild(o);}
      setTimeout(()=>{closeNewBrand();load();},800);
    } else {
      status.style.color=\'#ef4444\';
      status.textContent=\'❌ \'+(d.error||\'Error\');
      btn.disabled=false;btn.textContent=\'Crear marca\';
    }
  }catch(e){
    status.style.color=\'#ef4444\';status.textContent=\'❌ Error de red: \'+e.message;
    btn.disabled=false;btn.textContent=\'Crear marca\';
  }
}

// ===== MODAL GENERACIÓN IA =====
function openGenModal(){
  const ov=document.getElementById(\'gen-overlay\');
  // Pre-seleccionar marca activa si hay una
  if(active&&active!==\'all\'){
    const sel=document.getElementById(\'gen-brand\');
    if(sel)sel.value=active;
  }
  // Pre-seleccionar mes actual
  document.getElementById(\'gen-month\').value=curMonth;
  document.getElementById(\'gen-status\').textContent=\'\';
  ov.classList.remove(\'hidden\');
}

function closeGenModal(){
  document.getElementById(\'gen-overlay\').classList.add(\'hidden\');
}

async function runGenerate(){
  const brand=document.getElementById(\'gen-brand\').value;
  const month=document.getElementById(\'gen-month\').value;
  const type=document.querySelector(\'input[name="gen-type"]:checked\')?.value||\'social\';
  const prompt=document.getElementById(\'gen-prompt\').value.trim();

  if(!brand){alert(\'Seleccioná una marca\');return;}
  if(!month){alert(\'Seleccioná el mes\');return;}

  const btn=document.getElementById(\'gen-submit-btn\');
  const status=document.getElementById(\'gen-status\');
  btn.disabled=true;btn.style.opacity=\'0.6\';
  btn.textContent=\'⏳ Generando... (puede tardar 20-25s)\';
  status.textContent=\'\';

  try{
    const ctrl=new AbortController();
    const tid=setTimeout(()=>ctrl.abort(),29000);
    const r=await fetch(\'/calendar/generate-web?key=\'+KEY,{
      method:\'POST\',
      headers:{\'Content-Type\':\'application/json\'},
      body:JSON.stringify({brand,month,type,prompt}),
      signal:ctrl.signal
    });
    clearTimeout(tid);
    const d=await r.json();
    if(d.ok){
      status.style.color=\'#16a34a\';
      status.textContent=\'✅ \'+d.count+\' piezas generadas para \'+brand+\'. Recargando...\';
      setTimeout(()=>{closeGenModal();load();},900);
    } else {
      status.style.color=\'#ef4444\';
      status.textContent=\'❌ \'+( d.error||\'Error desconocido\');
      btn.disabled=false;btn.style.opacity=\'1\';btn.textContent=\'✨ Generar ahora\';
    }
  }catch(e){
    const msg=e.name===\'AbortError\'?\'Tardó demasiado — el servidor puede estar generando. Esperá 30s y recargá el calendario.\':\'Error de red: \'+e.message;
    status.style.color=\'#f59e0b\';
    status.textContent=\'⚠️ \'+msg;
    btn.disabled=false;btn.style.opacity=\'1\';btn.textContent=\'✨ Generar ahora\';
  }
}
</script>

<div class="regen-overlay" id="regen-overlay">
  <div class="regen-modal">
    <h3 id="regen-title">Regenerar post</h3>
    <p id="regen-subtitle" style="font-weight:500;color:#475569;margin-bottom:4px"></p>
    <p>Dejá en blanco para una versión diferente automática, o escribí una instrucción:</p>
    <textarea id="regen-instr" placeholder="Ej: enfocado en casos de éxito, tono más emocional, hablando del precio..."></textarea>
    <div class="regen-spinner" id="regen-spinner">⏳</div>
    <div class="regen-actions">
      <button class="btn-regen-go" id="regen-go" onclick="doRegen()">🔄 Regenerar</button>
      <button class="btn-cancel" onclick="closeRegen()">Cancelar</button>
    </div>
  </div>
</div>

</body>
</html>'''


# --- Flask routes ---
@app.route('/', methods=['GET'])
def health():
    return Response('Marketing Agent Bot running!', status=200)

@app.route('/debug/zoho-ebds')
def debug_zoho_ebds():
    """Testea conexión EBDS CRM y muestra estructura de datos."""
    out = {}
    try:
        # Test token
        token = zoho_get_token('ebds')
        out['token_ok'] = bool(token)
        # Primeros 3 Leads
        leads = zoho_get('Leads', {'per_page': 3, 'fields': 'Lead_Status,Lead_Source,Created_Time,Last_Name,Email'}, client='ebds')
        out['leads_sample'] = leads.get('data', [])
        out['leads_fields'] = list(leads.get('data', [{}])[0].keys()) if leads.get('data') else []
        # Primeros 3 Deals
        deals = zoho_get('Deals', {'per_page': 3}, client='ebds')
        out['deals_sample_fields'] = list(deals.get('data', [{}])[0].keys()) if deals.get('data') else []
        out['deals_stages_sample'] = [d.get('Stage') for d in deals.get('data', [])]
    except Exception as e:
        out['error'] = str(e)
    return Response(json.dumps(out, indent=2, ensure_ascii=False), mimetype='application/json')

@app.route('/debug/validar')
def debug_validar():
    """Diagnostica el check_validar: qué tareas hay en cada workspace."""
    out = {}
    for ws_id, ws_info in WORKSPACES.items():
        ws_result = {'name': ws_info['name'], 'tasks': [], 'error': None}
        try:
            # Intentar con statuses[]=validar
            r1 = cu_get(f'team/{ws_id}/task?statuses[]=validar&subtasks=true')
            ws_result['tasks_in_validar'] = len(r1.get('tasks', []))
            ws_result['sample'] = [
                {'id': t['id'], 'name': t['name'][:50],
                 'status': t.get('status', {}).get('status', '?'),
                 'assignees': [a.get('email', '') for a in t.get('assignees', [])]}
                for t in r1.get('tasks', [])[:5]
            ]
            # También traer primeras 5 tareas sin filtro de status para verificar que el workspace es correcto
            r2 = cu_get(f'team/{ws_id}/task?subtasks=true&page=0')
            ws_result['total_tasks_sample'] = [
                {'name': t['name'][:40], 'status': t.get('status', {}).get('status', '?')}
                for t in r2.get('tasks', [])[:5]
            ]
        except Exception as e:
            ws_result['error'] = str(e)
        out[ws_id] = ws_result
    out['sofia_email_filter'] = SOFIA_CLICKUP_EMAIL
    out['notified_count'] = len(read_state().get('notified_validar_tasks', []))
    return Response(json.dumps(out, indent=2, ensure_ascii=False), mimetype='application/json')

@app.route('/debug/zoho-deal-fields')
def debug_zoho_deal_fields():
    """Muestra todos los campos de un deal real para identificar nombre de campo 'fecha matriculado'."""
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return Response('Unauthorized', status=401)
    try:
        # Fetch one deal with all fields
        raw = zoho_get('Deals', {'per_page': 1})
        sample = raw.get('data', [{}])[0]
        # Also try the Zoho fields metadata
        out = {
            'sample_deal_all_fields': sample,
            'date_like_fields': {k: v for k, v in sample.items()
                                 if v and ('date' in k.lower() or 'fecha' in k.lower()
                                           or 'matric' in k.lower() or 'inscri' in k.lower())},
            'all_field_names': sorted(sample.keys()),
        }
        # Fetch matriculado deals with the key fields we need
        matric = _zoho_get_all('Deals', {
            'fields': 'Stage,Unidad_de_Negocio,Instituci_n,Created_Time,Modified_Time,Fecha_Matriculado,Closing_Date',
            'criteria': "(Stage:equals:8. Validado para facturar comisión)"
        }, max_pages=1)
        if not matric:
            matric = _zoho_get_all('Deals', {
                'fields': 'Stage,Unidad_de_Negocio,Instituci_n,Created_Time,Modified_Time,Fecha_Matriculado,Closing_Date',
                'criteria': "(Stage:equals:6. Inscrito)"
            }, max_pages=1)
        out['sample_matriculado'] = matric[:5] if matric else []
        # Also show unique Instituci_n values from all deals
        all_deals_inst = _zoho_get_all('Deals', {'fields': 'Stage,Instituci_n,Fecha_Matriculado'}, max_pages=1)
        out['unique_instituciones'] = list({d.get('Instituci_n','') for d in all_deals_inst if d.get('Instituci_n')})[:20]
        out['matriculado_count_all'] = sum(1 for d in all_deals_inst if d.get('Fecha_Matriculado'))
        return Response(json.dumps(out, indent=2, ensure_ascii=False, default=str), mimetype='application/json')
    except Exception as e:
        return Response(json.dumps({'error': str(e)}), mimetype='application/json')


@app.route('/debug/paid-media-raw')
def debug_paid_media_raw():
    """Muestra datos crudos de Meta Ads y CRM BHU para diagnóstico."""
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return Response('Unauthorized', status=401)
    month_param = request.args.get('month', '')
    today = dt.date.today()
    if month_param and len(month_param) == 7:
        try:
            yr, mo = int(month_param[:4]), int(month_param[5:])
            if (yr, mo) < (today.year, today.month):
                import calendar as _cal
                month_date = dt.date(yr, mo, _cal.monthrange(yr, mo)[1])
            else:
                month_date = today
        except Exception:
            month_date = today
    else:
        month_date = today

    out = {'month_date': str(month_date), 'since': str(month_date.replace(day=1)), 'until': str(min(month_date, today))}

    # Meta raw
    try:
        rows = fetch_meta_monthly(is_ebds=False, month_date=month_date)
        out['meta_rows_count'] = len(rows)
        out['meta_campaigns'] = list({r.get('campaign_name','?') for r in rows})
        out['meta_sample'] = [
            {'campaign': r.get('campaign_name',''), 'adset': r.get('adset_name',''),
             'spend': r.get('spend'), 'impressions': r.get('impressions'),
             'leads': _leads(r), 'actions': r.get('actions',[])}
            for r in rows[:5]
        ]
        out['meta_total_leads'] = sum(_leads(r) for r in rows)
        out['meta_total_spend'] = sum(float(r.get('spend',0)) for r in rows)
    except Exception as e:
        out['meta_error'] = str(e)

    # CRM raw
    try:
        crm = zoho_crm_funnel()
        out['crm_funnel'] = crm.get('funnel', {})
        out['crm_stages_raw'] = crm.get('stages_raw', {})
        out['crm_deals_total'] = crm.get('deals_total', 0)
        out['crm_ventas_mes'] = crm.get('ventas_mes', '?')
    except Exception as e:
        out['crm_error'] = str(e)

    return Response(json.dumps(out, indent=2, ensure_ascii=False), mimetype='application/json')


@app.route('/debug')
def debug_route():
    results = {}
    # Test ClickUp read
    try:
        task = cu_get(f'task/{STATE_TASK_ID}')
        results['clickup_read'] = 'ok — ' + str(task.get('name','?'))[:40]
    except Exception as e:
        results['clickup_read'] = f'ERROR: {e}'
    # Test ClickUp write — read state and write it back unchanged (non-destructive)
    try:
        task = cu_get(f'task/{STATE_TASK_ID}')
        existing_desc = task.get('description', '') or ''
        cu_put(f'task/{STATE_TASK_ID}', {'markdown_description': existing_desc})
        results['clickup_write'] = 'ok'
    except Exception as e:
        results['clickup_write'] = f'ERROR: {e}'
    # Test Telegram
    try:
        http_req(f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe')
        results['telegram'] = 'ok'
    except Exception as e:
        results['telegram'] = f'ERROR: {e}'
    # Token hints (first/last 4 chars only)
    cu_tok = CLICKUP_TOKEN
    tg_tok = TELEGRAM_TOKEN
    results['clickup_token_hint'] = f'{cu_tok[:6]}...{cu_tok[-4:]}' if len(cu_tok) > 10 else 'short?'
    results['telegram_token_hint'] = f'{tg_tok[:6]}...{tg_tok[-4:]}' if len(tg_tok) > 10 else 'short?'
    return Response(json.dumps(results, indent=2), mimetype='application/json')

@app.route('/webhook', methods=['POST'])
def webhook_post():
    try:
        body = request.get_json(force=True, silent=True) or {}
        msg = body.get('message', {})
        if msg and msg.get('chat', {}).get('id') == SOFIA_CHAT_ID:
            text = msg.get('text', '').strip()
            if text:
                try:
                    state = read_state()
                except Exception as e:
                    print(f'read_state error: {e}')
                    state = {'last_offset': 0, 'notified_validar_tasks': [], 'active_conversation': None, 'pending_approvals': []}
                try:
                    state = process(text, state)
                except Exception as e:
                    print(f'process error [{text[:40]}]: {e}')
                    return Response('OK', status=200)
                trigger_calendar = state.pop('_trigger_calendar', False)
                try:
                    save_state(state)
                except Exception as e:
                    print(f'save_state error: {e}')
                # Disparar /calendar/generate DESPUÉS de guardar el estado
                if trigger_calendar:
                    try:
                        req = urllib.request.Request(
                            'https://vercel-deploy-tan-one.vercel.app/calendar/generate',
                            data=b'', method='POST'
                        )
                        urllib.request.urlopen(req, timeout=3)
                    except Exception:
                        pass  # timeout/error esperado — generate sigue corriendo
    except Exception as e:
        print(f'webhook error: {e}')
    return Response('OK', status=200)

@app.route('/cron/check-validar', methods=['GET', 'POST'])
def cron_check_validar():
    try:
        state = read_state()
        state = check_validar(state)
        save_state(state)
    except Exception as e:
        print(f'Validar cron error: {e}')
    return Response('OK', status=200)

@app.route('/cron/check-posts', methods=['GET', 'POST'])
def cron_check_posts():
    try:
        state = read_state()
        state = check_new_posts(state)
        save_state(state)
    except Exception as e:
        print(f'Check posts error: {e}')
    return Response('OK', status=200)

@app.route('/calendar/generate', methods=['GET', 'POST'])
def calendar_generate():
    """Procesa UNA marca pendiente del calendario por llamada. Llamar cada 2 min desde cron-job.org."""
    try:
        state = read_state()
        pending = state.get('pending_calendar')
        if not pending:
            return Response('no pending', status=200)

        brands    = pending['brands']
        idx       = pending.get('idx', 0)
        month_str = pending['month_str']
        month_label = pending.get('month_label', month_str)

        if idx >= len(brands):
            # Todas las marcas listas
            key = os.environ.get('CALENDAR_KEY', 'sofia2026mkt')
            calendar_data = get_calendar_data(month_str)
            total = sum(len(v) for v in calendar_data.values())
            tg_send(
                f'✅ *Calendario {month_label} listo\\!*\n\n'
                f'📊 {total} piezas generadas\n'
                f'🏢 {", ".join(brands)}\n\n'
                f'🔗 https://vercel-deploy-tan-one.vercel.app/calendar?key={key}&month={month_str}'
            )
            del state['pending_calendar']
            save_state(state)
            return Response('done', status=200)

        brand = brands[idx]
        tg_send(f'⏳ Generando *{brand}*... ({idx+1}/{len(brands)})')

        try:
            year, mo = int(month_str[:4]), int(month_str[5:])
            posting_dates = get_posting_dates(year, mo)
            assignments   = assign_formats(brands, posting_dates)
            calendar_data = read_calendar().get(month_str) or {}

            slots = [(d, brands_day[brand]) for d, brands_day in sorted(assignments.items()) if brand in brands_day]
            social   = generate_social_posts(brand, month_label, slots)
            li_count = 4 if brand == 'ZoWeAre' else 3
            linkedin = generate_linkedin_posts(brand, month_label, li_count)
            blog     = [] if brand == 'ZoWeAre' else generate_blog_posts(brand, month_label, 2)
            emails   = [] if brand == 'ZoWeAre' else generate_email_posts(brand, month_label, 3)

            calendar_data[brand] = social + linkedin + blog + emails
            # Guardar en tarea de calendario — independiente del bot state
            update_calendar_month(month_str, calendar_data)
            tg_send(f'✅ *{brand}* generado — {len(social)} posts · {len(linkedin)} LinkedIn · {len(blog)} blog · {len(emails)} emails')
        except Exception as e:
            print(f'Calendar gen {brand}: {e}')
            tg_send(f'⚠️ Error generando {brand}: {str(e)[:100]}')

        pending['idx'] = idx + 1
        state['pending_calendar'] = pending
        save_state(state)  # solo guarda el bot state (pending, offset, etc.) — SIN calendario
    except Exception as e:
        print(f'calendar_generate error: {e}')
    return Response('OK', status=200)


@app.route('/calendar/generate-web', methods=['POST'])
def calendar_generate_web():
    """Genera contenido para UNA marca desde la UI web — sin Telegram.
    Body: {brand, month, type: 'social'|'linkedin'|'blog'|'email', prompt: '...extra...'}
    Cada tipo se llama por separado para no exceder 30s de Vercel.
    """
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    body       = request.get_json(force=True) or {}
    brand      = body.get('brand', '').strip()
    month_str  = body.get('month', '').strip()   # "2026-06"
    gen_type   = body.get('type', 'social')       # social | linkedin | blog | email
    extra_prompt = (body.get('prompt') or '').strip()

    if not brand or not month_str:
        return jsonify({'ok': False, 'error': 'brand y month son requeridos'}), 400
    # Aceptar marcas hardcodeadas O dinámicas (cargadas desde ClickUp)
    if brand not in CALENDAR_BRAND_TASKS:
        cfg = get_brands_config()
        if brand not in cfg:
            return jsonify({'ok': False, 'error': f'Marca desconocida: {brand}'}), 400
        # Registrar en runtime para esta sesión
        CALENDAR_BRAND_TASKS[brand] = cfg[brand]['task_id']
        if cfg[brand].get('brief'):
            BRAND_CONTEXT[brand] = cfg[brand]['brief']

    try:
        year, mo  = int(month_str[:4]), int(month_str[5:])
        from datetime import date as _date
        month_label = _date(year, mo, 1).strftime('%B %Y')

        # Si hay prompt extra, prependerlo al contexto de marca
        original_ctx = BRAND_CONTEXT.get(brand, brand)
        ctx_to_use   = (extra_prompt + '\n\n' + original_ctx) if extra_prompt else original_ctx
        BRAND_CONTEXT[brand] = ctx_to_use

        try:
            all_brands    = list(CALENDAR_BRAND_TASKS.keys())
            posting_dates = get_posting_dates(year, mo)
            assignments   = assign_formats(all_brands, posting_dates)

            # Posts existentes de esta marca/mes para merge
            existing = read_calendar_brand(brand, month_str)

            generated = []

            if gen_type == 'social':
                slots = [(d, bd[brand]) for d, bd in sorted(assignments.items()) if brand in bd]
                generated = generate_social_posts(brand, month_label, slots)
                # Merge: conservar linkedin/blog/email existentes
                keep = [p for p in existing if p.get('type') in ('LinkedIn','Blog','Email')]
                final = keep + generated

            elif gen_type == 'linkedin':
                li_count = 4 if brand == 'ZoWeAre' else 3
                generated = generate_linkedin_posts(brand, month_label, li_count)
                keep = [p for p in existing if p.get('type') != 'LinkedIn']
                final = keep + generated

            elif gen_type == 'blog':
                if brand == 'ZoWeAre':
                    return jsonify({'ok': False, 'error': 'ZoWeAre no tiene Blog'}), 400
                generated = generate_blog_posts(brand, month_label, 2)
                keep = [p for p in existing if p.get('type') != 'Blog']
                final = keep + generated

            elif gen_type == 'email':
                if brand == 'ZoWeAre':
                    return jsonify({'ok': False, 'error': 'ZoWeAre no tiene Email'}), 400
                generated = generate_email_posts(brand, month_label, 3)
                keep = [p for p in existing if p.get('type') != 'Email']
                final = keep + generated

            else:
                return jsonify({'ok': False, 'error': f'Tipo inválido: {gen_type}'}), 400

            save_calendar_brand(brand, month_str, final)
            return jsonify({'ok': True, 'brand': brand, 'type': gen_type, 'count': len(generated)})

        finally:
            BRAND_CONTEXT[brand] = original_ctx  # restaurar siempre

    except Exception as e:
        print(f'generate-web error: {e}')
        return jsonify({'ok': False, 'error': str(e)[:200]}), 500


@app.route('/calendar/brands', methods=['GET'])
def calendar_brands_get():
    """Devuelve la config de todas las marcas (nombre, color). Usado por el frontend."""
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401
    cfg = get_brands_config()
    # Devolver solo nombre + color (sin brief, para no exponer texto innecesariamente)
    return jsonify({'ok': True, 'brands': {k: {'color': v.get('color', '#666')} for k, v in cfg.items()}})


@app.route('/calendar/brands', methods=['POST'])
def calendar_brands_post():
    """Crea una nueva marca. Body: {name, color, brief}"""
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    body  = request.get_json(force=True) or {}
    name  = (body.get('name') or '').strip()
    color = (body.get('color') or '#6366f1').strip()
    brief = (body.get('brief') or '').strip()

    if not name:
        return jsonify({'ok': False, 'error': 'El nombre de la marca es requerido'}), 400
    if len(name) > 30:
        return jsonify({'ok': False, 'error': 'El nombre no puede superar 30 caracteres'}), 400

    cfg = get_brands_config()
    if name in cfg:
        return jsonify({'ok': False, 'error': f'La marca "{name}" ya existe'}), 409

    # Crear tarea ClickUp para el calendario de esta marca
    CALENDAR_LIST_ID = '901326439751'
    try:
        res = cu_post(f'list/{CALENDAR_LIST_ID}/task', {
            'name': f'📅 Cal-{name} [NO BORRAR]',
            'description': 'Calendario generado automáticamente.',
        })
        task_id = res.get('id') or res.get('task_id', '')
    except Exception as e:
        print(f'brands_post create task: {e}')
        return jsonify({'ok': False, 'error': f'Error creando tarea ClickUp: {str(e)[:100]}'}), 500

    if not task_id:
        return jsonify({'ok': False, 'error': 'No se pudo crear la tarea de ClickUp'}), 500

    # Guardar en CALENDAR_BRAND_TASKS runtime (para esta sesión) y en config
    CALENDAR_BRAND_TASKS[name] = task_id
    if brief:
        BRAND_CONTEXT[name] = brief
    cfg[name] = {'color': color, 'task_id': task_id, 'brief': brief}
    try:
        save_brands_config(cfg)
    except Exception as e:
        print(f'brands_post save config: {e}')

    return jsonify({'ok': True, 'brand': name, 'color': color, 'task_id': task_id})


@app.route('/cron/seo-report', methods=['GET', 'POST'])
def cron_seo_report():
    if not is_first_business_day():
        return Response('Not first business day — skipping.', status=200)
    try:
        run_seo_reports()
    except Exception as e:
        print(f'SEO report error: {e}')
        tg_send(f'❌ Error en reporte SEO: {str(e)[:150]}')
    return Response('OK', status=200)

@app.route('/calendar')
def calendar_page():
    key = request.args.get('key', '')
    expected = os.environ.get('CALENDAR_KEY', 'sofia2026mkt')
    if key != expected:
        return Response('<h2>Acceso no autorizado</h2>', status=401, mimetype='text/html')
    # Si no hay ?month= en la URL, detectar el mes con datos más próximo y redirigir
    if not request.args.get('month'):
        from flask import redirect
        today = dt.date.today()
        # Leer una vez por marca (5 llamadas) en lugar de buscar en el estado del bot
        months_with_data = set()
        for brand in get_all_brand_tasks():
            try:
                brand_data = read_calendar_brand(brand)  # {month_str: [posts]}
                for ms, posts in brand_data.items():
                    if posts:
                        months_with_data.add(ms)
            except Exception:
                pass
        for delta in range(0, 7):
            d = today.replace(day=1) + dt.timedelta(days=32 * delta)
            ms = f'{d.year}-{str(d.month).zfill(2)}'
            if ms in months_with_data:
                return redirect(f'/calendar?key={key}&month={ms}')
    return Response(CALENDAR_HTML, mimetype='text/html')

@app.route('/calendar/data')
def calendar_data_route():
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return Response('{}', status=401, mimetype='application/json')
    month_str = request.args.get('month', dt.date.today().strftime('%Y-%m'))
    month_data = get_calendar_data(month_str)
    brands = [b for b in get_all_brand_tasks() if b in month_data]
    state = read_state()
    designer_checks = state.get('designer_checks', [])
    return Response(json.dumps({'posts': month_data, 'brands': brands, 'designer_checks': designer_checks}, ensure_ascii=False), mimetype='application/json')

@app.route('/calendar/save', methods=['POST'])
def calendar_save_route():
    """Guarda/actualiza un post individual. Lee y escribe SOLO la tarea de calendario."""
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return Response('Unauthorized', status=401)
    body = request.get_json() or {}
    month_str = body.get('month')
    post = body.get('post')
    if not month_str or not post:
        return Response('Bad request', status=400)
    brand = post.get('brand', '')
    if not brand:
        return Response('Bad request — falta brand en el post', status=400)
    # Leer y escribir SOLO la tarea de esa marca (payload ~15KB en lugar de 107KB)
    brand_data = read_calendar_brand(brand)      # {month_str: [posts]}
    posts_list = brand_data.get(month_str, [])
    idx = next((i for i, p in enumerate(posts_list) if p.get('id') == post.get('id')), -1)
    if idx >= 0:
        posts_list[idx] = post
    else:
        posts_list.append(post)
    save_calendar_brand(brand, month_str, posts_list)
    return Response('OK', status=200)

@app.route('/calendar/check-toggle', methods=['POST'])
def calendar_check_toggle():
    """Activa/desactiva el check de diseñadora para un post. Guarda en el estado del bot."""
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return Response('Unauthorized', status=401)
    body = request.get_json() or {}
    post_id = body.get('post_id')
    if not post_id:
        return Response('Bad request', status=400)
    state = read_state()
    checks = state.get('designer_checks', [])
    if post_id in checks:
        checks.remove(post_id)
        checked = False
    else:
        checks.append(post_id)
        checked = True
    state['designer_checks'] = checks
    save_state(state)
    return Response(json.dumps({'ok': True, 'post_id': post_id, 'checked': checked}),
                    mimetype='application/json')

@app.route('/calendar/replace-brand', methods=['POST'])
def calendar_replace_brand_route():
    """Reemplaza TODOS los posts de una marca en un mes — atómico en la tarea de calendario.
    Body: {month, brand, posts: [...]}
    """
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return Response('Unauthorized', status=401)
    body = request.get_json() or {}
    month_str = body.get('month')
    brand     = body.get('brand')
    new_posts = body.get('posts', [])
    if not month_str or not brand:
        return Response('Bad request — se requiere month y brand', status=400)
    # Compactar: texto_imagen conservado en sociales (cap 200), omitido en LI/Blog/Email
    SOCIAL_TYPES = {'Post', 'Carrusel', 'Reel', 'Story'}
    COPY_LIMITS  = {'Blog': 400, 'Email': 400, 'LinkedIn': 400}
    compact_posts = []
    for p in new_posts:
        t  = p.get('type', '')
        cp = dict(p)
        if t in SOCIAL_TYPES:
            ti = cp.get('texto_imagen', '')
            if ti and len(ti) > 600:
                cp['texto_imagen'] = ti[:600]
        else:
            cp.pop('texto_imagen', None)
        lim = COPY_LIMITS.get(t)
        if lim and len(cp.get('copy', '')) > lim:
            cp['copy'] = cp['copy'][:lim]
        compact_posts.append(cp)
    # Escribir SOLO la tarea de esa marca (~15KB en lugar de 107KB)
    save_calendar_brand(brand, month_str, compact_posts)
    return Response(json.dumps({'ok': True, 'brand': brand, 'month': month_str,
                                'posts': len(new_posts)}), status=200,
                    mimetype='application/json')

@app.route('/calendar/delete', methods=['POST'])
def calendar_delete_route():
    """Elimina un post. Lee y escribe SOLO la tarea de calendario."""
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return Response('Unauthorized', status=401)
    body = request.get_json() or {}
    month_str = body.get('month')
    post_id   = body.get('post_id')
    brand     = body.get('brand')
    if not month_str or not post_id:
        return Response('Bad request', status=400)
    if brand:
        posts_list = read_calendar_brand(brand, month_str)
        posts_list = [p for p in posts_list if p.get('id') != post_id]
        save_calendar_brand(brand, month_str, posts_list)
    else:
        # sin brand: buscar en todas las marcas
        for b in get_all_brand_tasks():
            posts_list = read_calendar_brand(b, month_str)
            filtered = [p for p in posts_list if p.get('id') != post_id]
            if len(filtered) < len(posts_list):
                save_calendar_brand(b, month_str, filtered)
                break
    return Response('OK', status=200)

@app.route('/calendar/restore-backup', methods=['POST'])
def calendar_restore_backup_route():
    """Restaura el calendario desde el backup. Usar solo si el calendario principal se corrompió."""
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return Response('Unauthorized', status=401)
    try:
        task = cu_get(f'task/{CALENDAR_BACKUP_TASK_ID}')
        backup_desc = task.get('description', '') or ''
        if not backup_desc.strip():
            return Response(json.dumps({'error': 'Backup vacío — nada para restaurar'}),
                            status=404, mimetype='application/json')
        # Restaurar: copiar backup → principal (sin pasar por save_calendar para no pisar el backup)
        cu_put(f'task/{CALENDAR_TASK_ID}', {'markdown_description': backup_desc})
        restored = _decode_task_desc(backup_desc)
        total = sum(len(v) for month in restored.values() for v in (month.values() if isinstance(month, dict) else []))
        return Response(json.dumps({'ok': True, 'restored_posts': total}),
                        status=200, mimetype='application/json')
    except Exception as e:
        return Response(json.dumps({'error': str(e)}), status=500, mimetype='application/json')

@app.route('/calendar/regenerate-post', methods=['POST'])
def calendar_regenerate_post_route():
    """Regenera un post con IA. Lee y escribe SOLO la tarea de calendario."""
    key = request.args.get('key', '')
    if key != os.environ.get('CALENDAR_KEY', 'sofia2026mkt'):
        return Response('Unauthorized', status=401)
    body = request.get_json() or {}
    month_str   = body.get('month')
    post_id     = body.get('post_id')
    instruction = body.get('instruction', '').strip()
    if not month_str or not post_id:
        return Response('Bad request', status=400)
    # Buscar el post en las tareas de las marcas
    found_post = None; found_brand = None
    for b in get_all_brand_tasks():
        posts_list = read_calendar_brand(b, month_str)
        for p in posts_list:
            if p.get('id') == post_id:
                found_post = p; found_brand = b; break
        if found_post: break
    if not found_post:
        return Response('Post not found', status=404)
    try:
        new_post = regenerate_single_post(found_post, instruction)
        if new_post:
            posts_list = read_calendar_brand(found_brand, month_str)
            for i, p in enumerate(posts_list):
                if p.get('id') == post_id:
                    posts_list[i] = new_post; break
            save_calendar_brand(found_brand, month_str, posts_list)
            return Response(json.dumps(new_post, ensure_ascii=False), mimetype='application/json')
    except Exception as e:
        print(f'Regenerate post error: {e}')
    return Response('Error generating post', status=500)


# ─── PAID MEDIA MONTHLY REPORT ──────────────────────────────────────

REPORT_OBJECTIVES = {
    'BHU/UIN': {'leads': 1050, 'ventas': 24},
    'EBDS':    {'leads': 600,  'ventas': 10},
}

def calculate_curva(month_date=None):
    """% días hábiles (Lun–Sáb) transcurridos en el mes."""
    if month_date is None:
        month_date = dt.date.today()
    today = dt.date.today()
    first = month_date.replace(day=1)
    if month_date.month == 12:
        last = month_date.replace(day=31)
    else:
        last = month_date.replace(month=month_date.month + 1, day=1) - dt.timedelta(days=1)
    total_w = elapsed_w = 0
    d = first
    while d <= last:
        if d.weekday() < 6:   # 0=Lun … 5=Sáb
            total_w += 1
            if d <= today:
                elapsed_w += 1
        d += dt.timedelta(days=1)
    pct = round(elapsed_w / total_w * 100, 1) if total_w else 0
    return elapsed_w, total_w, pct

def fetch_meta_monthly(is_ebds=False, month_date=None):
    """Datos Meta Ads desde día 1 del mes hasta month_date (o hoy), nivel adset."""
    if month_date is None:
        month_date = dt.date.today()
    today = dt.date.today()
    # until = el menor entre month_date y hoy (para meses pasados usa último día del mes)
    until_date = min(month_date, today)
    since_date = month_date.replace(day=1)
    tr = json.dumps({'since': since_date.isoformat(), 'until': until_date.isoformat()})
    fields = 'campaign_name,adset_name,spend,impressions,clicks,ctr,cpm,cpc,reach,actions,cost_per_action_type'
    url = (f'https://graph.facebook.com/v21.0/act_2249213495344845/insights'
           f'?fields={urllib.parse.quote(fields)}&time_range={urllib.parse.quote(tr)}'
           f'&level=adset&limit=200&access_token={META_TOKEN}')
    try:
        resp = http_req(url)
        rows = resp.get('data', [])
        # Paginar si hay más resultados
        next_url = resp.get('paging', {}).get('next')
        while next_url and len(rows) < 500:
            try:
                r2 = http_req(next_url)
                rows += r2.get('data', [])
                next_url = r2.get('paging', {}).get('next')
            except Exception:
                break
    except Exception as e:
        print(f'fetch_meta_monthly error: {e}')
        rows = []
    if is_ebds:
        return [r for r in rows if 'ebds' in r.get('campaign_name', '').lower()]
    else:
        return [r for r in rows if 'ebds' not in r.get('campaign_name', '').lower()]

def _leads(row):
    return sum(int(a.get('value', 0)) for a in (row.get('actions') or [])
               if a.get('action_type') == 'onsite_conversion.lead_grouped')

def _is_remark(cn, an=''):
    t = (cn + ' ' + an).lower()
    return any(w in t for w in ['retargeting', 'remarketing', ' rtg', ' rtgt', 'remarket'])

def _norm_prog(s):
    s = s.lower()
    s = re.sub(r'^(ebds|uin|bhu|behind[-\s]u)\s*[-–:]\s*', '', s)
    s = re.sub(r'\b(leads?|clientes? potenciales?|retargeting|remarketing|rtg|rtgt|'
               r'prospecting|prosp|conversiones?|tr[a\xe1]fico|awareness|branding)\b', '', s)
    s = re.sub(r'[^a-z\xe1\xe9\xed\xf3\xfa\xfc\xf1\s]', ' ', s)
    return ' '.join(s.split())

# BHU/UIN: keyword in adset name → CRM program group label + list of matching CRM programs
BHU_META_PROG_GROUPS = {
    'ingenier': {
        'label': 'Ingenierías',
        'crm_progs': [
            'Ingeniería Industrial y de Sistemas',
            'Ingeniería en Sistemas Computacionales',
            'Ingeniería en Software y redes',
        ],
    },
    'proyectos': {
        'label': 'M. Administración de Proyectos',
        'crm_progs': ['Maestría en administración de proyectos'],
    },
    'derecho': {
        'label': 'M. Derecho',
        'crm_progs': [
            'Maestría en Derecho Penal', 'Maestría en Amparo',
            'Maestría en Derecho Fiscal', 'Maestría en Derecho Corporativo',
            'Maestría en Criminología', 'Maestría en Juicios Orales',
        ],
    },
}

def _bhu_prog_match(adset_name):
    """Returns (label, crm_prog_list) if adset matches a known BHU group, else None."""
    an = adset_name.lower()
    for keyword, grp in BHU_META_PROG_GROUPS.items():
        if keyword in an:
            return grp['label'], grp['crm_progs']
    return None

def _fuzzy_prog(adset_name, crm_progs):
    w1 = {w for w in _norm_prog(adset_name).split() if len(w) > 3}
    best, bsc = None, 0
    for p in crm_progs:
        w2 = {w for w in _norm_prog(p).split() if len(w) > 3}
        if not w1 or not w2:
            continue
        sc = len(w1 & w2) / max(len(w1), len(w2))
        if sc > bsc:
            bsc, best = sc, p
    return (best, bsc) if bsc >= 0.3 else (None, 0)

def _sum_rows(rows):
    sp  = sum(float(r.get('spend', 0)) for r in rows)
    ld  = sum(_leads(r) for r in rows)
    imp = sum(int(r.get('impressions', 0)) for r in rows)
    cl  = sum(int(r.get('clicks', 0)) for r in rows)
    cpl = sp / ld  if ld  else 0
    ctr = cl / imp * 100 if imp else 0
    cpm = sp / imp * 1000 if imp else 0
    return sp, ld, imp, cl, cpl, ctr, cpm

def _kc(val, target):
    if not target: return ''
    if val >= target:        return 'ok'
    if val >= target * 0.7:  return 'warn'
    return 'bad'


def build_paid_media_html(client_name, meta_data, crm_data, month_date):
    today      = dt.date.today()
    is_ebds    = (client_name == 'EBDS')
    obj        = REPORT_OBJECTIVES.get(client_name, {'leads': 1000, 'ventas': 20})
    elapsed_d, total_d, curva_pct = calculate_curva(month_date)

    MESES = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio',
             'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    month_es   = MESES[month_date.month]
    period_str = f'1 al {today.day} de {month_es} {today.year}'

    # ── Meta split ──────────────────────────────────────────────────
    prospc = [r for r in meta_data if not _is_remark(r.get('campaign_name',''), r.get('adset_name',''))]
    remar  = [r for r in meta_data if     _is_remark(r.get('campaign_name',''), r.get('adset_name',''))]

    t_sp, t_ld, t_imp, t_cl, t_cpl, t_ctr, t_cpm = _sum_rows(meta_data)
    p_sp, p_ld,  _,     _,    p_cpl, p_ctr, _     = _sum_rows(prospc)
    r_sp, r_ld,  _,     _,    r_cpl, r_ctr, _     = _sum_rows(remar)

    # Campaigns group
    camps = {}
    for row in prospc:
        cn = row.get('campaign_name', 'Sin campaña')
        camps.setdefault(cn, {'adsets': [], 'spend': 0, 'leads': 0, 'impressions': 0, 'clicks': 0})
        camps[cn]['adsets'].append(row)
        camps[cn]['spend']       += float(row.get('spend', 0))
        camps[cn]['leads']       += _leads(row)
        camps[cn]['impressions'] += int(row.get('impressions', 0))
        camps[cn]['clicks']      += int(row.get('clicks', 0))

    # ── CRM ──────────────────────────────────────────────────────────
    f           = (crm_data or {}).get('funnel', {})
    contactados = f.get('contactados', 0)
    interesados = f.get('interesados', 0)
    evaluando   = f.get('evaluando', 0)
    promesa     = f.get('promesa_pago', 0)
    estudiantes = f.get('estudiantes', 0)
    perdidos    = f.get('perdidos', 0)
    # ventas_mes = deals que llegaron a stage conversión en el mes (Modified_Time)
    ventas      = (crm_data or {}).get('ventas_mes', estudiantes)
    # mql_mes = deals creados en el mes (Created_Time)
    mql    = (crm_data or {}).get('mql_mes', 0) or (contactados + interesados + evaluando + promesa + estudiantes + perdidos)
    sql    = contactados + interesados + evaluando + promesa

    leads_pct   = t_ld   / obj['leads']  * 100 if obj['leads']  else 0
    ventas_pct  = ventas / obj['ventas'] * 100 if obj['ventas'] else 0
    mql_rate    = mql / t_ld * 100 if t_ld else 0
    sql_rate    = sql / t_ld * 100 if t_ld else 0
    leads_pace  = leads_pct  / curva_pct * 100 if curva_pct else 0
    ventas_pace = ventas_pct / curva_pct * 100 if curva_pct else 0

    def fc(v, d=0): return f'${v:,.{d}f}' if v else '—'
    def fn(v):      return f'{int(v):,}' if v else '—'
    def fp(v, d=1): return f'{v:.{d}f}%'

    def pace_badge(pace):
        if pace >= 95:  return '<span class="pill pill-ok">✓ On track</span>'
        if pace >= 70:  return '<span class="pill pill-new">⚠ Por detr\xe1s</span>'
        return '<span class="pill pill-bad">✗ En riesgo</span>'

    # ── Programs cross-reference ─────────────────────────────────────
    top_progs = (crm_data or {}).get('top_programas', {})
    prog_meta = {}
    covered_crm_progs = set()   # CRM programs already grouped under a BHU group key

    for row in prospc:
        an = row.get('adset_name', '')
        bhu_match = _bhu_prog_match(an) if not is_ebds else None

        if bhu_match:
            label, crm_prog_list = bhu_match
            key = label
            if key not in prog_meta:
                crm_count = sum(top_progs.get(p, 0) for p in crm_prog_list)
                prog_meta[key] = {'spend': 0, 'leads': 0, 'crm': crm_count, 'matched': True}
                covered_crm_progs.update(crm_prog_list)
        else:
            prog, _ = _fuzzy_prog(an, list(top_progs.keys()))
            key = prog if prog else an[:50]
            if key not in prog_meta:
                prog_meta[key] = {'spend': 0, 'leads': 0,
                                  'crm': top_progs.get(prog, 0) if prog else 0,
                                  'matched': bool(prog)}

        prog_meta[key]['spend'] += float(row.get('spend', 0))
        prog_meta[key]['leads'] += _leads(row)

    for p, cnt in top_progs.items():
        if p not in prog_meta and p not in covered_crm_progs:
            prog_meta[p] = {'spend': 0, 'leads': 0, 'crm': cnt, 'matched': False}

    sorted_progs = sorted(prog_meta.items(), key=lambda x: -(x[1]['spend'] + x[1]['crm'] * 5))[:14]

    # ── Accionables ──────────────────────────────────────────────────
    acciones = []
    if leads_pace < 70:
        acciones.append(('alta',
            f'Leads por detr\xe1s de curva ({fp(leads_pct)} acumulado vs {fp(curva_pct)} curva). '
            f'Revis\xe1 presupuesto diario y audiencias.', 'Meta Ads'))
    elif leads_pace < 90:
        acciones.append(('media',
            f'Pace de leads ligeramente por debajo ({fp(leads_pace, 0)} de lo esperado). '
            f'Monitorear CPL y creativos.', 'Meta Ads'))
    if t_cpl > 50:
        acciones.append(('alta', f'CPL total ${t_cpl:.0f} es elevado. Paus\xe1 adsets sin conversiones.', 'Meta Ads'))
    elif t_cpl > 30:
        acciones.append(('media', f'CPL ${t_cpl:.0f}. Prob\xe1 creativos con mayor tasa de click→lead.', 'Meta Ads'))
    for cn, cdata in sorted(camps.items(), key=lambda x: -x[1]['spend'])[:5]:
        camp_cpl_v = cdata['spend'] / cdata['leads'] if cdata['leads'] else 9999
        if cdata['leads'] == 0 and cdata['spend'] > 150:
            acciones.append(('alta',
                f'"{cn[:55]}" — ${cdata["spend"]:.0f} sin leads. Pausar o revisar p\xfablico.', 'Meta Ads'))
        elif cdata['leads'] > 0 and camp_cpl_v > t_cpl * 1.6:
            acciones.append(('media',
                f'"{cn[:55]}" — CPL ${camp_cpl_v:.0f} ({camp_cpl_v/t_cpl:.1f}x el promedio). '
                f'Revisar segmentaci\xf3n.', 'Meta Ads'))
    if sql > 0 and promesa / sql < 0.05:
        acciones.append(('media',
            f'Solo {promesa} deals en Promesa de Pago ({promesa/sql*100:.1f}% del pipeline activo). '
            f'Activar seguimiento en Evaluando ({evaluando}).', 'CRM'))
    if mql > 0 and perdidos > mql * 0.4:
        acciones.append(('media',
            f'{perdidos} perdidos ({perdidos/mql*100:.1f}% del MQL). Analizar motivo de rechazo.', 'CRM'))
    if ventas_pace < 60:
        acciones.append(('alta',
            f'Ventas muy por detr\xe1s de curva ({fp(ventas_pct)} vs {fp(curva_pct)}). '
            f'Revisar pipeline con ventas.', 'CRM'))
    if not acciones:
        acciones.append(('baja', 'Campa\xf1a en buen ritmo. Mantener optimizaci\xf3n semanal de creativos.', 'Meta Ads'))

    # ── Colors ───────────────────────────────────────────────────────
    primary   = '#1e3a8a' if is_ebds else '#1a4a8a'
    primary_l = '#e6eef9' if is_ebds else '#e6f1fb'
    primary_m = '#3b82f6' if is_ebds else '#378ADD'
    curva_cls = 'ok' if curva_pct >= 80 else ('warn' if curva_pct >= 50 else 'bad')

    # ── Campaigns HTML ───────────────────────────────────────────────
    def strip_prefix(s):
        for pfx in ['EBDS - ', 'EBDS- ', 'BHU - ', 'UIN - ', 'Behind-U - ', 'BeU - ']:
            s = s.replace(pfx, '')
        return s

    camps_html = ''
    for cn, cdata in sorted(camps.items(), key=lambda x: -x[1]['spend']):
        camp_cpl_v = cdata['spend'] / cdata['leads'] if cdata['leads'] else 0
        camp_ctr   = cdata['clicks'] / cdata['impressions'] * 100 if cdata['impressions'] else 0
        camps_html += (
            f'<tr class="camp-row">'
            f'<td style="font-weight:600;color:#1a1a18" title="{cn}">{strip_prefix(cn)[:60]}</td>'
            f'<td>{fc(cdata["spend"])}</td>'
            f'<td>{fn(cdata["leads"]) if cdata["leads"] else "<span class=bad>—</span>"}</td>'
            f'<td>{fc(camp_cpl_v) if cdata["leads"] else "<span class=bad>—</span>"}</td>'
            f'<td>{fp(camp_ctr)}</td>'
            f'<td>{fn(cdata["impressions"])}</td>'
            f'</tr>'
        )
        for a in sorted(cdata['adsets'], key=lambda x: -float(x.get('spend', 0))):
            a_sp  = float(a.get('spend', 0))
            a_ld  = _leads(a)
            a_cpl = a_sp / a_ld if a_ld else 0
            a_imp = int(a.get('impressions', 0))
            a_cl  = int(a.get('clicks', 0))
            a_ctr = a_cl / a_imp * 100 if a_imp else 0
            an    = a.get('adset_name', '')
            camps_html += (
                f'<tr class="adset-row">'
                f'<td style="padding-left:26px;color:#6b6b66;font-size:11px" title="{an}">'
                f'⤷ {strip_prefix(an)[:58]}</td>'
                f'<td style="color:#6b6b66">{fc(a_sp)}</td>'
                f'<td style="color:#6b6b66">{fn(a_ld) if a_ld else "—"}</td>'
                f'<td style="color:#6b6b66">{fc(a_cpl) if a_ld else "—"}</td>'
                f'<td style="color:#6b6b66">{fp(a_ctr)}</td>'
                f'<td style="color:#6b6b66">{fn(a_imp)}</td>'
                f'</tr>'
            )
    if not camps_html:
        camps_html = '<tr><td colspan="6" style="text-align:center;color:#9e9e98;padding:20px">Sin datos de campa\xf1as para el per\xedodo</td></tr>'

    # ── Remarketing HTML ─────────────────────────────────────────────
    remark_html = ''
    if remar:
        remark_camps = {}
        for row in remar:
            cn = row.get('campaign_name', 'Remarketing')
            remark_camps.setdefault(cn, {'spend': 0, 'leads': 0})
            remark_camps[cn]['spend'] += float(row.get('spend', 0))
            remark_camps[cn]['leads'] += _leads(row)
        for cn, cdata in sorted(remark_camps.items(), key=lambda x: -x[1]['spend']):
            r_cpl2 = cdata['spend'] / cdata['leads'] if cdata['leads'] else 0
            remark_html += (
                f'<tr>'
                f'<td style="font-weight:600" title="{cn}">{strip_prefix(cn)[:60]}</td>'
                f'<td>{fc(cdata["spend"])}</td>'
                f'<td>{fn(cdata["leads"]) if cdata["leads"] else "—"}</td>'
                f'<td>{fc(r_cpl2) if cdata["leads"] else "—"}</td>'
                f'</tr>'
            )
    if not remark_html:
        remark_html = '<tr><td colspan="4" style="text-align:center;color:#9e9e98;padding:16px">Sin campa\xf1as de remarketing en el per\xedodo</td></tr>'

    # ── Programs HTML ────────────────────────────────────────────────
    progs_html = ''
    for prog_name, pdata in sorted_progs:
        p_cpl2    = pdata['spend'] / pdata['leads'] if pdata['leads'] else 0
        badge_cls = 'pill-ok' if pdata['matched'] else 'pill-new'
        badge_txt = '✓' if pdata['matched'] else '~'
        progs_html += (
            f'<tr>'
            f'<td><span class="pill {badge_cls}" style="margin-right:6px">{badge_txt}</span>'
            f'{prog_name[:52]}</td>'
            f'<td>{fn(pdata["leads"]) if pdata["leads"] else "—"}</td>'
            f'<td>{fc(pdata["spend"])}</td>'
            f'<td>{fc(p_cpl2) if pdata["leads"] else "—"}</td>'
            f'<td>{fn(pdata["crm"]) if pdata["crm"] else "—"}</td>'
            f'</tr>'
        )
    if not progs_html:
        progs_html = '<tr><td colspan="5" style="text-align:center;color:#9e9e98;padding:16px">Sin datos de programas disponibles</td></tr>'

    # ── Accionables HTML ─────────────────────────────────────────────
    acc_html = ''
    for prio, desc, canal in acciones[:6]:
        pcls = {'alta': 'p-alta', 'media': 'p-media', 'baja': 'p-baja'}[prio]
        acc_html += (
            f'<div class="accion-block">'
            f'<div class="accion-header">'
            f'<div class="accion-title">{desc}</div>'
            f'<div class="prioridad {pcls}">{prio.upper()}</div>'
            f'</div>'
            f'<div class="accion-canal">\U0001f4cd {canal}</div>'
            f'</div>'
        )

    # ── Fuentes CRM ──────────────────────────────────────────────────
    fuentes_html = ''
    if crm_data and crm_data.get('leads_por_fuente'):
        fuentes_html = (
            '<div class="tbl-wrap" style="margin-top:14px">'
            '<table class="tbl"><thead><tr><th>Fuente de leads</th><th>Cantidad</th></tr></thead><tbody>'
        )
        for k, v in list(crm_data['leads_por_fuente'].items())[:8]:
            fuentes_html += f'<tr><td>{k}</td><td>{v:,}</td></tr>'
        fuentes_html += '</tbody></table></div>'

    # ── Asesores HTML ─────────────────────────────────────────────────
    asesores_html = ''
    asesores_list = (crm_data or {}).get('asesores', [])
    if asesores_list:
        total_leads_as = sum(a['leads'] for a in asesores_list)
        total_opps_as  = sum(a['opps']  for a in asesores_list)
        total_vent_as  = sum(a['ventas'] for a in asesores_list)
        def _pct(n, d): return f'{n/d*100:.0f}%' if d else '—'
        def _bar(n, d, color='#3b82f6'):
            w = min(n/d*100, 100) if d else 0
            return f'<div style="background:#f0f0f0;border-radius:3px;height:5px;width:60px;display:inline-block;vertical-align:middle"><div style="background:{color};border-radius:3px;height:5px;width:{w:.0f}%"></div></div>'

        asesores_html = (
            '<div class="tw"><table class="tbl">'
            '<thead><tr>'
            '<th style="width:18%">Asesor</th>'
            '<th style="width:9%">Leads</th>'
            '<th style="width:9%">Sin gestión</th>'
            '<th style="width:9%">Intentos</th>'
            '<th style="width:9%">Duplicado</th>'
            '<th style="width:9%">Inválido</th>'
            '<th style="width:9%">No contact.</th>'
            '<th style="width:9%">Opps.</th>'
            '<th style="width:9%">Ventas</th>'
            '<th style="width:10%">% Conv.</th>'
            '</tr></thead><tbody>'
        )
        for a in asesores_list:
            ld = a['leads'] or 1
            conv_color = '#16a34a' if a['conv_pct'] >= 2 else ('#d97706' if a['conv_pct'] >= 0.5 else '#dc2626')
            asesores_html += (
                f'<tr>'
                f'<td><b>{a["nombre"]}</b></td>'
                f'<td>{a["leads"]}</td>'
                f'<td>{a["sin_gestion"]} <span style="color:var(--hint);font-size:10px">{_pct(a["sin_gestion"],ld)}</span></td>'
                f'<td>{a["intentos"]} <span style="color:var(--hint);font-size:10px">{_pct(a["intentos"],ld)}</span></td>'
                f'<td>{a["duplicado"]} <span style="color:var(--hint);font-size:10px">{_pct(a["duplicado"],ld)}</span></td>'
                f'<td>{a["invalido"]} <span style="color:var(--hint);font-size:10px">{_pct(a["invalido"],ld)}</span></td>'
                f'<td>{a["no_contactable"]} <span style="color:var(--hint);font-size:10px">{_pct(a["no_contactable"],ld)}</span></td>'
                f'<td>{a["opps"]}</td>'
                f'<td><b style="color:var(--green)">{a["ventas"]}</b></td>'
                f'<td><b style="color:{conv_color}">{a["conv_pct"]}%</b> {_bar(a["ventas"], a["leads"], conv_color)}</td>'
                f'</tr>'
            )
        # Fila total
        conv_total = round(total_vent_as / total_leads_as * 100, 1) if total_leads_as else 0
        asesores_html += (
            f'<tr class="total-row">'
            f'<td><b>TOTAL</b></td>'
            f'<td><b>{total_leads_as}</b></td>'
            f'<td colspan="5"></td>'
            f'<td><b>{total_opps_as}</b></td>'
            f'<td><b style="color:var(--green)">{total_vent_as}</b></td>'
            f'<td><b>{conv_total}%</b></td>'
            f'</tr>'
            '</tbody></table></div>'
        )

    # ── Remarketing KPI cards ─────────────────────────────────────────
    remark_kpis = ''
    if remar:
        remark_kpis = (
            f'<div class="kpi-grid-3" style="margin-bottom:14px">'
            f'<div class="kpi"><div class="kpi-label">INVERSI\xd3N</div>'
            f'<div class="kpi-val">{fc(r_sp)}</div>'
            f'<div class="kpi-sub">{r_sp/t_sp*100:.1f}% del total</div></div>'
            f'<div class="kpi"><div class="kpi-label">LEADS</div>'
            f'<div class="kpi-val">{fn(r_ld)}</div>'
            f'<div class="kpi-sub">CPL {fc(r_cpl) if r_ld else "—"}</div></div>'
            f'<div class="kpi"><div class="kpi-label">CTR</div>'
            f'<div class="kpi-val">{fp(r_ctr)}</div>'
            f'<div class="kpi-sub">vs {fp(p_ctr)} prospecting</div></div>'
            f'</div>'
        )

    # ── CRM funnel steps ─────────────────────────────────────────────
    def conv_rate_html(num, denom):
        if not denom:
            return ''
        pct2 = num / denom * 100
        cls  = 'ok' if pct2 >= 40 else ('warn' if pct2 >= 20 else 'bad')
        return f'<div class="fstep-rate {cls}">{pct2:.1f}% del anterior</div>'

    pipeline_total = contactados + interesados + evaluando + promesa + estudiantes

    # ── Full HTML ────────────────────────────────────────────────────
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{client_name} — Reporte Paid Media · {month_es} {today.year}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --white:#ffffff;--off:#f7f6f3;--surface:#f0efe9;
  --border:rgba(0,0,0,.08);--border-mid:rgba(0,0,0,.14);
  --text:#1a1a18;--muted:#6b6b66;--hint:#9e9e98;
  --pri:{primary};--pri-l:{primary_l};--pri-m:{primary_m};
  --red:#c0392b;--red-l:#fdf0ee;
  --amber:#8a5a00;--amber-l:#fdf5e0;
  --green:#1a5c1a;--green-l:#eef7ee;--green-m:#1D9E75;
  --radius:10px;--rl:14px;
}}
html{{scroll-behavior:smooth}}
body{{font-family:'DM Sans',sans-serif;background:var(--off);color:var(--text);font-size:14px;line-height:1.6;-webkit-font-smoothing:antialiased}}
.rh{{background:var(--white);border-bottom:1px solid var(--border);padding:40px 0 32px}}
.container{{max-width:960px;margin:0 auto;padding:0 32px}}
.hi{{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap}}
.dot{{width:9px;height:9px;border-radius:50%;background:var(--pri-m);display:inline-block;margin-right:8px}}
.bname{{font-size:12px;font-weight:500;color:var(--muted);letter-spacing:.04em}}
.htitle{{font-size:26px;font-weight:600;letter-spacing:-.02em;line-height:1.2;margin-top:8px}}
.hsub{{font-size:13px;color:var(--muted);margin-top:4px}}
.hper{{font-family:'DM Mono',monospace;font-size:11px;color:var(--hint);background:var(--surface);padding:6px 12px;border-radius:6px}}
.curva{{font-family:'DM Mono',monospace;font-size:11px;padding:6px 12px;border-radius:6px;font-weight:600}}
.curva.ok{{background:var(--green-l);color:var(--green)}}
.curva.warn{{background:var(--amber-l);color:var(--amber)}}
.curva.bad{{background:var(--red-l);color:var(--red)}}
.nav{{background:var(--white);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:99}}
.ni{{display:flex;overflow-x:auto;max-width:960px;margin:0 auto;padding:0 32px}}
.nl{{font-size:12px;font-weight:500;color:var(--muted);padding:13px 18px;text-decoration:none;white-space:nowrap;border-bottom:2px solid transparent;transition:all .15s}}
.nl:hover,.nl.active{{color:var(--text);border-bottom-color:var(--text)}}
.main{{max-width:960px;margin:0 auto;padding:40px 32px 80px}}
.sec{{margin-bottom:56px}}
.sh{{display:flex;align-items:baseline;gap:12px;margin-bottom:20px;padding-bottom:12px;border-bottom:1px solid var(--border)}}
.sn{{font-family:'DM Mono',monospace;font-size:11px;color:var(--hint)}}
.st{{font-size:18px;font-weight:600;letter-spacing:-.01em}}
.sb{{font-size:10px;font-weight:500;padding:2px 8px;border-radius:20px;background:var(--pri-l);color:var(--pri)}}
.kg{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}}
.kg3{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:16px}}
.kpi{{background:var(--white);border:1px solid var(--border);border-radius:var(--radius);padding:16px}}
.kl{{font-size:11px;color:var(--hint);margin-bottom:4px;font-weight:500;letter-spacing:.02em}}
.kv{{font-size:24px;font-weight:600;line-height:1.1;margin-bottom:4px;letter-spacing:-.02em}}
.ks{{font-size:11px;color:var(--muted)}}
.ks b{{font-weight:600}}
.kpi.ok{{border-top:2px solid var(--green-m)}}
.kpi.warn{{border-top:2px solid #e6a800}}
.kpi.bad{{border-top:2px solid var(--red)}}
.kpi.pri{{border-top:2px solid var(--pri-m)}}
.al{{border-radius:0 var(--radius) var(--radius) 0;padding:12px 16px;font-size:13px;line-height:1.6;margin-bottom:16px}}
.al b{{font-weight:600}}
.al-blue{{background:var(--pri-l);color:var(--pri);border-left:3px solid var(--pri-m)}}
.al-amber{{background:var(--amber-l);color:var(--amber);border-left:3px solid #e6a800}}
.al-green{{background:var(--green-l);color:var(--green);border-left:3px solid var(--green-m)}}
.tw{{background:var(--white);border:1px solid var(--border);border-radius:var(--rl);overflow:hidden;margin-bottom:14px}}
.tbl{{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}}
.tbl th{{background:var(--surface);font-size:10px;font-weight:600;color:var(--hint);letter-spacing:.05em;padding:10px 12px;text-align:left;border-bottom:1px solid var(--border-mid)}}
.tbl th:not(:first-child){{text-align:right}}
.tbl td{{padding:9px 12px;border-bottom:1px solid var(--border);font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.tbl td:not(:first-child){{text-align:right;font-family:'DM Mono',monospace;font-size:11px}}
.tbl tr:last-child td{{border-bottom:none}}
.tbl tr:hover td{{background:var(--off)}}
.camp-row td{{background:var(--surface)!important;font-weight:700}}
.adset-row td{{background:var(--white)}}
.total-row td{{background:var(--pri-l)!important;font-weight:700;border-top:2px solid var(--pri-m)!important}}
.fw{{background:var(--white);border:1px solid var(--border);border-radius:var(--rl);padding:24px;margin-bottom:14px}}
.frow{{display:flex;gap:8px;align-items:stretch;margin-bottom:12px;flex-wrap:wrap}}
.fstep{{background:var(--off);border-radius:8px;padding:12px 16px;flex:1;min-width:90px}}
.fstep.hi2{{background:var(--pri-l);border:1px solid var(--pri-m)}}
.fstep.win{{background:var(--green-l);border:1px solid var(--green-m)}}
.fstep-name{{font-size:10px;color:var(--hint);font-weight:600;letter-spacing:.04em;margin-bottom:4px}}
.fstep-val{{font-size:20px;font-weight:600;line-height:1.1;margin-bottom:2px}}
.fstep-rate{{font-size:10px;color:var(--muted)}}
.fstep-rate.ok{{color:var(--green)}}
.fstep-rate.warn{{color:var(--amber)}}
.fstep-rate.bad{{color:var(--red)}}
.arr{{color:var(--hint);font-size:18px;align-self:center;flex-shrink:0}}
.mq{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}}
.mb{{background:var(--pri-l);border:1px solid var(--pri-m);border-radius:var(--radius);padding:16px}}
.mb.g{{background:var(--green-l);border-color:var(--green-m)}}
.ml{{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--pri);margin-bottom:4px}}
.mb.g .ml{{color:var(--green)}}
.mv{{font-size:28px;font-weight:600;letter-spacing:-.02em}}
.ms{{font-size:11px;color:var(--muted);margin-top:4px}}
.ob{{background:var(--white);border:1px solid var(--border);border-radius:var(--rl);padding:20px 22px;margin-bottom:16px}}
.oh{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px}}
.ol{{font-size:13px;font-weight:600}}
.on{{font-family:'DM Mono',monospace;font-size:11px;color:var(--muted)}}
.pb{{height:8px;background:var(--surface);border-radius:4px;overflow:hidden;margin:8px 0 4px}}
.pf{{height:100%;border-radius:4px}}
.pf.ok{{background:var(--green-m)}}
.pf.warn{{background:#e6a800}}
.pf.bad{{background:var(--red)}}
.ab{{background:var(--white);border:1px solid var(--border);border-radius:var(--rl);padding:20px 22px;margin-bottom:12px}}
.ah{{display:flex;align-items:flex-start;gap:10px;margin-bottom:8px}}
.at{{font-size:13px;font-weight:500;line-height:1.5;flex:1}}
.pr{{font-size:9px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:3px 8px;border-radius:20px;white-space:nowrap;margin-top:2px;flex-shrink:0}}
.p-alta{{background:var(--red-l);color:var(--red)}}
.p-media{{background:var(--amber-l);color:var(--amber)}}
.p-baja{{background:var(--green-l);color:var(--green)}}
.ac{{font-size:10px;color:var(--hint);font-weight:500}}
.pill{{font-size:9px;font-weight:700;padding:1px 6px;border-radius:20px;letter-spacing:.02em}}
.pill-ok{{background:var(--green-l);color:var(--green)}}
.pill-bad{{background:var(--red-l);color:var(--red)}}
.pill-new{{background:var(--amber-l);color:var(--amber)}}
.ok{{color:var(--green)}}
.warn{{color:var(--amber)}}
.bad{{color:var(--red)}}
footer{{background:var(--white);border-top:1px solid var(--border);padding:24px 0;margin-top:32px}}
.fn{{font-size:11px;color:var(--hint);line-height:1.8}}
@media(max-width:640px){{
  .kg{{grid-template-columns:1fr 1fr}}
  .kg3{{grid-template-columns:1fr 1fr}}
  .frow{{flex-direction:column}}
  .arr{{transform:rotate(90deg)}}
  .mq{{grid-template-columns:1fr}}
  .container{{padding:0 16px}}
  .main{{padding:24px 16px 60px}}
  .ni{{padding:0 16px}}
}}
@media print{{.nav{{display:none}}body{{background:white}}.sec{{page-break-inside:avoid}}}}
</style>
</head>
<body>

<header class="rh">
<div class="container">
<div class="hi">
  <div>
    <div class="bname"><span class="dot"></span>{client_name} &middot; Paid Media</div>
    <div class="htitle">Reporte Mensual de Performance</div>
    <div class="hsub">Meta Ads + CRM &middot; {period_str}</div>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
    <div class="hper">{period_str}</div>
    <div class="curva {curva_cls}">Curva {fp(curva_pct)} &middot; D\xeda {elapsed_d}/{total_d}</div>
  </div>
</div>
</div>
</header>

<nav class="nav">
<div class="ni">
  <a class="nl active" href="#resumen">Resumen</a>
  <a class="nl" href="#meta">Meta Ads</a>
  <a class="nl" href="#crm">CRM</a>
  <a class="nl" href="#asesores">Asesores</a>
  <a class="nl" href="#programas">Programas</a>
  <a class="nl" href="#remarketing">Remarketing</a>
  <a class="nl" href="#accionables">Accionables</a>
</div>
</nav>

<main class="main">

<!-- 01 RESUMEN -->
<section class="sec" id="resumen">
<div class="sh"><span class="sn">01</span><h2 class="st">Resumen ejecutivo</h2><span class="sb">{month_es} {today.year}</span></div>

<div class="kg">
  <div class="kpi pri">
    <div class="kl">INVERSI\xd3N TOTAL</div>
    <div class="kv">{fc(t_sp)}</div>
    <div class="ks">Prosp. {fc(p_sp)} &middot; Remark. {fc(r_sp) if r_sp else "—"}</div>
  </div>
  <div class="kpi {_kc(leads_pct, curva_pct)}">
    <div class="kl">LEADS META ADS</div>
    <div class="kv">{fn(t_ld)}</div>
    <div class="ks">Obj. {fn(obj["leads"])} &middot; <b>{fp(leads_pct)}</b> {pace_badge(leads_pace)}</div>
  </div>
  <div class="kpi">
    <div class="kl">CPL GENERAL</div>
    <div class="kv">{fc(t_cpl)}</div>
    <div class="ks">Prosp. {fc(p_cpl)} &middot; Remark. {fc(r_cpl) if r_ld else "—"}</div>
  </div>
  <div class="kpi">
    <div class="kl">CTR &middot; CPM</div>
    <div class="kv">{fp(t_ctr)}</div>
    <div class="ks">CPM {fc(t_cpm)} &middot; {fn(t_imp)} impr.</div>
  </div>
</div>

<div class="kg">
  <div class="kpi">
    <div class="kl">MQL (OPORT. DEL MES)</div>
    <div class="kv">{fn(mql)}</div>
    <div class="ks">{fp(mql_rate)} de leads Meta → CRM</div>
  </div>
  <div class="kpi">
    <div class="kl">SQL (PIPELINE ACTIVO)</div>
    <div class="kv">{fn(sql)}</div>
    <div class="ks">{fp(sql_rate)} de leads &middot; sin inscriptos/perdidos</div>
  </div>
  <div class="kpi {_kc(ventas_pct, curva_pct)}">
    <div class="kl">VENTAS / INSCRIPTOS</div>
    <div class="kv">{fn(ventas)}</div>
    <div class="ks">Obj. {fn(obj["ventas"])} &middot; <b>{fp(ventas_pct)}</b> {pace_badge(ventas_pace)}</div>
  </div>
  <div class="kpi">
    <div class="kl">CAC (COSTO POR VENTA)</div>
    <div class="kv">{fc(t_sp / ventas) if ventas else "—"}</div>
    <div class="ks">Inversi\xf3n total / inscriptos</div>
  </div>
</div>

<div class="ob">
  <div style="margin-bottom:20px">
    <div class="oh">
      <div class="ol">\U0001f4ca Leads vs objetivo del mes</div>
      <div class="on">{fn(t_ld)} de {fn(obj["leads"])} &middot; Curva {fp(curva_pct)}</div>
    </div>
    <div class="pb"><div class="pf {_kc(leads_pct, curva_pct)}" style="width:{min(leads_pct,100):.1f}%"></div></div>
    <div style="display:flex;justify-content:space-between;font-size:10px;font-family:DM Mono,monospace;color:var(--hint)">
      <span>0</span>
      <span style="color:var(--pri)">Curva esperada: {fn(int(obj["leads"] * curva_pct / 100))}</span>
      <span>{fn(obj["leads"])}</span>
    </div>
  </div>
  <div>
    <div class="oh">
      <div class="ol">\U0001f3c6 Ventas / inscriptos vs objetivo</div>
      <div class="on">{fn(ventas)} de {fn(obj["ventas"])} &middot; Curva {fp(curva_pct)}</div>
    </div>
    <div class="pb"><div class="pf {_kc(ventas_pct, curva_pct)}" style="width:{min(ventas_pct,100):.1f}%"></div></div>
    <div style="display:flex;justify-content:space-between;font-size:10px;font-family:DM Mono,monospace;color:var(--hint)">
      <span>0</span>
      <span style="color:var(--pri)">Curva esperada: {int(obj["ventas"] * curva_pct / 100)}</span>
      <span>{fn(obj["ventas"])}</span>
    </div>
  </div>
</div>
</section>

<!-- 02 META ADS -->
<section class="sec" id="meta">
<div class="sh"><span class="sn">02</span><h2 class="st">Meta Ads — Prospecting</h2><span class="sb">Nivel adset</span></div>
{'<div class="al al-amber">Sin datos de Meta Ads para el período seleccionado.</div>' if not meta_data else ''}
<div class="tw">
<table class="tbl">
<colgroup>
  <col style="width:40%"><col style="width:12%"><col style="width:10%">
  <col style="width:10%"><col style="width:10%"><col style="width:12%">
</colgroup>
<thead>
<tr>
  <th>Campa\xf1a / Conjunto de anuncios</th>
  <th>Inversi\xf3n</th><th>Leads</th><th>CPL</th><th>CTR</th><th>Impresiones</th>
</tr>
</thead>
<tbody>
<tr class="total-row">
  <td>TOTAL PROSPECTING</td>
  <td>{fc(p_sp)}</td><td>{fn(p_ld) if p_ld else "—"}</td>
  <td>{fc(p_cpl) if p_ld else "—"}</td>
  <td>{fp(p_ctr)}</td><td>{fn(t_imp)}</td>
</tr>
{camps_html}
</tbody>
</table>
</div>
</section>

<!-- 03 CRM -->
<section class="sec" id="crm">
<div class="sh"><span class="sn">03</span><h2 class="st">Funnel CRM</h2><span class="sb">Zoho &middot; Deals</span></div>
{'<div class="al al-amber">Sin datos de CRM disponibles.</div>' if not crm_data else ''}

<div class="fw">
<div class="frow">
  <div class="fstep">
    <div class="fstep-name">CONTACTADOS</div>
    <div class="fstep-val">{fn(contactados)}</div>
    <div class="fstep-rate">Entrada al pipeline</div>
  </div>
  <div class="arr">&rarr;</div>
  <div class="fstep">
    <div class="fstep-name">INTERESADOS</div>
    <div class="fstep-val">{fn(interesados)}</div>
    {conv_rate_html(interesados, contactados)}
  </div>
  <div class="arr">&rarr;</div>
  <div class="fstep">
    <div class="fstep-name">EVALUANDO</div>
    <div class="fstep-val">{fn(evaluando)}</div>
    {conv_rate_html(evaluando, interesados)}
  </div>
  <div class="arr">&rarr;</div>
  <div class="fstep hi2">
    <div class="fstep-name">PROMESA DE PAGO</div>
    <div class="fstep-val">{fn(promesa)}</div>
    {conv_rate_html(promesa, evaluando)}
  </div>
  <div class="arr">&rarr;</div>
  <div class="fstep win">
    <div class="fstep-name" style="color:var(--green)">INSCRIPTO</div>
    <div class="fstep-val">{fn(estudiantes)}</div>
    {f'<div class="fstep-rate ok">{estudiantes/pipeline_total*100:.1f}% del total</div>' if pipeline_total else ''}
  </div>
</div>

<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">
  <div style="background:var(--red-l);border-radius:8px;padding:10px 16px;font-size:12px;color:var(--red)">
    <b>❌ Perdidos:</b> {fn(perdidos)}{f" ({perdidos/mql*100:.1f}% del MQL)" if mql else ""}
  </div>
  {f'<div style="background:var(--off);border-radius:8px;padding:10px 16px;font-size:12px;color:var(--muted)"><b>Leads sin contactar:</b> {crm_data.get("leads_total",0):,}</div>' if crm_data else ""}
</div>

<div class="mq">
  <div class="mb">
    <div class="ml">MQL — Oportunidades del mes</div>
    <div class="mv">{fn(mql)}</div>
    <div class="ms">Deals creados en el mes &middot; {fp(mql_rate)} de leads Meta</div>
  </div>
  <div class="mb g">
    <div class="ml">SQL — Pipeline Activo</div>
    <div class="mv">{fn(sql)}</div>
    <div class="ms">Sin inscriptos ni perdidos &middot; {fp(sql_rate)} de leads Meta</div>
  </div>
</div>
</div>
{fuentes_html}
</section>

<!-- 04 ASESORES -->
<section class="sec" id="asesores">
<div class="sh"><span class="sn">04</span><h2 class="st">Performance por asesor</h2><span class="sb">Leads y ventas del mes</span></div>
{'<div class="al al-amber">Sin datos de asesores disponibles.</div>' if not asesores_list else ''}
{asesores_html}
</section>

<!-- 05 PROGRAMAS -->
<section class="sec" id="programas">
<div class="sh"><span class="sn">05</span><h2 class="st">Inversi\xf3n por programa</h2><span class="sb">Meta ↔ CRM</span></div>
<div class="al al-blue"><b>Matching autom\xe1tico:</b> ✓ = match confirmado &middot; ~ = aproximado (puede diferir en nomenclatura). Verific\xe1 y ajust\xe1 si es necesario.</div>
<div class="tw">
<table class="tbl">
<colgroup>
  <col style="width:38%"><col style="width:12%">
  <col style="width:14%"><col style="width:12%"><col style="width:14%">
</colgroup>
<thead>
<tr>
  <th>Programa</th>
  <th>Leads Meta</th><th>Inversi\xf3n</th><th>CPL</th><th>Pipeline CRM</th>
</tr>
</thead>
<tbody>{progs_html}</tbody>
</table>
</div>
</section>

<!-- 06 REMARKETING -->
<section class="sec" id="remarketing">
<div class="sh"><span class="sn">06</span><h2 class="st">Remarketing</h2><span class="sb">Campa\xf1as de retargeting</span></div>
{remark_kpis}
<div class="tw">
<table class="tbl">
<thead>
<tr><th style="width:50%">Campa\xf1a</th><th>Inversi\xf3n</th><th>Leads</th><th>CPL</th></tr>
</thead>
<tbody>{remark_html}</tbody>
</table>
</div>
</section>

<!-- 07 ACCIONABLES -->
<section class="sec" id="accionables">
<div class="sh"><span class="sn">07</span><h2 class="st">Accionables</h2><span class="sb">Auto-generado</span></div>
{acc_html}
</section>

</main>

<footer>
<div class="container">
<div class="fn">
  Reporte generado el {today.strftime("%d/%m/%Y")} &middot; {period_str} &middot; {client_name}<br>
  Datos: Meta Ads Graph API v21.0 + Zoho CRM &middot; Procesado por Marketing Agent Bot
</div>
</div>
</footer>

<script>
const secs=document.querySelectorAll('section[id]');
const nls=document.querySelectorAll('.nl');
new IntersectionObserver(entries=>{{
  entries.forEach(e=>{{
    if(e.isIntersecting){{
      nls.forEach(l=>l.classList.remove('active'));
      const a=document.querySelector('.nl[href="#'+e.target.id+'"]');
      if(a)a.classList.add('active');
    }}
  }});
}},{{threshold:0.25}}).observe&&secs.forEach(s=>new IntersectionObserver(entries=>{{
  entries.forEach(e=>{{if(e.isIntersecting){{nls.forEach(l=>l.classList.remove('active'));const a=document.querySelector('.nl[href="#'+e.target.id+'"]');if(a)a.classList.add('active');}}}}
  }},{{threshold:0.25}}).observe(s));
</script>
</body>
</html>'''


def _parse_month_from_text(text):
    """Detecta mes/año del texto. Devuelve 'YYYY-MM' o None (= mes actual)."""
    t = text.lower()
    months_es = {
        'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,
        'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12
    }
    import re
    # Formato explícito: 2026-05, 05/2026, 05-2026
    m = re.search(r'(20\d\d)[/-](\d{1,2})', t) or re.search(r'(\d{1,2})[/-](20\d\d)', t)
    if m:
        parts = m.groups()
        if len(parts[0]) == 4:  # YYYY-MM
            return f'{parts[0]}-{parts[1].zfill(2)}'
        else:                   # MM-YYYY
            return f'{parts[1]}-{parts[0].zfill(2)}'
    # Nombre de mes en español
    for name, num in months_es.items():
        if name in t:
            yr_m = re.search(r'20\d\d', t)
            yr = int(yr_m.group()) if yr_m else dt.date.today().year
            return f'{yr}-{str(num).zfill(2)}'
    return None

def h_paid_report(text, state):
    """Genera link del reporte HTML paid media. Soporta mes específico."""
    t = text.lower()
    is_ebds = 'ebds' in t
    slug    = 'ebds' if is_ebds else 'bhu'
    key     = os.environ.get('CALENDAR_KEY', 'sofia2026mkt')
    client_name = 'EBDS' if is_ebds else 'BHU/UIN'

    month_param = _parse_month_from_text(text)
    url = f'https://vercel-deploy-tan-one.vercel.app/report/paid-media?key={key}&client={slug}'
    if month_param:
        url += f'&month={month_param}'
        # Nombre legible del mes
        mnames = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio',
                  'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
        yr, mo = int(month_param[:4]), int(month_param[5:])
        period_label = f'{mnames[mo]} {yr}'
    else:
        today = dt.date.today()
        mnames = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio',
                  'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
        period_label = f'{mnames[today.month]} {today.year} (mes actual)'

    tg_send(
        f'\U0001f4ca *Reporte Paid Media — {client_name}*\n'
        f'_Período: {period_label}_\n\n'
        f'\U0001f517 {url}\n\n'
        f'_Abr\xed el link, guard\xe1 como HTML (Ctrl+S) y compart\xed._'
    )
    return state


@app.route('/report/paid-media')
def paid_media_report_route():
    key      = request.args.get('key', '')
    expected = os.environ.get('CALENDAR_KEY', 'sofia2026mkt')
    if key != expected:
        return Response('<h2>Acceso no autorizado</h2>', status=401, mimetype='text/html')

    client_param = request.args.get('client', 'bhu').lower()
    is_ebds      = (client_param == 'ebds')
    client_name  = 'EBDS' if is_ebds else 'BHU/UIN'
    # Soporte para ?month=YYYY-MM (default: mes actual, último día disponible = hoy)
    month_param  = request.args.get('month', '')
    if month_param and len(month_param) == 7:
        try:
            yr, mo = int(month_param[:4]), int(month_param[5:])
            # Si el mes pedido es anterior al actual, usar el último día del mes
            today = dt.date.today()
            if (yr, mo) < (today.year, today.month):
                import calendar as _cal
                last_day = _cal.monthrange(yr, mo)[1]
                month_date = dt.date(yr, mo, last_day)
            else:
                month_date = today.replace(year=yr, month=mo)
        except Exception:
            month_date = dt.date.today()
    else:
        month_date = dt.date.today()

    meta_data = []
    try:
        meta_data = fetch_meta_monthly(is_ebds=is_ebds, month_date=month_date)
    except Exception as e:
        print(f'paid_media_route meta error: {e}')

    crm_data = None
    try:
        if is_ebds and ZOHO_EBDS_REFRESH_TOKEN:
            crm_data = zoho_crm_funnel_ebds()  # TODO: add month_date support for EBDS
        elif not is_ebds and ZOHO_REFRESH_TOKEN:
            crm_data = zoho_crm_funnel(month_date=month_date)
    except Exception as e:
        print(f'paid_media_route crm error: {e}')

    html = build_paid_media_html(client_name, meta_data, crm_data, month_date)
    return Response(html, mimetype='text/html')
