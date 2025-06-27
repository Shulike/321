import json
import os
from http import server
from urllib.parse import parse_qs
import cgi

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
DATA_FILE = os.path.join(BASE_DIR, 'assistants.json')
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

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


class Handler(server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/static/'):
            self.serve_static(self.path[1:])
            return
        if self.path.startswith('/uploads/'):
            self.serve_static(self.path[1:])
            return
        if self.path == '/' or self.path.startswith('/dashboard'):
            self.show_dashboard()
        elif self.path == '/create':
            self.show_create()
        elif self.path.startswith('/assistant/'):
            try:
                aid = int(self.path.split('/')[-1])
            except ValueError:
                self.send_error(404)
                return
            self.show_details(aid)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/create':
            self.handle_create()
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
            row = f"<tr><td><a href='/assistant/{a['id']}'>{a['id']}</a></td>" \
                  f"<td>{a['name']}</td><td>{a.get('description','')}</td></tr>"
            rows.append(row)
        html = render_template('dashboard.html', rows='\n'.join(rows))
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def show_create(self):
        html = render_template('create.html')
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

    def show_details(self, aid):
        assistants = load_assistants()
        a = next((x for x in assistants if x['id'] == aid), None)
        if not a:
            self.send_error(404)
            return
        file_link = f"<a href='/uploads/{a['file']}'>{a['file']}</a>" if a['file'] else 'None'
        html = render_template('details.html', name=a['name'], description=a.get('description',''),
                              knowledge=a.get('knowledge',''), file_link=file_link)
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
