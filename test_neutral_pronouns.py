"""Player-facing text never assigns a gender.

Players, coaches and GMs are procedurally generated and their gender is unspecified —
the name pool is deliberately mixed — so any text the sim shows a reader must use
they/them. Reported 2026-08-19 from a live game: "Billie Muzzles brings him down for -1
yards", one line in the sack pool that had said `him` since it was written.

⚠️ This scans STRING LITERALS ONLY, via `ast` for Python and a full walk for YAML.
Grepping the raw files does not work: comments and docstrings discuss "he" constantly
(the QB read, the punter's trade-off), so a naive scan is ~30 false positives deep and
gets ignored, which is how the real one survived.

Run: .venv/bin/python test_neutral_pronouns.py   (exits non-zero on any failure)
"""
import ast, io, os, re, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

fails = []
def expect(d, c):
    print(f"  [{'OK' if c else 'FAIL'}] {d}")
    if not c: fails.append(d)

GENDERED = re.compile(r'\b(he|him|his|himself|she|her|hers|herself)\b', re.I)

# Every source that can put a sentence in front of a reader.
PY_SOURCES = ['floosball_game.py', 'managers/coresManager.py', 'managers/awakenedPowers.py',
              'managers/personalityManager.py', 'managers/personalityReactionEngine.py',
              'league_news.py', 'front_page.py', 'standings_view.py']
YAML_SOURCES = sorted(glob.glob('data/templates/*.yaml'))

def pyStrings(path):
    """Every string literal, with its line. Docstrings are excluded — they are
    documentation for us, not copy for a reader."""
    tree = ast.parse(io.open(path, encoding='utf-8').read())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, 'body', None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
               and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.lineno, node.value

def yamlStrings(path):
    import yaml
    def walk(node):
        if isinstance(node, str):
            yield node
        elif isinstance(node, dict):
            for v in node.values(): yield from walk(v)
        elif isinstance(node, list):
            for v in node: yield from walk(v)
    yield from walk(yaml.safe_load(io.open(path, encoding='utf-8')))

pyHits = []
for path in PY_SOURCES:
    if not os.path.exists(path):
        continue
    for lineno, text in pyStrings(path):
        # Only sentences. Identifiers, keys and format specs are not reader-facing.
        if ' ' not in text.strip():
            continue
        m = GENDERED.search(text)
        if m:
            pyHits.append((path, lineno, m.group(0), text.strip()[:72]))

expect(f"no gendered pronoun in engine text ({len(pyHits)} found)", not pyHits)
for h in pyHits[:6]:
    print(f"        {h[0]}:{h[1]}  '{h[2]}'  {h[3]}")

yamlHits = []
for path in YAML_SOURCES:
    for text in yamlStrings(path):
        m = GENDERED.search(text)
        if m:
            yamlHits.append((os.path.basename(path), m.group(0), text.strip()[:72]))

expect(f"no gendered pronoun in the YAML text pools ({len(yamlHits)} found)", not yamlHits)
for h in yamlHits[:6]:
    print(f"        {h[0]}  '{h[1]}'  {h[2]}")

# The specific line that was reported, so a regression is named rather than counted.
sack = [t for _l, t in pyStrings('floosball_game.py') if 'nowhere to throw' in t]
expect("the reported sack line reads 'brings them down'",
       bool(sack) and 'brings them down' in sack[0])

# ⚠️ Guard the guard: if the scanner stops finding text at all it passes vacuously,
# which is the failure mode that makes a clean sweep meaningless.
scanned = sum(1 for p in PY_SOURCES if os.path.exists(p)
              for _l, t in pyStrings(p) if ' ' in t.strip())
yamlScanned = sum(1 for p in YAML_SOURCES for t in yamlStrings(p) if ' ' in t.strip())
expect(f"the scanner is actually reading text ({scanned} py strings, {yamlScanned} yaml)",
       scanned > 500 and yamlScanned > 500)

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("PASS — nothing the sim says assigns a gender.")
