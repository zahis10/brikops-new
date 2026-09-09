URGENCIES = ('urgent', 'normal')
STATUSES = ('open', 'done', 'dismissed')
ESCALATABLE = ('short', 'borderline')


def build_spare_context(spare_status):
    context = {'short': [], 'borderline': []}
    for row in (spare_status or {}).get('categories') or []:
        if row.get('status') == 'short':
            context['short'].append({
                'name': row.get('name', ''),
                'missing': row.get('missing') or 0,
                'measure': row.get('measure'),
                'zero': bool(row.get('entered') and row.get('actual') == 0),
            })
        elif row.get('status') == 'borderline':
            context['borderline'].append(row.get('name', ''))
    return context


def can_escalate(spare_status):
    return (spare_status or {}).get('overall') in ESCALATABLE


def context_line(context):
    context = context or {}
    short_items = []
    for row in context.get('short') or []:
        name = row.get('name', '')
        missing = row.get('missing') or 0
        if missing > 0:
            short_items.append(f"{name} {missing}")
        elif row.get('zero'):
            short_items.append(f"{name} (אין ספייר)")
        else:
            short_items.append(name)
    parts = []
    if short_items:
        parts.append(f"חסר: {', '.join(short_items)}")
    borderline = context.get('borderline') or []
    if borderline:
        parts.append(f"גבולי: {', '.join(borderline)}")
    return ' · '.join(parts)


def default_text(urgency, unit_label, context):
    if urgency == 'urgent':
        count = len((context or {}).get('short') or [])
        shortage = 'חסר סוג אחד' if count == 1 else f'חסר {count} סוגים'
        return f"דחוף להזמין ריצוף ספייר לדירה {unit_label} — {shortage}"
    return f"להשלים ריצוף ספייר לדירה {unit_label} — {context_line(context)}"


def escalation_body(esc):
    kind = 'דחופה' if esc.get('urgency') == 'urgent' else 'חדשה'
    return (
        f"הקפצה {kind} מ{esc['requested_by']['name']}: {esc['text']} — "
        f"{esc['labels']['building']} · דירה {esc['labels']['unit']}"
    )


def note_body(esc, actor_name, note):
    return f"הערה חדשה מ{actor_name} על ההקפצה בדירה {esc['labels']['unit']}: {note}"


def assigned_body(esc, actor_name):
    return (
        f"הקפצה הועברה אליך ע״י {actor_name}: {esc['text']} — "
        f"{esc['labels']['building']} · דירה {esc['labels']['unit']}"
    )


def resolved_body(esc):
    state = 'טופלה' if esc.get('status') == 'done' else 'סומנה כלא רלוונטית'
    body = (
        f"ההקפצה על דירה {esc['labels']['unit']} {state} "
        f"ע״י {esc['resolved_by']['name']}"
    )
    if esc.get('resolution_note'):
        body += f" — \"{esc['resolution_note']}\""
    return body