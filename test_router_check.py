from core.router import Router

r = Router()

tests = [
    ('/help', 'Commands'),
    ('/status', 'ATLAS status'),
    ('/tools', 'Loaded tools'),
    ('/memory', 'Memory count'),
    ('/debug', 'Debug Report'),
    ('/screen', 'Screen'),
    ('/undo', 'Nothing to undo'),
    ('/skills', 'Loaded skills'),
    ('/vision', 'screenshot'),
    ('spotify current', 'Spotify'),
    ('spotify play', 'Spotify'),
    ('spotify search test', 'Spotify'),
    ('spotify volume 50', 'Spotify'),
    ('spotify next', 'Spotify'),
    ('spotify pause', 'Spotify'),
    ('spotify devices', 'Spotify'),
    ('system info', 'Platform'),
    ('read file', 'file path'),
    ('list folder', 'directory path'),
    ('web search python', 'Search'),
    ('take screenshot', 'screenshot'),
    ('open app notepad', 'Launched'),
    ('copy to clipboard hello', 'Copied'),
    ('mouse position', 'Mouse position'),
]

print('=== Router Dispatch Tests ===')
for cmd, expected in tests:
    result = r.route(cmd)
    ok = expected in result
    status = 'OK' if ok else 'FAIL'
    print(f'{status}: "{cmd}" -> {expected}')
    if not ok:
        print(f'  Got: {result[:100]}')