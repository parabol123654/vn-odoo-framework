# -*- coding: utf-8 -*-
"""Sinh lại i18n/vi.po cho một module, giữ nguyên bản dịch đang có."""
import re, glob, io, collections, datetime, os, sys

MODULE = sys.argv[1]
os.chdir('addons/' + MODULE)
def read(p): return io.open(p, encoding='utf-8').read()

def unescape(s):
    return s.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')


def read_po(path):
    """Read an existing catalogue into ``{msgid: msgstr}``.

    Written by hand rather than with a regex because gettext wraps long strings
    over several quoted lines, and tools such as polib rewrap on save. A
    single-line regex silently misses every wrapped entry, so each regeneration
    would drop exactly the longest and most valuable translations — which is
    what happened before this parser existed.
    """
    entries, msgid, msgstr, mode = {}, None, None, None

    def flush():
        if msgid:
            entries[msgid] = msgstr or ''

    for raw in io.open(path, encoding='utf-8'):
        line = raw.rstrip('\n')
        if line.startswith('msgid '):
            flush()
            msgid, msgstr, mode = unescape(line[7:-1]), '', 'id'
        elif line.startswith('msgstr '):
            msgstr, mode = unescape(line[8:-1]), 'str'
        elif line.startswith('"') and mode:
            piece = unescape(line[1:-1])
            if mode == 'id':
                msgid += piece
            else:
                msgstr += piece
        elif not line.strip():
            flush()
            msgid, msgstr, mode = None, None, None
    flush()
    return entries

models = {}; mixin = {}
for f in sorted(glob.glob('wizard/*.py')):
    src = read(f); m = re.search(r"_name = '([\w.]+)'", src)
    if not m: continue
    fields = {}
    for fm in re.finditer(r"^\s{4}(\w+) = fields\.(\w+)\((.*?)\)\n", src, re.S | re.M):
        fn, ft, body = fm.groups()
        sm = re.search(r"string='([^']+)'", body)
        sels = re.findall(r"\('(\w+)', '([^']+)'\)", body) if ft == 'Selection' else []
        fields[fn] = (sm.group(1) if sm else None, sels)
    d = re.search(r"_description = '([^']+)'", src)
    models[m.group(1)] = {'f': fields,
                          'mix': "_inherit = 'vn.report.wizard.mixin'" in src,
                          'd': d.group(1) if d else ''}
    if m.group(1) == 'vn.report.wizard.mixin': mixin = fields
for n, i in models.items():
    if i['mix']:
        mg = dict(mixin); mg.update(i['f']); i['f'] = mg
models.pop('vn.report.wizard.mixin', None)

merged = collections.OrderedDict()
def put(t, refs, py=False):
    if not t or not t.strip(): return
    e = merged.setdefault(t, {'refs': [], 'py': False})
    for r in refs:
        if r and r not in e['refs']: e['refs'].append(r)
    e['py'] = e['py'] or py

for model, i in sorted(models.items()):
    slug = model.replace('.', '_')
    if i['d']: put(i['d'], ['model:ir.model,name:%s.model_%s' % (MODULE, slug)])
    for fn, (lbl, sels) in sorted(i['f'].items()):
        if lbl: put(lbl, ['model:ir.model.fields,field_description:%s.field_%s__%s' % (MODULE, slug, fn)])
        for k, sl in sels:
            put(sl, ['model:ir.model.fields.selection,name:%s.selection__%s__%s__%s' % (MODULE, slug, fn, k)])
for f in sorted(glob.glob('views/*.xml')):
    s = read(f)
    for vid, arch in re.findall(r'<record id="([^"]+)" model="ir\.ui\.view">(.*?)</record>', s, re.S):
        for x in re.findall(r'\bstring="([^"]+)"', arch):
            put(x, ['model_terms:ir.ui.view,arch_db:%s.%s' % (MODULE, vid)])
        for x in re.findall(r'<div class="text-muted"[^>]*>\s*(.*?)\s*</div>', arch, re.S):
            put(' '.join(x.split()), ['model_terms:ir.ui.view,arch_db:%s.%s' % (MODULE, vid)])
    for aid, b in re.findall(r'<record id="([^"]+)" model="ir\.actions\.act_window">(.*?)</record>', s, re.S):
        nm = re.search(r'<field name="name">([^<]+)</field>', b)
        if nm: put(nm.group(1), ['model:ir.actions.act_window,name:%s.%s' % (MODULE, aid)])
    for mid, at in re.findall(r'<menuitem id="([^"]+)"(.*?)/>', s, re.S):
        nm = re.search(r'name="([^"]+)"', at)
        if nm: put(nm.group(1), ['model:ir.ui.menu,name:%s.%s' % (MODULE, mid)])
