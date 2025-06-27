import json
import os
import hashlib
import uuid
from http import server
from urllib.parse import parse_qs
import cgi

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
DATA_FILE = os.path.join(BASE_DIR, 'assistants.json')
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
USERS_FILE = os.path.join(BASE_DIR, 'users.json')

os.makedirs(UPLOAD_DIR, exist_ok=True)


def load_assistants():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_assistants(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def render_template(name, **context):
    path = os.path.join(TEMPLATE_DIR, name)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    for k, v in context.items():
        content = content.replace('{{ ' + k + ' }}', v)
    return content


def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_users(data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


SESSIONS = {}

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()


class Handler(server.SimpleHTTPRequestHandler):
    user = None

    def get_user(self):
        cookie = self.headers.get('Cookie', '')
        for part in cookie.split(';'):
            if part.strip().startswith('session='):
                sid = part.split('=', 1)[1]
                return SESSIONS.get(sid)
        return None

    def require_login(self):
        self.user = self.get_user()
        if not self.user:
            self.send_response(303)
            self.send_header('Location', '/login')
            self.end_headers()
            return False
        return True
    def do_GET(self):
        if self.path.startswith('/static/'):
            self.serve_static(self.path[1:])
            return
        if self.path.startswith('/uploads/'):
            self.serve_static(self.path[1:])
            return
        if self.path == '/login':
            self.show_login()
            return
        if self.path == '/register':
            self.show_register()
            return
        if self.path == '/logout':
            self.handle_logout()
            return
        if self.path == '/' or self.path.startswith('/dashboard'):
            if not self.require_login():
                return
            self.show_dashboard()
        elif self.path == '/create':
            if not self.require_login():
                return
            self.show_create()
        elif self.path.startswith('/assistant/'):
            try:
                aid = int(self.path.split('/')[-1])
            except ValueError:
                self.send_error(404)
                return
            if not self.require_login():
                return
            self.show_details(aid)
        elif self.path.startswith('/edit/'):
            try:
                aid = int(self.path.split('/')[-1])
            except ValueError:
                self.send_error(404)
                return
            if not self.require_login():
                return
            self.show_edit(aid)
        elif self.path.startswith('/delete/'):
            try:
                aid = int(self.path.split('/')[-1])
            except ValueError:
                self.send_error(404)
                return
            if not self.require_login():
                return
            self.handle_delete(aid)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/login':
            self.handle_login()
        elif self.path == '/register':
            self.handle_register()
        elif self.path == '/create':
            if not self.require_login():
                return
            self.handle_create()
        elif self.path.startswith('/edit/'):
            try:
                aid = int(self.path.split('/')[-1])
            except ValueError:
                self.send_error(404)
                return
            if not self.require_login():
                return
            self.handle_edit(aid)
        else:
            self.send_error(404)

    def serve_static(self, rel_path):
        path = os.path.join(BASE_DIR, rel_path)
        if not os.path.exists(path):
            self.send_error(404)
            return
        self.send_response(200)
        if rel_path.endswith('.css'):
            self.send_header('Content-Type', 'text/css')
        else:
            self.send_header('Content-Type', 'application/octet-stream')
        self.end_headers()
        with open(path, 'rb') as f:
            self.wfile.write(f.read())

    def show_dashboard(self):
        assistants = load_assistants()
        rows = []
        for a in assistants:
            actions = (
                f"<a href='/assistant/{a['id']}' class='btn btn-sm btn-outline-secondary me-1'>View</a>"
                f"<a href='/edit/{a['id']}' class='btn btn-sm btn-outline-primary me-1'>Edit</a>"
                f"<a href='/delete/{a['id']}' class='btn btn-sm btn-outline-danger'>Delete</a>"
            )
            row = (
                f"<tr><td>{a['id']}</td>"
                f"<td>{a['name']}</td>"
                f"<td>{a.get('description','')}</td>"
                f"<td>{actions}</td></tr>"
            )
            rows.append(row)
        html = render_template('dashboard.html', rows='\n'.join(rows), username=self.user)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def show_create(self):
        html = render_template('create.html', username=self.user)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def handle_create(self):
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers,
                                environ={'REQUEST_METHOD': 'POST',
                                         'CONTENT_TYPE': self.headers['Content-Type']})
        name = form.getfirst('name', '')
        description = form.getfirst('description', '')
        knowledge = form.getfirst('knowledge', '')
        fileitem = form['file'] if 'file' in form else None

        assistants = load_assistants()
        new_id = (assistants[-1]['id'] + 1) if assistants else 1
        filename = ''
        if fileitem and fileitem.filename:
            fname = os.path.basename(fileitem.filename)
            dest_path = os.path.join(UPLOAD_DIR, fname)
            with open(dest_path, 'wb') as f:
                f.write(fileitem.file.read())
            filename = fname
        assistants.append({'id': new_id, 'name': name, 'description': description,
                           'knowledge': knowledge, 'file': filename})
        save_assistants(assistants)
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def show_edit(self, aid):
        assistants = load_assistants()
        a = next((x for x in assistants if x['id'] == aid), None)
        if not a:
            self.send_error(404)
            return
        file_link = f"<a href='/uploads/{a['file']}'>{a['file']}</a>" if a['file'] else 'None'
        html = render_template(
            'edit.html',
            id=str(a['id']),
            name=a['name'],
            description=a.get('description', ''),
            knowledge=a.get('knowledge', ''),
            file_link=file_link,
            username=self.user,
        )
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def handle_edit(self, aid):
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers,
                                environ={'REQUEST_METHOD': 'POST',
                                         'CONTENT_TYPE': self.headers['Content-Type']})
        name = form.getfirst('name', '')
        description = form.getfirst('description', '')
        knowledge = form.getfirst('knowledge', '')
        fileitem = form['file'] if 'file' in form else None

        assistants = load_assistants()
        a = next((x for x in assistants if x['id'] == aid), None)
        if not a:
            self.send_error(404)
            return
        if fileitem and fileitem.filename:
            fname = os.path.basename(fileitem.filename)
            dest_path = os.path.join(UPLOAD_DIR, fname)
            with open(dest_path, 'wb') as f:
                f.write(fileitem.file.read())
            a['file'] = fname
        a['name'] = name
        a['description'] = description
        a['knowledge'] = knowledge
        save_assistants(assistants)
        self.send_response(303)
        self.send_header('Location', f'/assistant/{aid}')
        self.end_headers()

    def handle_delete(self, aid):
        assistants = load_assistants()
        new_list = [x for x in assistants if x['id'] != aid]
        if len(new_list) == len(assistants):
            self.send_error(404)
            return
        save_assistants(new_list)
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def show_login(self):
        html = render_template('login.html')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def handle_login(self):
        length = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(length).decode('utf-8')
        params = parse_qs(data)
        username = params.get('username', [''])[0]
        password = params.get('password', [''])[0]
        users = load_users()
        if any(u['username'] == username and u['password'] == hash_password(password) for u in users):
            sid = uuid.uuid4().hex
            SESSIONS[sid] = username
            self.send_response(303)
            self.send_header('Location', '/')
            self.send_header('Set-Cookie', f'session={sid}; HttpOnly')
            self.end_headers()
        else:
            self.send_response(303)
            self.send_header('Location', '/login')
            self.end_headers()

    def show_register(self):
        html = render_template('register.html')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def handle_register(self):
        length = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(length).decode('utf-8')
        params = parse_qs(data)
        username = params.get('username', [''])[0]
        password = params.get('password', [''])[0]
        users = load_users()
        if any(u['username'] == username for u in users) or not username or not password:
            self.send_response(303)
            self.send_header('Location', '/register')
            self.end_headers()
            return
        users.append({'username': username, 'password': hash_password(password)})
        save_users(users)
        sid = uuid.uuid4().hex
        SESSIONS[sid] = username
        self.send_response(303)
        self.send_header('Location', '/')
        self.send_header('Set-Cookie', f'session={sid}; HttpOnly')
        self.end_headers()

    def handle_logout(self):
        sid = None
        cookie = self.headers.get('Cookie', '')
        for part in cookie.split(';'):
            if part.strip().startswith('session='):
                sid = part.split('=', 1)[1]
        if sid and sid in SESSIONS:
            del SESSIONS[sid]
        self.send_response(303)
        self.send_header('Location', '/login')
        self.send_header('Set-Cookie', 'session=; expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.end_headers()

    def show_details(self, aid):
        assistants = load_assistants()
        a = next((x for x in assistants if x['id'] == aid), None)
        if not a:
            self.send_error(404)
            return
        file_link = f"<a href='/uploads/{a['file']}'>{a['file']}</a>" if a['file'] else 'None'
        html = render_template(
            'details.html',
            id=str(a['id']),
            name=a['name'],
            description=a.get('description', ''),
            knowledge=a.get('knowledge', ''),
            file_link=file_link,
            username=self.user,
        )
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))


def run(server_class=server.HTTPServer, handler_class=Handler):
    addr = ('', 8000)
    httpd = server_class(addr, handler_class)
    print("Serving on http://localhost:8000 ...")
    httpd.serve_forever()


if __name__ == '__main__':
    run()
