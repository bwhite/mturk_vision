import os
import mturk_vision
import redis
import logging
from . import __path__
from data_sources import data_source_from_uri
ROOT = os.path.abspath(__path__[0])


def manager(**args):
    db_nums = list(enumerate(['users', 'response', 'data', 'state', 'key_to_path', 'path_to_key']))
    logging.debug(db_nums)
    args.update(dict((y + '_db', redis.StrictRedis(host=args['redis_address'], port=args['redis_port'], db=x))
                     for x, y in db_nums))
    logging.debug(args)
    sp = lambda x: ROOT + '/static_private/' + x
    args['data_source'] = data_source_from_uri(args['data'])
    if args['type'] == 'image_class':
        m = mturk_vision.AMTImageClassManager(index_path=sp('video_label.html'),
                                              config_path=sp('image_class_config.js'),
                                              **args)
    elif args['type'] == 'image_query_batch':
        m = mturk_vision.AMTImageQueryBatchManager(index_path=sp('image_query_batch.html'),
                                                   config_path=sp('image_query_batch_config.js'),
                                                   **args)
    else:
        raise ValueError('Unknown type[%s]' % args['type'])
    if args['setup']:
        if args['reset']:
            m.reset()
        m.initial_setup()
    return m
