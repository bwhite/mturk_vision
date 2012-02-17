import gevent.monkey
gevent.monkey.patch_all()
import bottle
import base
import os
import mturk_vision
from . import __path__
ROOT = os.path.abspath(__path__[0])
MANAGER = None


@bottle.get('/')
def index():
    return MANAGER.index


@bottle.get('/static/<file_name:re:[a-zA-z_\-\.0-9]+\.(js|png|jpeg|jpg|html|css)>')
def static(file_name):
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


@bottle.get('/frames/:frame_key')
def frames(frame_key):
    try:
        data_key = frame_key.rsplit('.', 1)[0]
        cur_data = MANAGER.read_data(data_key)
    except KeyError:
        bottle.abort(404)
    bottle.response.content_type = "image/jpeg"
    return cur_data


@bottle.get('/:secret/results.js')
def admin_results(secret):
    return MANAGER.admin_results(secret)


@bottle.get('/:secret/users.js')
def admin_users(secret):
    return MANAGER.admin_users(secret)


@bottle.get('/:secret/quit')
def admin_quit(secret):
    print('Quitting')
    MANAGER.sync()
    quit()


@bottle.put('/result/')
def result():
    return MANAGER.result(**bottle.request.json)


def make_data(user_id):
    return MANAGER.make_data(user_id)


def sync_dbs():
    while 1:
        MANAGER.sync()
        gevent.sleep(5)


def server(**args):
    global MANAGER
    path_root = os.path.expanduser(args['db'])
    try:
        os.makedirs(path_root)
        existing = False
    except OSError:
        existing = True
    uri_root = 'leveldb://' + path_root
    args.update(dict((x + '_db_uri', uri_root + x + '.db')
                     for x in ['user', 'key_to_path', 'path_to_key', 'frame', 'description']))
    sp = lambda x: ROOT + '/static_private/' + x
    if args['type'] == 'label':
        args['response_db_uri'] = uri_root + 'label_response.db'
        MANAGER = mturk_vision.AMTVideoClassificationManager(index_path=sp('video_label.html'),
                                                             config_path=sp('video_label_config.js'),
                                                             **args)
    elif args['type'] == 'match':
        args['response_db_uri'] = uri_root + 'match_response.db'
        MANAGER = mturk_vision.AMTVideoTextMatchManager(index_path=sp('video_match.html'),
                                                        config_path=sp('video_match_config.js'),
                                                        **args)
    elif args['type'] == 'description':
        args['response_db_uri'] = uri_root + 'description_response.db'
        MANAGER = mturk_vision.AMTVideoDescriptionManager(index_path=sp('video_description.html'),
                                                          config_path=sp('video_description_config.js'),
                                                          **args)
    else:
        raise ValueError('Unknown type[%s]' % args['type'])
    if not existing:
        MANAGER.initial_setup(os.path.expanduser(args['data']))
    gevent.spawn(sync_dbs)
    bottle.run(host='0.0.0.0', port=args['port'], server='gevent')
