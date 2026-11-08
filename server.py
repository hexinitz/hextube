#!/usr/bin/env python3
"""Local server for the HexTube talks app. Standard library only.
  python3 server.py            -> http://127.0.0.1:8000
Serves static/ and a tiny JSON API:
  GET  /api/videos    curated list + data/extra_videos.json (YouTube finds)
  GET  /api/watched   {vid: epoch_ms}
  POST /api/watched   {"vid": "...", "watched": true|false}   (stored in data/watched.json)"""
import json, os, re, sys, tempfile, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEOS, META, WATCHED, EXTRA = (os.path.join(HERE, 'data', f) for f in ('videos.json', 'youtube_meta.jsonl', 'watched.json', 'extra_videos.json'))
VID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')
lock = threading.Lock()

def load_videos():
    videos = json.load(open(VIDEOS, encoding='utf-8'))
    out = list(videos)
    n_hn = len(out)
    if os.path.exists(EXTRA):
        try: extra = json.load(open(EXTRA, encoding='utf-8'))
        except ValueError: extra = []
        have = {v['vid'] for v in out}
        out += [e for e in extra if e['vid'] not in have]
    return {'videos': out, 'total_curated': len(videos), 'extra': len(out) - n_hn}

def read_watched():
    try: return json.load(open(WATCHED, encoding='utf-8'))
    except (OSError, ValueError): return {}

def write_watched(d):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(WATCHED), suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8') as f: json.dump(d, f)
    os.replace(tmp, WATCHED)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw): super().__init__(*a, directory=os.path.join(HERE, 'static'), **kw)
    def log_message(self, *a): pass
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body))); self.send_header('Cache-Control', 'no-store'); self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/api/videos': return self._json(load_videos())
        if p == '/api/watched':
            with lock: return self._json(read_watched())
        super().do_GET()
    def do_POST(self):
        if self.path != '/api/watched': return self._json({'error': 'not found'}, 404)
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + (self.headers.get('Host') or ''): return self._json({'error': 'bad origin'}, 403)
        if 'application/json' not in (self.headers.get('Content-Type') or ''): return self._json({'error': 'json only'}, 415)
        try:
            n = int(self.headers.get('Content-Length') or 0)
            if not 0 < n < 2048: raise ValueError
            req = json.loads(self.rfile.read(n))
            vid, on = req['vid'], bool(req['watched'])
            if not VID_RE.match(vid): raise ValueError
        except (ValueError, KeyError, TypeError): return self._json({'error': 'bad request'}, 400)
        with lock:
            d = read_watched()
            if on: d.setdefault(vid, int(__import__('time').time() * 1000))
            else: d.pop(vid, None)
            write_watched(d)
            return self._json(d)

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if not os.path.exists(VIDEOS): sys.exit('data/videos.json is missing. Run: python3 build_data.py <path to hackertube-data>')
    print(f'HexTube running at http://127.0.0.1:{port}  (Ctrl+C to stop)')
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
