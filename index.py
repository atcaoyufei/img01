import json
import logging
import time

from bottle import default_app, template, static_file, request, abort

from config import drive_data
from onedrive import OneDrive

DEFAULT_FORMATTER = '%(asctime)s[%(filename)s:%(lineno)d][%(levelname)s]:%(message)s'
logging.basicConfig(format=DEFAULT_FORMATTER, level=logging.INFO)

app = default_app()

not_time = int(time.time())
expires_time = int(drive_data.get('expires_time'))
one_drive = OneDrive()

if expires_time <= not_time:
    _data = one_drive.refresh_token(**drive_data)
    access_token = _data.get('access_token')
    refresh_token = _data.get('refresh_token')
    if not access_token:
        abort(text="refresh token fail.")

    drive_data['access_token'] = access_token
    if refresh_token:
        drive_data['refresh_token'] = refresh_token
    with open('config.py', 'w') as f:
        f.write(f"drive_data = {json.dumps(drive_data, indent=4)}")

one_drive.access_token = drive_data['access_token']


@app.route('/static/<filename:path>')
def send_static(filename):
    return static_file(filename, root='static')


@app.route('/', method='GET')
def index():
    return template('index.html', request=request)


@app.route('/upload', method='POST')
def upload_action():
    upload = request.files.get('file')
    ext = upload.raw_filename.split('.')[-1]
    name = f'{str(time.time()).replace(".", "")}.{ext}'
    return one_drive.upload_file(name, upload.file.read(), site_id=drive_data['site_id'])


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
