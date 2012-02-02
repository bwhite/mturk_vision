import gevent.monkey
gevent.monkey.patch_all()
import bottle
import argparse
import base
import os
import signal


MANAGER = None


@bottle.get('/')
def index():
    return MANAGER.index


@bottle.get('/style.css')
def styles():
    return bottle.static_file('style.css', './')


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


@bottle.put('/result/')
def result():
    return MANAGER.result(**bottle.request.json)


def make_data(user_id):
    return MANAGER.make_data(user_id)


def sync_dbs(signum, frame):
    print('Syncing DB')
    MANAGER.sync()
    if signum == signal.SIGINT:
        quit()


def main():
    global MANAGER
    # Parse command line
    parser = argparse.ArgumentParser(description="Serve ")
    parser.add_argument('--port', help='Run on this port',
                        default='8080')
    parser.add_argument('--num_tasks', help='Number of tasks per worker (unused in standalone mode)',
                        default=100, type=int)
    parser.add_argument('--mode', help='Number of tasks per worker',
                        default='standalone', choices=['amt', 'standalone'])
    parser.add_argument('--type', help='Which AMT job type to run',
                        default='label', choices=['label', 'match', 'description'])
    args = vars(parser.parse_args())
    path_root = os.path.expanduser('~/amt_video/')
    try:
        os.makedirs(path_root)
        existing = False
    except OSError:
        existing = True
    uri_root = 'sqlite:///' + path_root
    args.update(dict((x + '_db_uri', uri_root + x + '.db')
                     for x in ['user', 'key_to_path', 'path_to_key', 'frame', 'description']))
    if args['type'] == 'label':
        args['response_db_uri'] = uri_root + 'label_response.db'
        MANAGER = base.AMTVideoClassificationManager(index_path='video_label.html',
                                                     config_path='video_label_config.js',
                                                     **args)
    elif args['type'] == 'match':
        args['response_db_uri'] = uri_root + 'match_response.db'
        MANAGER = base.AMTVideoTextMatchManager(index_path='video_match.html',
                                                     config_path='video_match_config.js',
                                                     **args)
    elif args['type'] == 'description':
        args['response_db_uri'] = uri_root + 'description_response.db'
        MANAGER = base.AMTVideoDescriptionManager(index_path='video_description.html',
                                                  config_path='video_description_config.js',
                                                  **args)
    else:
        raise ValueError('Unknown type[%s]' % args['type'])
    if not existing:
        MANAGER.initial_setup()
    signal.signal(signal.SIGINT, sync_dbs)
    signal.alarm(60)
    bottle.run(host='0.0.0.0', port=args['port'], server='gevent')

if __name__ == "__main__":
    main()
