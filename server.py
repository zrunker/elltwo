import os
import shutil
import sys
import re
import json
import argparse
import mimetypes
from operator import itemgetter
from collections import namedtuple
import codecs
import random
from subprocess import call

import tornado.ioloop
import tornado.web
import tornado.websocket

import parser

# parse input arguments
ap = argparse.ArgumentParser(description='Elltwo Server.')
ap.add_argument('--path', type=str, default='testing', help='path for markdown files')
ap.add_argument('--port', type=int, default=8500, help='port to serve on')
ap.add_argument('--ip', type=str, default='127.0.0.1', help='ip address to listen on')
ap.add_argument('--demo', action='store_true', help='run in demo mode')
ap.add_argument('--auth', type=str, default=None)
ap.add_argument('--local-libs', action='store_true', help='use local libraries instead of CDN')
args = ap.parse_args()

# others
use_auth = not (args.demo or args.auth is None)
local_libs = args.local_libs
tmp_dir = 'temp'
blank_doc = '#! Title\n\nBody text.'

# randomization
rand_hex = lambda: hex(random.getrandbits(128))[2:].zfill(32)

# authentication
if use_auth:
    with open(args.auth) as fid:
      auth = json.load(fid)
    cookie_secret = auth['cookie_secret']
    username_true = auth['username']
    password_true = auth['password']
else:
    cookie_secret = None

if use_auth:
    def authenticated(get0):
        def get1(self, *args):
            current_user = self.get_secure_cookie('user')
            print(current_user)
            if not current_user:
                self.redirect('/auth/login/')
                return
            get0(self, *args)
        return get1
else:
    def authenticated(get0):
        return get0

# initialize/open database
def read_cells(fname):
    try:
        fid = open(fname, 'r+', encoding='utf-8')
        text = fid.read()
        fid.close()
    except:
        text = ''

    # construct cell dictionary
    CellStruct = namedtuple('CellStruct', 'id body')
    tcells = map(str.strip, text.split('\n\n'))
    fcells = filter(len, tcells)
    if fcells:
        cells = {i: {'prev': i-1, 'next': i+1, 'body': s} for (i, s) in enumerate(fcells)}
        cells[max(cells.keys())]['next'] = -1
        cells[min(cells.keys())]['prev'] = -1
    else:
        cells = {0: {'prev': -1, 'next': 1, 'body': '#! Title'}, 1: {'prev':0, 'next': -1, 'body': 'Body text.'}}
    return cells

def gen_cells(cells):
    cur = [c for c in cells.values() if c['prev'] == -1]
    if cur:
        cur = cur[0]
    else:
        return
    while cur:
        yield cur
        nextid = cur['next']
        cur = cells[nextid] if nextid != -1 else None

def construct_markdown(cells):
    return '\n\n'.join(map(itemgetter('body'), gen_cells(cells)))

def get_base_name(fname):
    ret = re.match(r'(.*)\.md', fname)
    if ret:
        fname_new = ret.group(1)
    else:
        fname_new = fname
    return fname_new

# Tornado time
class AuthLoginHandler(tornado.web.RequestHandler):
    def get(self):
        try:
            errormessage = self.get_argument('error')
        except:
            errormessage = ''
        self.render('login.html', errormessage=errormessage)

    def check_permission(self, password, username):
        if username == username_true and password == password_true:
            return True
        return False

    def post(self):
        username = self.get_argument('username', '')
        password = self.get_argument('password', '')
        auth = self.check_permission(password, username)
        if auth:
            self.set_current_user(username)
            self.redirect('/')
        else:
            error_msg = '?error=' + tornado.escape.url_escape('Login incorrect')
            self.redirect('/auth/login/' + error_msg)

    def set_current_user(self, user):
        if user:
            print(user)
            self.set_secure_cookie('user', tornado.escape.json_encode(user))
        else:
            self.clear_cookie('user')

