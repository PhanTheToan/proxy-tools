import http.server
import socketserver
import threading
import urllib.request
import urllib.error
import sqlite3
import json
import uuid
import os
import ssl
from urllib.parse import urlparse
import socket
import re

DB_PATH = "mappings.db"
STATIC_DIR = "static"
CERTS_DIR = "certs"

def build_ssl_context():
    """Default trust store + any internal/private CA certs dropped into backend/certs/*.pem.

    Needed because Python's SSL module (unlike the browser) doesn't read
    certs trusted via the macOS Keychain, so internal CAs (e.g. corporate
    UAT gateways) have to be loaded explicitly here.
    """
    context = ssl.create_default_context()
    if os.path.isdir(CERTS_DIR):
        for fname in os.listdir(CERTS_DIR):
            if fname.endswith(('.pem', '.crt')):
                try:
                    context.load_verify_locations(cafile=os.path.join(CERTS_DIR, fname))
                except ssl.SSLError as e:
                    print(f"Warning: failed to load CA cert {fname}: {e}")
    # OpenSSL 3.x turns this on by default and rejects certs missing an
    # Authority Key Identifier extension — some internal/corporate CAs
    # (e.g. UAT gateways) issue leaf certs without it. Chain trust is still
    # enforced via the loaded CAs above; this only relaxes the structural
    # RFC 5280 conformance check.
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return context

