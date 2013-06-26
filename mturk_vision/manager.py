import os
import mturk_vision
import redis
import logging
from . import __path__
from data_sources import data_source_from_uri
ROOT = os.path.abspath(__path__[0])


def manager(**args):
    db_nums = list(enumerate(['users', 'response', 'state', 'key_to_path', 'path_to_key', 'tasks']))
    logging.debug(db_nums)
    args.update(dict((y + '_db', redis.StrictRedis(host=args['redis_address'], port=args['redis_port'], db=x))
                     for x, y in db_nums))
    logging.debug(args)
    sp = lambda x: ROOT + '/static_private/' + x
    args['data_source'] = data_source_from_uri(args['data'])
    if args['type'] == 'image_class':
        m = mturk_vision.AMTImageClassManager(index_path=sp('image_label.html'),
                                              config_path=sp('image_class_config.js'),
                                              **args)
    elif args['type'] == 'image_qa':
        m = mturk_vision.AMTImageQAManager(index_path=sp('image_qa.html'),
                                           config_path=sp('image_qa_config.js'),
                                           **args)
    else:
        raise ValueError('Unknown type[%s]' % args['type'])
    if args['sync']:
        m.sync()
    return m
