import gevent.monkey
gevent.monkey.patch_all()
import gevent.pywsgi
import bottle
import mturk_vision
import os
from . import __path__
MANAGER = None
SERVER = None
ROOT = os.path.abspath(__path__[0])
print('ROOT[%s]' % ROOT)


@bottle.get('/')
def index():
    return MANAGER.index


@bottle.get('/static/:file_name')
def static(file_name):
    print('Static ROOT[%s]' % ROOT)
    return bottle.static_file(file_name, ROOT + '/static')


@bottle.get('/user.js')
def user():
    return MANAGER.user(bottle.request)


@bottle.get('/:user_id/data.js')
def data(user_id):
    return MANAGER.make_data(user_id)


@bottle.get('/config.js')
def config():
    return MANAGER.config


@bottle.get('/image/:image_key')
def image(image_key):
    try:
        data_key = image_key.rsplit('.', 1)[0]
        cur_data = MANAGER.read_data(data_key)
    except KeyError:
        bottle.abort(404)
    bottle.response.content_type = "image/jpeg"
    return cur_data


@bottle.get('/data/:data_key')
def metadata(data_key):
    try:
        cur_data = MANAGER.read_data(data_key)
    except KeyError:
        bottle.abort(404)
    return cur_data


@bottle.get('/admin/:secret/results.js')
def admin_results(secret):
    return MANAGER.admin_results(secret)


@bottle.get('/admin/:secret/users.js')
def admin_users(secret):
    return MANAGER.admin_users(secret)


@bottle.get('/admin/:secret/stop')
def admin_stop(secret):
    print('Quitting')
    SERVER.stop()


@bottle.post('/result')
def result():
    return MANAGER.result(**bottle.request.json)


# AMTManagerDB's
# 0: users
# 1: key_to_path
# 2: path_to_key
# AMTVideoClassificationManager
# 3: frame
# 6: response
# AMTVideoTextMatchManager / AMTVideoDescriptionManager (these inherit AMTVideoClassificationManager)
# 4: description


def server(**args):
    global MANAGER, SERVER
    MANAGER = mturk_vision.manager(**args)
    SERVER = gevent.pywsgi.WSGIServer(('0.0.0.0', int(args['port'])), bottle.app())
    SERVER.serve_forever()
