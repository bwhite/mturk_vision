import mturk_vision
import os
import glob
import random
import json
import time
from . import __path__


class AMTImageSegmentsManager(mturk_vision.AMTImageClassificationManager):

    def __init__(self, *args, **kw):
        super(AMTImageSegmentsManager, self).__init__(*args, **kw)
        self.image_segments_config = json.load(open(__path__[0] + '/static_private/image_segments_config.js'))
        self.classes = self.image_segments_config['classes']
        self.class_prob_cache = {}  # image path
        self.num_random = 100

    def _segments_fn(self, image_fn):
        return image_fn + '.js'

    def _input_data(self, data_root):
        for image_fn in glob.glob(data_root + '/*.jpg'):
            segments_fn = self._segments_fn(image_fn)
            if not os.path.exists(segments_fn):
                print('Skipping [%s], missing segments JSON!' % image_fn)
                continue
            yield image_fn, True
            yield segments_fn, False

    def _image_paths(self, image):
        return [image, self._segments_fn(image)]

    def random_image_sort_class(self, user_class):
        images = self.random_images(self.num_random)
        cached_images = set(self.cache).intersection(images)
        if not cached_images:  # If there are none cached, then just quit
            return images[0]
        image_segments = map(self._segments_fn, cached_images)
        # Update the class_prob_cache, this allows us to avoid parsing json constantly
        for cache_fn in set(image_segments) - set(self.class_prob_cache):
            self.class_prob_cache[cache_fn] = json.loads(self.cache[cache_fn])['class_prob']
        return max((self.class_prob_cache.get(self._segments_fn(cache_fn), {}).get(user_class, 0.), cache_fn)
                   for cache_fn in cached_images)[1]

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        # The class the user is responsible for is stored in the users_db
        user_class = self.users_db.hget(user_id, 'user_class')
        if user_class:
            user_class = json.loads(user_class)
        else:
            user_class = random.choice(self.classes)
            self.users_db.hset(user_id, 'user_class', json.dumps(user_class))
        image = self.random_image_sort_class(user_class['name'])
        image_out = 'image/%s' % self.path_to_key_db.get(image)
        segments_out = 'data/' + self.path_to_key_db.get(self._segments_fn(image))
        out = {"image": image_out,
               "segments": segments_out,
               "data_id": self.urlsafe_uuid(),
               "user_class": user_class}
        self.response_db.hmset(out['data_id'], {'image': image, 'segments': self._segments_fn(image),
                                                'user_id': user_id, 'start_time': time.time()})
        return out
