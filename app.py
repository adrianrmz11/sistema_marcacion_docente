import os, sys, io, logging
from dotenv import load_dotenv
load_dotenv()
# Fuerza UTF-8 para que el logger de DeepFace (con emojis) no falle en Windows cp1252
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s %(message)s')

from flask import Flask, render_template, request, redirect, url_for
from routers.login import login_bp
from routers.marcaciones import marcaciones_bp
from modules.face_worker import start_face_worker

app = Flask(__name__)
app.secret_key = os.environ['SECRET_KEY']
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_DEBUG') != '1',
)

app.register_blueprint(login_bp)
app.register_blueprint(marcaciones_bp)

@app.route('/')
def hello():
    success = request.args.get('success')
    error = request.args.get('error')
    warning = request.args.get('warning')

    if success:
        return render_template('index.html', success=success)
    if warning:
        return render_template('index.html', warning=warning)
    if error:
        return render_template('index.html', error=error)

    return render_template('index.html')

if __name__ == '__main__':
    # En modo debug el reloader lanza dos procesos; solo arrancar el worker en el hijo.
    debug = os.environ.get('FLASK_DEBUG') == '1'
    if not debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_face_worker()
    app.run(host=os.environ.get('APP_HOST', '127.0.0.1'), port=5656, debug=debug)