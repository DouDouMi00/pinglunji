from quart import Quart, websocket, request, send_from_directory
import asyncio, random, os
from .logger import timeLog
from .config import HTTP_SERVER_PASSWORD

staticFilesPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../static')
app = Quart(__name__, static_folder=staticFilesPath, static_url_path='/')
pinglunji = {}

def getIp(ws = False):
    instance = websocket if ws else request
    ip = instance.headers['X-Forwarded-For'] if 'X-Forwarded-For' in instance.headers else instance.remote_addr
    return ip

@app.route('/robots.txt', methods=['GET'])
async def noRobots():
    return 'User-agent: *\nDisallow: /', 200, { 'Content-Type': 'text/plain' }

@app.route('/', methods=['GET'])
async def index():
    global staticFilesPath
    return await send_from_directory(staticFilesPath, 'index.html')

@app.after_request
def addHeader(response):
    response.cache_control.no_cache = True
    return response

@app.route('/api/running_mode', methods=['GET'])
async def getRunningMode():
    return { 'status': 0, 'msg': { 'remote': True } }

@app.route('/api/<path:path>', methods=['GET', 'POST'])
async def proxyRequest(path):
    global pinglunji
    if request.args.get('token') not in pinglunji:
        return { 'status': -1, 'msg': 'token error' }, 401
    target = pinglunji[request.args.get('token')]
    requestID = random.randrange(100000000, 999999999)
    ip = getIp()
    timeLog(f"[Client] Forwarding http request {'/api/' +path} to server which token: {request.args.get('token')}, host: {ip}")
    await target['server'].send_json({
        'type': 'request',
        'id': requestID,
        'url': '/api/' + path,
        'query': request.args,
        'method': request.method,
        'data': await request.json,
    })
    while target['response'] == None or target['response']['id'] != requestID:
        await target['event'].wait()
    timeLog(f"[Client] Got http response from server which token: {request.args.get('token')}, host: {ip}")
    if target['response']['data'] == None:
        return { 'status': -1, 'msg': 'error' }, 500
    return target['response']['data']

@app.websocket('/ws/client')
async def wsClient():
    global pinglunji
    if 'token' not in websocket.args or websocket.args['token'] not in pinglunji:
        await websocket.close(code=-1, reason='token error')
        return
    token = websocket.args['token']
    ip = getIp(ws=True)
    timeLog(f'[Client] New connection from token: {token}, host: {ip}')
    try:
        pinglunji[token]['client'].append(websocket._get_current_object())
        while True:
            await websocket.receive()
    except asyncio.CancelledError:
        timeLog(f'[Client] Disconnected from token: {token}, host: {ip}')
        if token in pinglunji:
            pinglunji[token]['client'].remove(websocket._get_current_object())
        raise

@app.websocket('/ws/server')
async def wsServer():
    ip = getIp(ws=True)
    if 'password' not in websocket.args or 'token' not in websocket.args:
        timeLog(f'[Server] Password or token not found from host: {ip}')
        await websocket.close(code=-1003, reason='password or token not found!')
        return
    if websocket.args['password'] != HTTP_SERVER_PASSWORD:
        timeLog(f'[Server] Password incorrect from host: {ip}')
        await websocket.close(code=-1002, reason='server password is incorrect!')
        return
    global pinglunji
    token = websocket.args['token']
    if token in pinglunji:
        await websocket.close(code=-1001, reason='this token has been used!')
        return
    pinglunji[token] = {
        'client': [],
        'server': websocket._get_current_object(),
        'event': asyncio.Event(),
        'response': None,
    }
    timeLog(f'[Server] New connection from token: {token}, host: {ip}')
    try:
        while True:
            message = await websocket.receive_json()
            if message['type'] == 'response':
                pinglunji[token]['response'] = message
                pinglunji[token]['event'].set()
                pinglunji[token]['event'].clear()
            elif message['type'] == 'websocket':
                for client in pinglunji[token]['client']:
                    await client.send_json(message['data'])
    except asyncio.CancelledError:
        timeLog(f'[Server] Disconnected from token: {token}, host: {ip}')
        for client in pinglunji[token]['client']:
            try:
                await client.close()
            except:
                pass
        del pinglunji[token]
        raise

def main():
    app.run(host='0.0.0.0', port=80)

if __name__ == '__main__':
    main()