class AuthLogoutHandler(tornado.web.RequestHandler):
    def get(self):
        self.clear_cookie('user')
        self.redirect(self.get_argument('next', '/'))

class BrowseHandler(tornado.web.RequestHandler):
    @authenticated
    def get(self):
        self.render('directory.html', relpath='', dirname='', pardir='', demo=args.demo)

class PathHandler(tornado.web.RequestHandler):
    @authenticated
    def get(self, path):
        (pardir, fname) = os.path.split(path)
        fpath = os.path.join(args.path, path)
        if os.path.isdir(fpath):
            self.render('directory.html', relpath=path, dirname=fname, pardir=pardir, demo=args.demo)
        elif os.path.isfile(fpath):
            if fname.endswith('.md') or '.' not in fname:
                self.render('editor.html', path=path, curdir=pardir, fname=fname, local_libs=local_libs)
            else:
                (mime_type, encoding) = mimetypes.guess_type(path)
                if mime_type:
                    self.set_header("Content-Type", mime_type)
                fid = open(fpath, 'rb')
                self.write(fid.read())
        else:
            self.write('File %s not found!' % path)

class UploadHandler(tornado.web.RequestHandler):
    @authenticated
    def post(self, rpath):
        file = self.request.files['payload'][0]
        fname = file['filename']
        plocal = os.path.join(args.path, rpath, fname)
        if os.path.isdir(plocal):
            print('Directory exists!')
            return
        out = open(plocal, 'wb')
        out.write(file['body'])

class DemoHandler(tornado.web.RequestHandler):
    def get(self):
        drand = rand_hex()
        fullpath = os.path.join(args.path, drand)
        os.mkdir(fullpath)
        shutil.copy(os.path.join('testing', 'demo.md'), fullpath)
        shutil.copy(os.path.join('testing', 'Jahnke_gamma_function.png'), fullpath)
        self.redirect('/%s' % drand)

class MarkdownHandler(tornado.web.RequestHandler):
    @authenticated
    def post(self, rpath):
        (curdir, fname) = os.path.split(rpath)
        fullpath = os.path.join(args.path, rpath)

        # read source
        fid = open(fullpath, 'r')
        text = fid.read()

        # post output
        self.set_header('Content-Type', 'text/markdown')
        self.set_header('Content-Disposition', 'attachment; filename=%s' % fname)
        self.write(text)
    get = post

class HtmlHandler(tornado.web.RequestHandler):
    @authenticated
    def post(self, rpath):
        (curdir, fname) = os.path.split(rpath)
        fullpath = os.path.join(args.path, rpath)

        # generate html
        fid = open(fullpath, 'r')
        text = fid.read()
        html = parser.convert_html(text)

        # find new name
        ret = re.match(r'(.*)\.md', fname)
        if ret:
            fname_new = ret.group(1)
        else:
            fname_new = fname

        # post output
        self.set_header('Content-Type', 'text/html')
        self.set_header('Content-Disposition', 'attachment; filename=%s.html' % fname_new)
        self.write(html)
    get = post

class LatexHandler(tornado.web.RequestHandler):
    @authenticated
    def post(self, rpath):
        (curdir, fname) = os.path.split(rpath)
        fullpath = os.path.join(args.path, rpath)

        # generate latex
        fid = open(fullpath, 'r')
        text = fid.read()
        (latex, images) = parser.convert_latex(text)

        # find new name
        ret = re.match(r'(.*)\.md', fname)
        if ret:
            fname_new = ret.group(1)
        else:
            fname_new = fname

        # post output
        self.set_header('Content-Type', 'text/latex')
        self.set_header('Content-Disposition', 'attachment; filename=%s.tex' % fname_new)
        self.write(latex)
    get = post

