#!/usr/bin/env python

import json
import re
import os
import logging
import mimetypes
from functools import wraps

from flask import Flask, request, make_response, abort, render_template, render_template_string, send_from_directory, url_for
from weasyprint import HTML, CSS, default_url_fetcher
from weasyprint.text.fonts import FontConfiguration

UNICODE_SCHEME_RE = re.compile('^([a-zA-Z][a-zA-Z0-9.+-]+):')
BASE64_DATA_RE = re.compile('^data:[^;]+;base64,')
def get_blocked_url_pattern():
    return get("BLOCKED_URL_PATTERN", "^.*$")

def get(key, default=None):
    return os.environ.get(key) or default

def get_allowed_url_pattern():
    return get("ALLOWED_URL_PATTERN", "^$")

def check_url_access(url):
    allowed_url_pattern = get_allowed_url_pattern()
    blocked_url_pattern = get_blocked_url_pattern()

    try:
        if re.match(allowed_url_pattern, url):
            return True
        if re.match(blocked_url_pattern, url):
            return False
        return True  # pragma: no cover
    except Exception:  # pragma: no cover
        logging.error(
            "Could not parse one of the URL Patterns correctly. Therefor the URL %r was " +
            "blocked. Please check your configuration." % url
        )
        return False
    
def url_fetcher(url):
    if not UNICODE_SCHEME_RE.match(url):  # pragma: no cover
        raise ValueError('Not an absolute URI: %r' % url)

    if url.startswith('file://'):
        return _resolve_file(url.split('?')[0])

    if not check_url_access(url) and not BASE64_DATA_RE.match(url):
        raise PermissionError('Requested URL %r was blocked because of restircion definitions.' % url)

    fetch_result = default_url_fetcher(url)
    if fetch_result["mime_type"] == "text/plain":
        fetch_result["mime_type"] = mimetypes.guess_type(url)[0]

    return fetch_result

def _resolve_file(url):
        abs_file_path = re.sub("^file://", "", url)
        file_path = os.path.relpath(abs_file_path, os.getcwd())

        file = None

        if file is None:  # pragma: no cover
            raise FileNotFoundError('File %r was not found.' % file_path)

        mimetype = file.mimetype
        if mimetype in ["application/octet-stream", "text/plain"]:
            mimetype = mimetypes.guess_type(file_path)[0]

        return {
            'mime_type': mimetype,
            'file_obj': NonClosable(file),
            'filename': file_path
        }


app = Flask('pdf')


def authenticate(f):
    @wraps(f)
    def checkauth(*args, **kwargs):
        if 'X_API_KEY' not in request.headers or os.environ.get('X_API_KEY') == request.headers['X_API_KEY']:
            return f(*args, **kwargs)
        else:
            abort(401)

    return checkauth


def auth():
    if app.config.from_envvar('X_API_KEY') == request.headers['X_API_KEY']:
        return True
    else:
        abort(401)


@app.route('/health')
def index():
    return 'ok'


with app.app_context():
    logging.addLevelName(logging.DEBUG, "\033[1;36m%s\033[1;0m" % logging.getLevelName(logging.DEBUG))
    logging.addLevelName(logging.INFO, "\033[1;32m%s\033[1;0m" % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR))

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'
    ))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.DEBUG)


@app.route('/')
def home():
    return '''
            <h1>PDF Generator</h1>
            <p>The following endpoints are available:</p>
            <ul>
                <li>POST to <code>/pdf?filename=myfile.pdf</code>. The body should
                    contain html or a JSON list of html strings and css strings: { "html": html, "css": [css-file-objects] }</li>
                <li>POST to <code>/multiple?filename=myfile.pdf</code>. The body
                    should contain a JSON list of html strings. They will each
                    be rendered and combined into a single pdf</li>
            </ul>
        '''

@app.route('/pdf', methods=['POST'])
@authenticate
def generate():
    name = request.args.get('filename', 'unnamed.pdf')
    app.logger.info('POST  /pdf?filename=%s' % name)
    app.logger.info('css = %s' % request.form['css'])
    html_content = render_template_string(request.form['html'],name="Stephan")
    app.logger.info('html_content = %s' % html_content)
    font_config = FontConfiguration()
    html = HTML(string=html_content, base_url=os.getcwd())
    css = CSS(string=request.form['css'])
    pdf = html.write_pdf(stylesheets=[css],url_fetcher=url_fetcher,font_config=font_config)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline;filename=%s' % name
    app.logger.info(' ==> POST  /pdf?filename=%s  ok' % name)
    return response


@app.route('/multiple', methods=['POST'])
@authenticate
def multiple():
    name = request.args.get('filename', 'unnamed.pdf')
    app.logger.info('POST  /multiple?filename=%s' % name)
    htmls = json.loads(request.data.decode('utf-8'))
    documents = [HTML(string=html, base_url="").render() for html in htmls]
    pdf = documents[0].copy([page for doc in documents for page in doc.pages]).write_pdf()
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline;filename=%s' % name
    app.logger.info(' ==> POST  /multiple?filename=%s  ok' % name)
    return response


if __name__ == '__main__':
    app.run()


class NonClosable:
    def __init__(self, stream_like):
        self.stream_like = stream_like

    def close(self):
        # Reset file instead of closing it
        if hasattr(self.stream_like, "seek"):
            self.stream_like.seek(0)

    def __bool__(self):
        return self.stream_like.__bool__()

    def __getattr__(self, name):
        return getattr(self.stream_like, name)

    def __iter__(self):
        return self.stream_like.__iter__()

    def __repr__(self):
        return self.stream_like.__repr__()