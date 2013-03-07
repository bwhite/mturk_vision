import os
import mturk_vision
import redis
from . import __path__
from data_sources import data_source_from_uri
ROOT = os.path.abspath(__path__[0])


def manager(**args):
    db_nums = list(enumerate(['users', 'key_to_path', 'path_to_key', 'frame', 'description', 'image', 'response']))
    print(db_nums)
    args.update(dict((y + '_db', redis.StrictRedis(host=args['redis_address'], port=args['redis_port'], db=x))
                     for x, y in db_nums))
    print(args)
    sp = lambda x: ROOT + '/static_private/' + x
    args['data_source'] = data_source_from_uri(args['data'])
    if args['type'] == 'video_label':
        m = mturk_vision.AMTVideoClassificationManager(index_path=sp('video_label.html'),
                                                       config_path=sp('video_label_config.js'),
                                                       **args)
    elif args['type'] == 'video_match':
        m = mturk_vision.AMTVideoTextMatchManager(index_path=sp('video_match.html'),
                                                  config_path=sp('video_match_config.js'),
                                                  **args)
    elif args['type'] == 'video_description':
        m = mturk_vision.AMTVideoDescriptionManager(index_path=sp('video_description.html'),
                                                    config_path=sp('video_description_config.js'),
                                                    **args)
    elif args['type'] == 'image_label':
        m = mturk_vision.AMTImageClassificationManager(index_path=sp('video_label.html'),
                                                       config_path=sp('image_label_config.js'),
                                                       **args)
    elif args['type'] == 'image_entity':
        m = mturk_vision.AMTImageEntityManager(index_path=sp('video_label.html'),
                                               config_path=sp('image_entity_config.js'),
                                               **args)
    elif args['type'] == 'image_segments':
        m = mturk_vision.AMTImageSegmentsManager(index_path=sp('image_segments.html'),
                                                 config_path=sp('image_segments_config.js'),
                                                 **args)
    elif args['type'] == 'image_query':
        m = mturk_vision.AMTImageQueryManager(index_path=sp('video_label.html'),
                                              config_path=sp('image_query_config.js'),
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
