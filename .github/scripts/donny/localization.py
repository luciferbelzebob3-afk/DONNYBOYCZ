"""Exact C literal inventory, translation memory and guarded edits (stdlib only)."""
import ast
import difflib
import hashlib
import json
import re
import time

TOKEN = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_]\w*|\d+|[^\s]', re.M)
FORMAT = re.compile(r'%(?:\d+\$)?[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|ll|[hljztL])?[diouxXfFeEgGaAcspn%]')
ESCAPE = re.compile(r'\\(?:[abfnrtv\\\"\'?]|[0-7]{1,3}|x[0-9a-fA-F]+)')
SOURCE_EXT = {'.c', '.h', '.cpp', '.hpp', '.cc', '.js', '.fam'}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def tokens(text):
    return [m for m in TOKEN.finditer(text) if not m[0].startswith(('//', '/*'))]


def literals(text):
    ts = tokens(text)
    result = []
    for i, t in enumerate(ts):
        if not t[0].startswith('"'):
            continue
        # Context contains code tokens only: translations elsewhere cannot alter identity.
        before = [x[0] for x in ts[max(0, i - 16):i] if not x[0].startswith('"')]
        after = [x[0] for x in ts[i + 1:i + 9] if not x[0].startswith('"')]
        result.append(dict(start=t.start(), end=t.end(), literal=t[0],
                           context=' '.join(before + ['<TEXT>'] + after)))
    return result


def identity(path, item):
    return digest(path + '\0' + item['literal'] + '\0' + item['context'])


def source_constraints(text, item):
    """Conservative syntax facts; no inference can turn logs/serialized data into UI."""
    body = ESCAPE.sub('', FORMAT.sub('', item['literal'][1:-1]))
    if not re.search('[A-Za-z]', body):
        return {'technical': 'Formatovaci retezec bez lidskeho textu'}
    ts = tokens(text[:item['start']])
    stack = []
    for index, token in enumerate(ts):
        value = token[0]
        if value == '(':
            previous = ts[index - 1][0] if index else ''
            stack.append([previous if re.fullmatch(r'[A-Za-z_]\w*', previous) else None, 0, index])
        elif value == ')' and stack:
            stack.pop()
        elif value == ',' and stack:
            stack[-1][1] += 1
    calls = [entry for entry in stack if entry[0]]
    if not calls:
        return {}
    name, argument, opening = calls[-1]
    if name.startswith('FURI_LOG_') or name.startswith(('flipper_format_write_', 'flipper_format_read_')):
        return {'technical': 'Log nebo serializovana hodnota/klic: ' + name}
    if name != 'snprintf' or argument != 3:
        return {}
    # Only the unambiguous snprintf(buffer, sizeof(buffer), "%s", literal)
    # form supplies a numeric upper bound here. Other flows remain model/review work.
    prefix = ' '.join(t[0] for t in ts[opening + 1:])
    match = re.fullmatch(r'(\w+) , sizeof \( \1 \) , "%s" ,', prefix)
    if not match:
        return {}
    declarations = re.findall(r'\bchar ' + re.escape(match[1]) + r' \[ (\d+) \]',
                              ' '.join(t[0] for t in ts[:opening]))
    if len(declarations) == 1 and int(declarations[0]) > 1:
        return {'max_bytes': int(declarations[0]) - 1}
    return {}


def validate(source, target, limit=None):
    if not isinstance(target, str) or not re.fullmatch(r'"(?:\\.|[^"\\])*"', target):
        raise ValueError('Neplatny uplny literal')
    if not target.isascii():
        raise ValueError('Text displeje obsahuje diakritiku nebo jine neASCII znaky')
    if FORMAT.findall(source) != FORMAT.findall(target):
        raise ValueError('Zmenene formatovaci parametry')
    if ESCAPE.findall(source) != ESCAPE.findall(target):
        raise ValueError('Zmenene ridici sekvence')
    # Reject unknown C escapes rather than silently accepting implementation-defined syntax.
    for text in (source, target):
        body = ESCAPE.sub('', text[1:-1])
        if '\\' in body:
            raise ValueError('Neznama escape sekvence')
    if limit is not None and len(ast.literal_eval(target).encode('ascii')) > limit:
        raise ValueError('Prekrocen limit retezce')


