import json
import logging
from urllib.parse import urlencode

import requests


def _get_drive(**kwargs):
    site_id = kwargs.get('site_id')
    if site_id:
        return f'/sites/{site_id}/drive/root'

    user_id = kwargs.get('user_id')
    if not user_id or user_id == 'me':
        return f'/me/drive/root'
    return f'/users/{user_id}/drive/root'


class OneDrive:

    def __init__(self):
        self._api_base_url = 'https://graph.microsoft.com/v1.0/'
        self.http = requests.session()
        self._auth_url = 'https://login.microsoftonline.com/{}/oauth2/v2.0/authorize'
        self._token_url = 'https://login.microsoftonline.com/{}/oauth2/v2.0/token'
        self.access_token = None
        self._redirect_uri = 'https://oneindex.atcaoyufei.workers.dev'
        self.scope = 'offline_access User.Read Sites.ReadWrite.All'
        self.logger = logging.getLogger(self.__class__.__name__)
        self.file_fields = 'id, name, size, folder, audio, video, photo, image, lastModifiedDateTime, @microsoft.graph.downloadUrl'
        self.default_client_id = ''
        self.default_client_secret = ''

    def api(self, api_sub_url, params=None, data=None, method=None, **kwargs):
        self.http.headers['Authorization'] = "Bearer {}".format(self.access_token)
        if api_sub_url.find('http') == -1:
            url = '{}/{}'.format(self._api_base_url.strip('/'), api_sub_url.strip('/'))
        else:
            url = api_sub_url
        response = self.fetch(url, data=data, method=method, params=params, **kwargs)
        if response.status_code == 204:
            return {'status_code': response.status_code}
        if response.status_code in [301, 302]:
            return response.headers
        if len(response.content) > 1:
            return response.json()
        return {'status_code': response.status_code}

    def api_debug(self, api_sub_url, params=None, data=None, method=None, **kwargs):
        return json.dumps(self.api(api_sub_url, params, data, method, **kwargs), indent=4)

    def site_list(self):
        api_params = {'search': '*', '$top': 30, '$select': '*'}
        return self.api('/sites', api_params)

    def user_info(self):
        return self.api('/me')

    def upload_file(self, file_name, file_data, **kwargs):
        drive = _get_drive(**kwargs)
        return self.api(f'{drive}:/{file_name}:/content', method='PUT', data=file_data, timeout=300)

    def file_list(self, folder: str = None, **kwargs):
        fields = kwargs.get('fields') or self.file_fields
        drive = _get_drive(**kwargs)
        params = {
            'select': fields,
            '$top': kwargs.get('limit') or 20,
            '$orderby': 'name desc'
        }

        wd = kwargs.get('wd')
        if wd:
            wd = wd.encode('latin1').decode('utf-8')
            params['$top'] = 100
            return self.api(f"{drive}/search(q='{wd}')", params)

        dest = '/children'
        if folder and folder != '/':
            dest = ':/{}:/children'.format(folder.strip('/'))
        params['$expand'] = 'thumbnails($select=large)'
        return self.api(f'{drive}{dest}', params)

    def delete_file(self, file: str, **kwargs):
        drive = _get_drive(**kwargs)
        return self.api(f'{drive}:/{file}', method='DELETE', timeout=10)

    def get_file(self, file: str, **kwargs):
        drive = _get_drive(**kwargs)
        return self.api(f'{drive}:/{file}')

    def rename_file(self, file: str, new_file: str, **kwargs):
        drive = _get_drive(**kwargs)
        json_data = {'name': new_file}
        return self.api(f'{drive}:/{file}', json=json_data, method='PATCH')

    def create_folder(self, parent_folder: str, folder_name: str, **kwargs):
        drive = _get_drive(**kwargs)
        json_data = {
            '@microsoft.graph.conflictBehavior': 'fail',
            'folder': {'childCount': 1},
            'name': folder_name
        }
        dest = '/children'
        if parent_folder and parent_folder != '/':
            dest = ':/{}:/children'.format(parent_folder.strip('/'))
        return self.api(f'{drive}{dest}', json=json_data)

    def get_drive(self, **kwargs):
        return self.api(f'/me/drive')

    def get_site_drive(self, site_id, **kwargs):
        return self.api(f'/sites/{site_id}/drive')

    def authorize_url(self, **kwargs):
        params = self._default_params(**kwargs)
        params['prompt'] = 'consent'
        params['state'] = kwargs.get('state', '')
        params['response_type'] = 'code'

        del params['client_secret']

        tenant_id = kwargs.get('tenant_id', 'common')
        return '{}?{}'.format(self._auth_url.format(tenant_id), urlencode(params, doseq=True))

    def fetch_token(self, **kwargs) -> dict:
        params = self._default_params(**kwargs)
        params['grant_type'] = 'authorization_code'
        params['code'] = kwargs.get('code')
        tenant_id = kwargs.get('tenant_id', 'common')
        return self.fetch(self._token_url.format(tenant_id), params).json()

    def _default_params(self, **kwargs):
        return {
            'client_id': kwargs.get('client_id') or self.default_client_id,
            'redirect_uri': kwargs.get('redirect_uri', self._redirect_uri),
            'client_secret': kwargs.get('client_secret') or self.default_client_secret,
            'scope': kwargs.get('scope') or self.scope,
        }

    def refresh_token(self, **kwargs) -> dict:
        params = self._default_params(**kwargs)
        params['grant_type'] = 'refresh_token'
        params['refresh_token'] = kwargs.get('refresh_token')
        tenant_id = kwargs.get('tenant_id', 'common')
        return self.fetch(self._token_url.format(tenant_id), params).json()

    def fetch(self, url, data=None, method=None, **kwargs):
        kwargs.setdefault('timeout', 30)
        if (data or kwargs.get('json')) and method is None:
            method = 'POST'

        if method is None:
            method = 'GET'

        response = self.http.request(method, url, data=data, **kwargs)
        if response.ok:
            return response

        raise OneDriveException(response.url, response.status_code, response.text)


class OneDriveException(Exception):

    def __init__(self, api, status_code, message):
        self.api = api
        self.status_code = status_code
        self.message = message
