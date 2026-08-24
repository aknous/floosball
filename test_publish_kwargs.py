"""Every league_news.publish call must match the signature — checked statically.

⚠️ THIS CLASS OF TYPO HAS NOW COST TWO INCIDENTS, AND BOTH WERE INVISIBLE.
`publish` is keyword-only with camelCase names, and its callers are wrapped in broad
excepts, so a snake_case kwarg raises TypeError at the CALL BOUNDARY and is swallowed:

  `_publishCriticalityNews` passed `lead_weight=`  -> 17 seasons of production with ZERO
                                                      criticality rows in the feed.
  `_publishChampionNews`    passed `event_type=`   -> took the SITE DOWN (2026-08-21).

The second one is why this test exists rather than a code review note. The champion
block unpins the previous champion first — a bulk UPDATE that executes immediately and
takes SQLite's single write lock — then calls publish. The TypeError skipped the commit,
so the shared session held that write transaction open; every other session's write then
waited the full 30s busy_timeout and failed (playoff bracket prizes, favourite-team
bonus). And because `runSimulation()` is an asyncio task on the SAME event loop as the
HTTP server, each 30s block froze the health check until Fly pulled the instance and the
proxy reported no healthy instances for tcp/443.

A one-word kwarg typo is a production outage. It is worth a static sweep.

Run: .venv/bin/python test_publish_kwargs.py
"""
import ast, glob, inspect, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.WARNING)
import league_news

fails = []
def expect(label, cond):
    print(f"  [{'OK' if cond else 'FAIL'}] {label}")
    if not cond:
        fails.append(label)


# The signatures we police, and whether they accept arbitrary kwargs.
TARGETS = {}
for fn in ('publish', 'publishSafe'):
    params = inspect.signature(getattr(league_news, fn)).parameters
    TARGETS[fn] = (set(params),
                   any(p.kind is p.VAR_KEYWORD for p in params.values()))

# `publishSafe` forwards **kwargs straight into `publish`, so its real contract is
# publish's names -- checking it against its own (**kwargs) signature would pass anything.
_pubNames, _ = TARGETS['publish']
TARGETS['publishSafe'] = (_pubNames | {'sessionFactory'}, False)

SOURCES = sorted(set(glob.glob('*.py') + glob.glob('managers/*.py') + glob.glob('api/*.py')))
BASES = {'league_news', 'news'}   # module aliases these are called through

bad, checked = [], 0
for path in SOURCES:
    try:
        tree = ast.parse(open(path, encoding='utf-8').read())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute):
            name = f.attr
            base = f.value
            baseName = base.id if isinstance(base, ast.Name) else getattr(base, 'attr', None)
            if baseName not in BASES:
                continue
        elif isinstance(f, ast.Name):
            name = f.id            # `from league_news import publish`
        else:
            continue
        if name not in TARGETS:
            continue
        valid, takesVarKw = TARGETS[name]
        checked += 1
        for kw in node.keywords:
            if kw.arg is None:      # **kwargs splat — nothing static to check
                continue
            if kw.arg not in valid and not takesVarKw:
                bad.append((path, node.lineno, name, kw.arg))

print(f"scanned {len(SOURCES)} files, {checked} publish call sites")
expect("the sweep actually found call sites to check", checked > 0)
for path, line, fn, arg in bad:
    print(f"      {path}:{line}  {fn}(... {arg}=...)")
expect(f"every kwarg matches the signature ({len(bad)} mismatches)", not bad)

# The names that caused the two incidents, pinned so a rename cannot quietly reintroduce
# a snake_case twin alongside them.
print()
for camel, snake in (('eventType', 'event_type'), ('leadWeight', 'lead_weight'),
                     ('teamId', 'team_id'), ('playerId', 'player_id'),
                     ('playerName', 'player_name')):
    expect(f"publish takes {camel}, not {snake}",
           camel in _pubNames and snake not in _pubNames)

print()
if fails:
    print(f"FAILED ({len(fails)}): " + "; ".join(fails))
    raise SystemExit(1)
print("PASS — no publish call can raise TypeError into a swallowing except.")