for f in glob.glob('report/report_actions.xml'):
    for aid, b in re.findall(r'<record id="([^"]+)" model="ir\.actions\.report">(.*?)</record>', read(f), re.S):
        nm = re.search(r'<field name="name">([^<]+)</field>', b)
        if nm: put(nm.group(1), ['model:ir.actions.report,name:%s.%s' % (MODULE, aid)])
for f in glob.glob('security/*groups*.xml'):
    for gid, b in re.findall(r'<record id="([^"]+)" model="res\.groups">(.*?)</record>', read(f), re.S):
        nm = re.search(r'<field name="name">([^<]+)</field>', b)
        if nm: put(nm.group(1), ['model:res.groups,name:%s.%s' % (MODULE, gid)])

def gettext(src):
    out = []
    for m in re.finditer(r'\b_\(', src):
        i = m.end(); d = 1
        while i < len(src) and d:
            if src[i] == '(': d += 1
            elif src[i] == ')': d -= 1
            i += 1
        parts = re.findall(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"", src[m.end():i-1])
        j = ''.join(a or b for a, b in parts)
        if j: out.append(j)
    return out
for f in sorted(glob.glob('wizard/*.py')) + sorted(glob.glob('models/*.py')) + sorted(glob.glob('services/*.py')):
    for t in gettext(read(f)): put(t, ['code:addons/%s/%s:0' % (MODULE, f)], True)
for JS in glob.glob('static/src/js/*.js'):
    for m in re.finditer(r"_t\(\s*'([^']+)'|_t\(\s*\"([^\"]+)\"", read(JS)):
        put(m.group(1) or m.group(2), ['code:addons/%s/%s:0' % (MODULE, JS)], True)
for XML in glob.glob('static/src/xml/*.xml'):
    xs = read(XML); tt = set()
    for t in re.findall(r'>([^<>{}]+)<', xs):
        t = ' '.join(t.split())
        if t and any(c.isalpha() for c in t): tt.add(t)
    for a in re.findall(r'(?:placeholder|title|alt)="([^"]+)"', xs): tt.add(a.strip())
    for t in tt: put(t, ['code:addons/%s/%s:0' % (MODULE, XML)], True)

old = read_po('i18n/vi.po') if os.path.exists('i18n/vi.po') else {}

SUFFIX = re.compile(r'^(.*?) (\((?:S\d+[a-z]?-DN|B\d+-DN|F\d+-DNN)(?: / S\d+[a-z]?-DN)?\))$')
def translate(text):
    if old.get(text): return old[text]
    m = SUFFIX.match(text)
    if m and old.get(m.group(1)):
        return '%s %s' % (old[m.group(1)], m.group(2))
    return None

def esc(s): return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M+0000')
out = ['# Translation of Odoo Server.',
       '# This file contains the translation of the following modules:',
       '# \t* %s' % MODULE, '#',
       '# Source strings are English, as Odoo expects. Statutory form numbers are',
       '# part of the menu label and read the same in both languages. The headings',
       '# printed inside the reports are absent on purpose: they are fixed by Thong',
       '# tu 200 and are hardcoded in the QWeb templates.', '#',
       'msgid ""', 'msgstr ""', '"Project-Id-Version: Odoo Server 14.0\\n"',
       '"Report-Msgid-Bugs-To: \\n"', '"POT-Creation-Date: %s\\n"' % now,
       '"PO-Revision-Date: %s\\n"' % now, '"Last-Translator: \\n"',
       '"Language-Team: Vietnamese\\n"', '"Language: vi\\n"', '"MIME-Version: 1.0\\n"',
       '"Content-Type: text/plain; charset=UTF-8\\n"', '"Content-Transfer-Encoding: \\n"',
       '"Plural-Forms: nplurals=1; plural=0;\\n"', '']
missing = []
for text, v in sorted(merged.items(), key=lambda x: x[0].lower()):
    tr = translate(text)
    if tr is None: missing.append(text); tr = ''
    out.append('#. module: %s' % MODULE)
    out += ['#: %s' % r for r in v['refs']]
    if v['py'] or '%s' in text or '%(' in text: out.append('#, python-format')
    out += ['msgid "%s"' % esc(text), 'msgstr "%s"' % esc(tr), '']
io.open('i18n/vi.po', 'w', encoding='utf-8').write('\n'.join(out))
print('%-24s term=%d  chưa dịch=%s' % (MODULE, len(merged), missing or 'không có'))
