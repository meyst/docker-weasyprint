#!/usr/bin/env python

import json
import re
import io
import os
import logging
import mimetypes
from functools import wraps
from jinja2 import Template

from flask import Flask, request, make_response, abort, render_template, render_template_string, send_from_directory, url_for
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from weasyprint import HTML, CSS, default_url_fetcher
from weasyprint.text.fonts import FontConfiguration

logging.addLevelName(logging.DEBUG, "\033[1;36m%s\033[1;0m" % logging.getLevelName(logging.DEBUG))
logging.addLevelName(logging.INFO, "\033[1;32m%s\033[1;0m" % logging.getLevelName(logging.INFO))
logging.addLevelName(logging.WARNING, "\033[1;33m%s\033[1;0m" % logging.getLevelName(logging.WARNING))
logging.addLevelName(logging.ERROR, "\033[1;31m%s\033[1;0m" % logging.getLevelName(logging.ERROR))

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s '
    '[in %(pathname)s:%(lineno)d]'
))

app = Flask('pdf')
app.config["UPLOAD_FOLDER"] = "/usr/src/app/uploads/"

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
    payload = request.form['payload']
    #app.logger.info('POST  /pdf?filename=%s' % name)
    #app.logger.info('css = %s' % request.form['css'])
    
    #html_content = render_template_string(request.form['html'],json.loads(payload))
    html_content = Template(request.form['html']).render(json.loads(payload))
    #app.logger.info('html_content = %s' % html_content)
    app.logger.info("OS get cwd: %s" % os.getcwd())
    font_config = FontConfiguration()
    html = HTML(string=html_content, base_url=os.getcwd())
    css = CSS(string=request.form['css'],font_config=font_config)
    #pdf = html.write_pdf(stylesheets=[css],url_fetcher=url_fetcher,font_config=font_config)
    pdf = html.write_pdf(stylesheets=[css],font_config=font_config)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline;filename=%s' % name
    app.logger.info(' ==> POST  /pdf?filename=%s  ok' % name)
    return response

@app.get('/media/<path:path>')
def send_media(path):
    """
    :param path: a path like "posts/<int:post_id>/<filename>"
    """
    app.logger.info("Media Path: %s" % path)
    return send_from_directory(
        directory="/usr/src/app/uploads", path=path
    )

@app.route("/upload", methods = ["POST"])
def save_upload():
    filename = request.headers["filename"]
    content_type = request.headers["content_type"]
    data = request.get_data()
    stream = io.BytesIO(data)
    file = FileStorage( stream=stream, content_type=content_type, filename=filename)
    file.save(app.config["UPLOAD_FOLDER"] + filename)
    app.logger.info("length of input data: {}".format(len(data)))
    app.logger.info("Filename: %s" % filename)
    app.logger.info("Content type: %s" % content_type)
    return "UPLOAD OK"


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