class PdfHandler(tornado.web.RequestHandler):
    @authenticated
    def post(self, rpath):
        (rdir, fname) = os.path.split(rpath)
        fullpath = os.path.join(args.path, rpath)

        # generate latex
        fid = open(fullpath, 'r')
        text = fid.read()
        (latex, images) = parser.convert_latex(text)

        # create unique directory
        comp_dir = os.path.join(tmp_dir, rand_hex())
        os.mkdir(comp_dir)

        # copy over images
        for img in images:
            ret = re.search(r'(^|:)//(.*)', img)
            if ret:
                (rloc, ) = ret.groups()
                (_, rname) = os.path.split(rloc)
                urllib.urlretrieve(url, os.path.join(comp_dir, rname))
            else:
                if img[0] == '/':
                    ipath = img[1:]
                else:
                    ipath = os.path.join(rdir, img)
                shutil.copy(os.path.join(args.path, ipath), comp_dir)

        # find new name
        ret = re.match(r'(.*)\.md', fname)
        if ret:
            fname_new = ret.group(1)
        else:
            fname_new = fname

        # write latex file
        fname_tex = '%s.tex' % fname_new
        ftex = open(os.path.join(comp_dir, fname_tex), 'w+')
        ftex.write(latex)
        ftex.close()

        # compile latex file
        cwd = os.getcwd()
        os.chdir(comp_dir)
        call(['pdflatex', '-interaction=nonstopmode', fname_tex])
        call(['pdflatex', '-interaction=nonstopmode', fname_tex]) # to resolve references
        os.chdir(cwd)

        # read latex file
        fname_pdf = '%s.pdf' % fname_new
        fpdf = open(os.path.join(comp_dir, fname_pdf), 'rb')
        data = fpdf.read()

        # remove compilation directory
        shutil.rmtree(comp_dir)

        # post output
        self.set_header('Content-Type', 'application/pdf')
        self.set_header('Content-Disposition', 'attachment; filename=%s' % fname_pdf)
        self.write(data)
    get = post

class ContentHandler(tornado.websocket.WebSocketHandler):
    def initialize(self):
        print('initializing')
        self.cells = {}

    def allow_draft76(self):
        return True

    def open(self, path):
        print('connection received: %s' % path)
        (self.dirname, self.fname) = os.path.split(path)
        self.basename = get_base_name(self.fname)
        self.temppath = os.path.join(tmp_dir, self.fname)
        self.fullpath = os.path.join(args.path, path)
        self.cells = read_cells(self.fullpath)

    def on_close(self):
        print('connection closing')

    def error_msg(self, error_code):
        if not error_code is None:
            json_string = json.dumps({'type': 'error', 'code': error_code})
            self.write_message(json_string)
        else:
            print('error code not found')

    def on_message(self, msg):
        try:
            print('received message: %s' % msg)
        except Exception as e:
            print(e)
        data = json.loads(msg)
        (cmd, cont) = (data['cmd'], data['content'])
        if cmd in ('fetch', 'revert'):
            if cmd == 'revert':
                self.cells = read_cells(self.fullpath)
            vcells = [{'cid': i,
                       'prev': c['prev'],
                       'next': c['next'],
                       'text': c['body'],
                       'html': parser.parse_cell(c['body']).html()
                      } for (i, c) in self.cells.items()]
            self.write_message(json.dumps({'cmd': 'fetch', 'content': vcells}))
        elif cmd == 'save':
            cid = int(cont['cid'])
            body = cont['body']
            self.cells[cid]['body'] = body
            html = parser.parse_cell(body).html()
            self.write_message({'cmd': 'render', 'content': {'cid': cid, 'html': html}})
        elif cmd == 'create':
            newid = int(cont['newid'])
            prev = int(cont['prev'])
            next = int(cont['next'])
            if prev is not -1:
                self.cells[prev]['next'] = newid
            if next is not -1:
                self.cells[next]['prev'] = newid
            self.cells[newid] = {'prev': prev, 'next': next, 'body': ''}
        elif cmd == 'delete':
            cid = int(cont['cid'])
            prev = int(cont['prev'])
            next = int(cont['next'])
            if prev is not -1:
                self.cells[prev]['next'] = next
            if next is not -1:
                self.cells[next]['prev'] = prev
            del self.cells[cid]
        elif cmd == 'write':
            output = construct_markdown(self.cells)
            fid = codecs.open(self.temppath, 'w+', encoding='utf-8')
            fid.write(output)
            fid.close()
            shutil.move(self.temppath, self.fullpath)
        elif cmd == 'revert':
            self.cells = read_cells(self.fullpath)
            vcells = [{'cid': i, 'prev': c['prev'], 'next': c['next'], 'body': c['body']} for (i, c) in self.cells.items()]
            self.write_message(json.dumps({'cmd': 'results', 'content': vcells}))