SSL_CONTEXT = build_ssl_context()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS mappings (
            id TEXT PRIMARY KEY,
            local_port INTEGER UNIQUE,
            target_url TEXT,
            is_active BOOLEAN,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Schema migration
    c.execute("PRAGMA table_info(mappings)")
    columns = [col[1] for col in c.fetchall()]
    if 'parent_id' not in columns:
        c.execute('ALTER TABLE mappings ADD COLUMN parent_id TEXT')
    if 'item_type' not in columns:
        c.execute("ALTER TABLE mappings ADD COLUMN item_type TEXT DEFAULT 'proxy'")
    conn.commit()
    conn.close()

def get_mappings():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM mappings ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_mapping(local_port, target_url, description):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    m_id = str(uuid.uuid4())
    try:
        c.execute('INSERT INTO mappings (id, local_port, target_url, is_active, description, item_type) VALUES (?, ?, ?, ?, ?, ?)',
                  (m_id, local_port, target_url, True, description, 'proxy'))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return m_id if success else None

def delete_mapping(m_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT local_port, item_type FROM mappings WHERE id = ?', (m_id,))
    row = c.fetchone()
    
    ports_to_stop = []
    
    if row:
        if row[1] == 'folder':
            # Cascade delete: get all children (simplified to 1 level for now, or just use recursive CTE if needed, but a simple loop works if we assume 1-2 levels, or just delete by parent_id)
            # Actually, to delete all descendants:
            def get_all_descendants(parent_id):
                desc = []
                c.execute('SELECT id, local_port FROM mappings WHERE parent_id = ?', (parent_id,))
                children = c.fetchall()
                for child in children:
                    desc.append(child)
                    desc.extend(get_all_descendants(child[0]))
                return desc
            
            descendants = get_all_descendants(m_id)
            for d in descendants:
                if d[1]: # if has port
                    ports_to_stop.append(d[1])
                c.execute('DELETE FROM mappings WHERE id = ?', (d[0],))
                
        else:
            if row[0]:
                ports_to_stop.append(row[0])
                
        c.execute('DELETE FROM mappings WHERE id = ?', (m_id,))
        conn.commit()
        
    conn.close()
    return ports_to_stop

def toggle_mapping(m_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT is_active, local_port, target_url FROM mappings WHERE id = ?', (m_id,))
    row = c.fetchone()
    if row:
        new_status = not row[0]
        port = row[1]
        target_url = row[2]
        c.execute('UPDATE mappings SET is_active = ? WHERE id = ?', (new_status, m_id))
        conn.commit()
        conn.close()
        return new_status, port, target_url
    conn.close()
    return None, None, None

# --- Proxy Server ---
class ProxyRequestHandler(http.server.BaseHTTPRequestHandler):
    target_url = None
    local_port = None

    def do_GET(self): self.handle_request()
    def do_POST(self): self.handle_request()
    def do_PUT(self): self.handle_request()
    def do_DELETE(self): self.handle_request()
    def do_PATCH(self): self.handle_request()
    def do_OPTIONS(self): self.handle_request()

    def handle_request(self):
        url = self.target_url.rstrip('/') + self.path
        parsed = urlparse(self.target_url)
        
        req_headers = {}
        for k, v in self.headers.items():
            if k.lower() not in ['host', 'connection', 'content-length', 'accept-encoding']:
                req_headers[k] = v
        req_headers['Host'] = parsed.netloc

        body = None
        if 'Content-Length' in self.headers:
            body = self.rfile.read(int(self.headers['Content-Length']))
            
        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        
        opener = urllib.request.build_opener(NoRedirectHandler, urllib.request.HTTPSHandler(context=SSL_CONTEXT))
        req = urllib.request.Request(url, method=self.command, headers=req_headers, data=body)
        try:
            response = opener.open(req, timeout=10)
        except urllib.error.HTTPError as e:
            response = e
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode())
            return
            
        status_code = getattr(response, 'code', getattr(response, 'status', 500))
        self.send_response(status_code)
        res_headers = response.getheaders() if hasattr(response, 'getheaders') else response.headers.items()
        
        try:
            body = response.read()
        except Exception:
            body = b""
        
        content_type = response.headers.get('Content-Type', '').lower()
        is_text = any(t in content_type for t in ['text/', 'application/json', 'application/javascript', 'application/x-javascript'])
        
        if is_text and body:
            try:
                text_body = body.decode('utf-8', errors='ignore')
                mappings = [m for m in get_mappings() if m['item_type'] == 'proxy' and m['target_url']]
                mapped_targets = {m['target_url'].rstrip('/') for m in mappings}
                
                found_prefixes = set(re.findall(r'https?://[a-zA-Z0-9.-]+', text_body))
                for p in found_prefixes:
                    p_parsed = urlparse(p)
                    netloc = p_parsed.netloc
                    if not netloc or 'localhost' in netloc or '127.0.0.1' in netloc: continue
                    blacklist = ['w3.org', 'google.com', 'googleapis.com', 'gstatic.com', 'facebook.net', 'facebook.com', 'twitter.com', 'googletagmanager.com', 'cloudflare.com', 'jquery.com', 'bootstrapcdn.com', 'jsdelivr.net']
                    if any(netloc.endswith(b) for b in blacklist):
                        continue
                    target_base = f"{p_parsed.scheme}://{netloc}"
                    if target_base not in mapped_targets:
                        get_or_create_auto_mapping(target_base, self.target_url)
                        mapped_targets.add(target_base)
                
                # Re-fetch mappings in case auto-discovery added new ones!
                mappings = [m for m in get_mappings() if m['item_type'] == 'proxy' and m['target_url']]
                
                for m in mappings:
                    t_url = m['target_url'].rstrip('/')
                    l_url = f"http://localhost:{m['local_port']}"
                    if not t_url: continue
                    text_body = text_body.replace(t_url, l_url)
                    t_netloc = urlparse(t_url).netloc
                    if not t_netloc: continue
                    text_body = text_body.replace(f"//{t_netloc}", f"//localhost:{m['local_port']}")
                    text_body = text_body.replace(f"\\/\\/{t_netloc}", f"\\/\\/localhost:{m['local_port']}")
                body = text_body.encode('utf-8')
            except Exception as e:
                print(f"Error processing body: {e}")
        
        for k, v in res_headers:
            if k.lower() not in ['transfer-encoding', 'connection', 'content-length', 'content-encoding']:
                if k.lower() == 'location':
                    loc_parsed = urlparse(v)
                    if loc_parsed.scheme in ['http', 'https']:
                        loc_target = f"{loc_parsed.scheme}://{loc_parsed.netloc}"
                        if loc_target == self.target_url.rstrip('/'):
                            v = v.replace(loc_target, f"http://localhost:{self.local_port}", 1)
                        else:
                            new_port = get_or_create_auto_mapping(loc_target, self.target_url)
                            v = v.replace(loc_target, f"http://localhost:{new_port}", 1)
                elif k.lower() == 'set-cookie':
                    v = re.sub(r';\s*Domain=[^;]+', '', v, flags=re.IGNORECASE)
                self.send_header(k, v)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass # Client disconnected prematurely

    def log_message(self, format, *args):
        pass # Suppress proxy logging

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True

class ProxyManager:
    def __init__(self):
        self.servers = {}

    def start_proxy(self, port, target_url):
        if port in self.servers:
            return
        
        class Handler(ProxyRequestHandler):
            pass
        Handler.target_url = target_url
        Handler.local_port = port

        host = os.getenv('HOST', '127.0.0.1')
        server = ThreadedHTTPServer((host, port), Handler)
        server.daemon_threads = True
        
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.servers[port] = server

    def stop_proxy(self, port):
        if port in self.servers:
            self.servers[port].shutdown()
            self.servers[port].server_close()
            del self.servers[port]

proxy_manager = ProxyManager()

def get_root_domain(netloc):
    parts = netloc.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[-2:])
    return netloc

def get_or_create_folder(folder_name, parent_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if parent_id:
        c.execute('SELECT id FROM mappings WHERE item_type = "folder" AND description = ? AND parent_id = ?', (folder_name, parent_id))
    else:
        c.execute('SELECT id FROM mappings WHERE item_type = "folder" AND description = ? AND parent_id IS NULL', (folder_name,))
    row = c.fetchone()
    if row:
        conn.close()
        return row[0]
    m_id = str(uuid.uuid4())
    c.execute('INSERT INTO mappings (id, target_url, is_active, description, item_type, parent_id) VALUES (?, ?, ?, ?, ?, ?)',
              (m_id, "", True, folder_name, 'folder', parent_id))
    conn.commit()
    conn.close()
    return m_id

def get_or_create_auto_mapping(target_url_base, parent_url=""):
    target_url_base = target_url_base.rstrip('/')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT local_port FROM mappings WHERE item_type = 'proxy' AND (target_url = ? OR target_url = ? || '/')", (target_url_base, target_url_base))
    row = c.fetchone()
    
    if row:
        conn.close()
        return row[0]
        
    parent_id = None
    if parent_url:
        parent_url_clean = parent_url.rstrip('/')
        c.execute("SELECT id FROM mappings WHERE item_type = 'proxy' AND (target_url = ? OR target_url = ? || '/')", (parent_url_clean, parent_url_clean))
        p_row = c.fetchone()
        if p_row:
            parent_id = p_row[0]
            
    conn.close()
            
    folder_name = "External"
    t_netloc = urlparse(target_url_base).netloc
    p_netloc = urlparse(parent_url).netloc if parent_url else ""
    
    social_domains = ['github.com', 'facebook.com', 'google.com', 'twitter.com', 'linkedin.com', 'fontawesome.io', 'youtube.com', 'gstatic.com', 'googleapis.com', 'blindsignals.com', 'opensource.org', 'apache.org', 'semantic-ui.com']
    
    if p_netloc and get_root_domain(t_netloc) == get_root_domain(p_netloc):
        folder_name = "Subdomains"
    elif any(sd in t_netloc for sd in social_domains):
        folder_name = "Social & CDN"
        
    actual_parent_id = get_or_create_folder(folder_name, parent_id) if parent_id else None
    
    docker_env = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
    if docker_env:
        start_port = 8100
        end_port = 11100
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT local_port FROM mappings WHERE item_type = "proxy" AND local_port IS NOT NULL')
        used_ports = {row[0] for row in c.fetchall()}
        conn.close()
        
        port = None
        for p in range(start_port, end_port + 1):
            if p not in used_ports:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.bind(('0.0.0.0', p))
                    port = p
                    s.close()
                    break
                except Exception:
                    pass
        if port is None:
            raise Exception("No free ports available in the allocated Docker range (8100-11100)")
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()
    
    m_id = str(uuid.uuid4())
    desc = "Auto-discovered" if not parent_url else f"Auto-discovered via {p_netloc}"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO mappings (id, local_port, target_url, is_active, description, item_type, parent_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (m_id, port, target_url_base, True, desc, 'proxy', actual_parent_id))
    conn.commit()
    conn.close()
    
    proxy_manager.start_proxy(port, target_url_base)
    return port

# --- API and UI Server ---
class APIServerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        if self.path == '/api/v1/mappings':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(get_mappings()).encode())
        else:
            if not os.path.exists(os.path.join(STATIC_DIR, self.path.lstrip('/'))):
                self.path = '/index.html'
            super().do_GET()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/v1/mappings':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            port = data.get('local_port')
            url = data.get('target_url')
            desc = data.get('description', '')
            
            if not port or not url:
                self.send_error_json(400, "Missing required fields")
                return
                
            m_id = add_mapping(port, url, desc)
            if m_id:
                try:
                    proxy_manager.start_proxy(port, url)
                    self.send_success_json({'success': True, 'id': m_id})
                except Exception as e:
                    delete_mapping(m_id)
                    self.send_error_json(500, f"Failed to bind port: {e}")
            else:
                self.send_error_json(400, "Port already in use")
        
        elif self.path == '/api/v1/folders':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            folder_name = data.get('name')
            parent_id = data.get('parent_id')
            
            if not folder_name:
                self.send_error_json(400, "Missing folder name")
                return
                
            m_id = get_or_create_folder(folder_name, parent_id)
            self.send_success_json({'success': True, 'id': m_id})
            
        elif self.path.startswith('/api/v1/mappings/') and self.path.endswith('/toggle'):
            m_id = self.path.split('/')[4]
            new_status, port, target_url = toggle_mapping(m_id)
            if port is not None:
                if new_status:
                    try:
                        proxy_manager.start_proxy(port, target_url)
                    except Exception as e:
                        toggle_mapping(m_id)
                        self.send_error_json(500, f"Failed to bind port: {e}")
                        return
                else:
                    proxy_manager.stop_proxy(port)
                self.send_success_json({'success': True, 'is_active': new_status})
            else:
                self.send_error_json(404, "Not found")
        else:
            self.send_response(404)
            self.end_headers()

    def do_PUT(self):
        if self.path.startswith('/api/v1/mappings/') and self.path.endswith('/move'):
            m_id = self.path.split('/')[4]
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            new_parent_id = data.get('parent_id')
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('UPDATE mappings SET parent_id = ? WHERE id = ?', (new_parent_id, m_id))
            conn.commit()
            conn.close()
            
            self.send_success_json({'success': True})
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        if self.path.startswith('/api/v1/folders/') and self.path.endswith('/empty'):
            folder_id = self.path.split('/')[4]
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            def get_all_descendants(parent_id):
                desc = []
                c.execute('SELECT id, local_port, item_type FROM mappings WHERE parent_id = ?', (parent_id,))
                children = c.fetchall()
                for child in children:
                    desc.append(child)
                    if child[2] == 'folder':
                        desc.extend(get_all_descendants(child[0]))
                return desc
            
            descendants = get_all_descendants(folder_id)
            for d in descendants:
                if d[1]: # if proxy has port
                    proxy_manager.stop_proxy(d[1])
                c.execute('DELETE FROM mappings WHERE id = ?', (d[0],))
            
            conn.commit()
            conn.close()
            self.send_success_json({'success': True})
            return

        if self.path.startswith('/api/v1/mappings/'):
            m_id = self.path.split('/')[4]
            ports = delete_mapping(m_id)
            for port in ports:
                proxy_manager.stop_proxy(port)
            self.send_success_json({'success': True})
        else:
            self.send_response(404)
            self.end_headers()

    def send_error_json(self, code, msg):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'error': msg}).encode())
        
    def send_success_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

if __name__ == '__main__':
    init_db()
    for m in get_mappings():
        if m['is_active'] and m['item_type'] == 'proxy' and m['local_port']:
            try:
                proxy_manager.start_proxy(m['local_port'], m['target_url'])
            except Exception as e:
                print(f"Failed to start proxy {m['local_port']}: {e}")
                
    port = 8085
    host = os.getenv('HOST', '127.0.0.1')
    server = ThreadedHTTPServer((host, port), APIServerHandler)
    print(f"LRPM UI running on http://{host}:{port}")
    server.serve_forever()
