import gevent.monkey
gevent.monkey.patch_all()
import bottle
import base
import os
import mturk_vision
import redis
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


@bottle.get('/image/:image_key')
def image(image_key):
    try:
        data_key = image_key.rsplit('.', 1)[0]
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
    quit()


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
    else:
        raise ValueError('Unknown type[%s]' % args['type'])
    if args['setup']:
        if args['data'] is not None:
            args['data'] = os.path.expanduser(args['data'])
        MANAGER.initial_setup(args['data'])
    bottle.run(host='0.0.0.0', port=args['port'], server='gevent')
