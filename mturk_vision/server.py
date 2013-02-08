import gevent.monkey
gevent.monkey.patch_all()
import bottle
import base
import os
import mturk_vision
import redis
import gevent.pywsgi
from . import __path__
from data_sources import data_source_from_uri
ROOT = os.path.abspath(__path__[0])
MANAGER = None
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
    MANAGER.stop_server()


@bottle.put('/result/')
def result():
    return MANAGER.result(**bottle.request.json)


def make_data(user_id):
    return MANAGER.make_data(user_id)
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
    global MANAGER

    db_nums = list(enumerate(['users', 'key_to_path', 'path_to_key', 'frame', 'description', 'image', 'response']))
    print(db_nums)
    args.update(dict((y + '_db', redis.StrictRedis(host=args['redis_address'], port=args['redis_port'], db=x))
                     for x, y in db_nums))
    print(args)
    sp = lambda x: ROOT + '/static_private/' + x
    SERVER = gevent.pywsgi.WSGIServer(('0.0.0.0', int(args['port'])), bottle.app())
    args['server'] = SERVER
    args['data_source'] = data_source_from_uri(args['data'])
    if args['type'] == 'video_label':
        MANAGER = mturk_vision.AMTVideoClassificationManager(index_path=sp('video_label.html'),
                                                             config_path=sp('video_label_config.js'),
                                                             **args)
    elif args['type'] == 'video_match':
        MANAGER = mturk_vision.AMTVideoTextMatchManager(index_path=sp('video_match.html'),
                                                        config_path=sp('video_match_config.js'),
                                                        **args)
    elif args['type'] == 'video_description':
        MANAGER = mturk_vision.AMTVideoDescriptionManager(index_path=sp('video_description.html'),
                                                          config_path=sp('video_description_config.js'),
                                                          **args)
    elif args['type'] == 'image_label':
        MANAGER = mturk_vision.AMTImageClassificationManager(index_path=sp('video_label.html'),
                                                             config_path=sp('image_label_config.js'),
                                                             **args)
    elif args['type'] == 'image_entity':
        MANAGER = mturk_vision.AMTImageEntityManager(index_path=sp('video_label.html'),
                                                     config_path=sp('image_entity_config.js'),
                                                     **args)
    elif args['type'] == 'image_segments':
        MANAGER = mturk_vision.AMTImageSegmentsManager(index_path=sp('image_segments.html'),
                                                       config_path=sp('image_segments_config.js'),
                                                       **args)
    elif args['type'] == 'image_query':
        MANAGER = mturk_vision.AMTImageQueryManager(index_path=sp('video_label.html'),
                                                    config_path=sp('image_query_config.js'),
                                                    **args)
    else:
        raise ValueError('Unknown type[%s]' % args['type'])
    if args['setup']:
        if args['reset']:
            MANAGER.reset()
        MANAGER.initial_setup()
    print(bottle.app[0].routes)
    SERVER.serve_forever()
