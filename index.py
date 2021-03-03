import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from bottle import default_app, template, static_file, request, abort, redirect
from pymongo import MongoClient

from onedrive import OneDrive

DEFAULT_FORMATTER = '%(asctime)s[%(filename)s:%(lineno)d][%(levelname)s]:%(message)s'
logging.basicConfig(format=DEFAULT_FORMATTER, level=logging.INFO)
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception as e:
    logging.debug(e)

app = default_app()

mongo_uri = os.environ.get('MONGO_URI')
client = MongoClient(mongo_uri, connectTimeoutMS=5000, socketTimeoutMS=5000)
db = client.get_database('db0')
col = db['oneindex']
drive_data = col.find_one({'_id': 'img01'})

not_time = int(time.time())
expires_time = int(drive_data.get('expires_time'))
one_drive = OneDrive()


def get_time():
    utc_dt = datetime.utcnow().replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')


if expires_time <= not_time:
    _data = one_drive.refresh_token(**drive_data)
    access_token = _data.get('access_token')
    if not access_token:
        abort(text="refresh token fail.")

    drive_data['access_token'] = access_token
    params = {
        'access_token': _data.get('access_token'),
        'refresh_token': _data.get('refresh_token'),
        'expires_time': int(time.time()) + 3500,
        'update_date': get_time(),
    }
    col.update_one({'_id': drive_data['_id']}, {'$set': params})

one_drive.access_token = drive_data['access_token']


@app.route('/static/<filename:path>')
def send_static(filename):
    return static_file(filename, root='static')


@app.route('/', method='GET')
def index():
    return template('index.html', request=request)


@app.route('/<filename:path>')
def get_file(filename):
    data = one_drive.get_file(filename, site_id=drive_data['site_id'])
    redirect(data['@microsoft.graph.downloadUrl'], 301)


@app.route('/upload', method='POST')
def upload_action():
    upload = request.files.get('file')
    ext = upload.raw_filename.split('.')[-1]
    name = f'{str(time.time()).replace(".", "")}.{ext}'
    return one_drive.upload_file(name, upload.file.read(), site_id=drive_data['site_id'])


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