def bootstrap(path, english, czech):
    """Infer only aligned literal-to-literal edits; never infer changes to code."""
    a, b = tokens(english), tokens(czech)
    memory = []
    sm = difflib.SequenceMatcher(a=[t[0] for t in a], b=[t[0] for t in b], autojunk=False)
    contexts = {x['start']: x for x in literals(english)}
    for op, i, j, k, l in sm.get_opcodes():
        if op != 'replace' or j-i != l-k:
            continue
        if not all(x[0].startswith('"') for x in a[i:j] + b[k:l]):
            continue
        for en, cz in zip(a[i:j], b[k:l]):
            if en[0] == cz[0] or 'DONNY' in cz[0] or 'unleashed-firmware-CZ' in cz[0]:
                continue
            try:
                validate(en[0], cz[0])
            except ValueError:
                continue
            item = contexts[en.start()]
            memory.append(dict(id=identity(path, item), path=path, source=en[0],
                               translation=cz[0], context=item['context'], origin='existing'))
    return memory


def reverse_localized(path, text, memory):
    """Reverse only unambiguous previously paired literals for three-way merging."""
    by_cz = {}
    for m in memory:
        if m['path'] == path:
            by_cz.setdefault(m['translation'], set()).add(m['source'])
    edits = []
    for item in literals(text):
        choices = by_cz.get(item['literal'], set())
        if len(choices) == 1:
            edits.append((item['start'], item['end'], next(iter(choices))))
    for start, end, value in reversed(edits):
        text = text[:start] + value + text[end:]
    return text


def apply_memory(path, text, memory):
    exact = {m['id']: m for m in memory}
    # A changed surrounding call may reuse an unambiguous translation within the same file.
    local = {}
    for m in memory:
        if m['path'] == path:
            local.setdefault(m['source'], set()).add(m['translation'])
    edits = []
    for item in literals(text):
        m = exact.get(identity(path, item))
        choices = local.get(item['literal'], set())
        target = m['translation'] if m else next(iter(choices)) if len(choices) == 1 else None
        if target:
            validate(item['literal'], target)
            edits.append((item['start'], item['end'], target))
    for start, end, value in reversed(edits):
        text = text[:start] + value + text[end:]
    return text, len(edits)


class ModelDeferred(RuntimeError):
    def __init__(self, message, delay=900):
        super().__init__(message)
        self.retry_at = int(time.time()) + max(60, min(int(delay), 86400))


def validate_json(value, schema):
    """Validate the schema subset used by localization before accepting/cache reuse."""
    if 'anyOf' in schema:
        for branch in schema['anyOf']:
            try:
                validate_json(value, branch)
                break
            except ValueError:
                continue
        else:
            raise ValueError('Odpoved neodpovida zadne povolene variante')
    kinds = schema.get('type', [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    checks = {'object': lambda: isinstance(value, dict), 'array': lambda: isinstance(value, list),
              'string': lambda: isinstance(value, str), 'integer': lambda: type(value) is int,
              'number': lambda: type(value) in (int, float), 'boolean': lambda: type(value) is bool,
              'null': lambda: value is None}
    if kinds and not any(checks[k]() for k in kinds):
        raise ValueError('Nespravny typ strukturovane odpovedi')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError('Hodnota mimo povoleny vycet')
    if isinstance(value, str) and not schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', float('inf')):
        raise ValueError('Nespravna delka retezce ve strukturovane odpovedi')
    if isinstance(value, dict):
        props = schema.get('properties', {})
        if not set(schema.get('required', [])).issubset(value):
            raise ValueError('Chybi povinna pole odpovedi')
        if schema.get('additionalProperties') is False and set(value) - set(props):
            raise ValueError('Neocekavana pole odpovedi')
        for name, child in props.items():
            if name in value:
                validate_json(value[name], child)
    if isinstance(value, list):
        if not schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', float('inf')):
            raise ValueError('Nespravny pocet polozek odpovedi')
        for item in value:
            validate_json(item, schema.get('items', {}))


def model_json(instruction, data, schema):
    # Import lazily: the local adapter shares the literal/schema validators above.
    from local_inference import model_json as local_model_json
    return local_model_json(instruction, data, schema)


def array_schema(properties):
    return {'type': 'object', 'properties': {'items': {'type': 'array', 'items': {
        'type': 'object', 'properties': properties, 'required': list(properties),
        'additionalProperties': False}}}, 'required': ['items'], 'additionalProperties': False}