class FileHandler(tornado.websocket.WebSocketHandler):
    def initialize(self):
        print('initializing')

    def allow_draft76(self):
        return True

    def open(self, relpath):
        print('connection received')
        self.relpath = relpath
        self.curdir = os.path.join(args.path, self.relpath)
        (self.pardir, self.dirname) = os.path.split(self.curdir)

    def on_close(self):
        print('connection closing')

    def error_msg(self, error_code):
        if not error_code is None:
            json_string = json.dumps({'type': 'error', 'code': error_code})
            self.write_message(json_string)
        else:
            print('error code not found')

    def on_message(self, msg):
        try:
            print('received message: %s' % msg)
        except Exception as e:
            print(e)
        data = json.loads(msg)
        (cmd, cont) = (data['cmd'], data['content'])
        if cmd == 'list':
            if args.demo and self.relpath == '':
                print('Not so fast!')
                return
        elif cmd == 'create':
            if '..' in cont or cont.startswith('/'):
                print('No special directives allowed!')
                return
            fullpath = os.path.join(self.curdir, cont)
            if os.path.exists(fullpath):
                print('File exists.')
                return
            try:
                if cont.endswith('/'):
                    os.mkdir(fullpath)
                else:
                    fid = open(fullpath, 'w+')
                    fid.write(blank_doc)
                    fid.close()
            except:
                print('Could not create file \'%s\'' % fullpath)
        elif cmd == 'delete':
            fullpath = os.path.join(self.curdir, cont)
            if os.path.isdir(fullpath):
                shutil.rmtree(fullpath)
            else:
                os.remove(fullpath)

        # list always
        files = sorted(os.listdir(self.curdir))
        dtype = [os.path.isdir(os.path.join(self.curdir, f)) for f in files]
        dirs = [f for (f, t) in zip(files, dtype) if t]
        docs = [f for (f, t) in zip(files, dtype) if not t and f.endswith('.md')]
        misc = [f for (f, t) in zip(files, dtype) if not t and not f.endswith('.md')]
        cont = {'dirs': dirs, 'docs': docs, 'misc': misc}
        self.write_message(json.dumps({'cmd': 'results', 'content': cont}))

# tornado content handlers
class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/auth/login/?', AuthLoginHandler),
            (r'/auth/logout/?', AuthLogoutHandler),
            (r'/upload/(.*)', UploadHandler),
            (r'/markdown/(.+)', MarkdownHandler),
            (r'/html/(.+)', HtmlHandler),
            (r'/latex/(.+)', LatexHandler),
            (r'/pdf/(.+)', PdfHandler),
            (r'/elledit/(.*)', ContentHandler),
            (r'/diredit/(.*)', FileHandler)
        ]

        if args.demo:
            handlers += [
                (r'/?', DemoHandler),
                (r'/(.+)', PathHandler),
            ]
        else:
            handlers += [
                (r'/?', BrowseHandler),
                (r'/(.*)', PathHandler)
            ]

        settings = dict(
            app_name='Elltwo Editor',
            template_path='templates',
            static_path='static',
            cookie_secret=cookie_secret
        )

        tornado.web.Application.__init__(self, handlers, debug=True, **settings)

# create server
application = Application()
application.listen(args.port, address=args.ip)
tornado.ioloop.IOLoop.current().start()