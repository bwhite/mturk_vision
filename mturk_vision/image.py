import mturk_vision
import os
import glob
import random
import json
import time


class AMTImageClassificationManager(mturk_vision.AMTManager):

    def __init__(self, image_db, response_db, *args, **kw):
        super(AMTImageClassificationManager, self).__init__(*args, **kw)
        self.image_db = image_db  # [image_path] = ''
        self.response_db = response_db
        self.images_to_answer = set()  # Represents which images need to been answered, once there are none left we reset
        self.images_cached = set()
        self.num_cached = 1000
        self.dbs += [self.image_db, self.response_db]
        self.random_images()  # Warm cache

    def _parse_fns(self, fn_path):
        return [fn.rstrip() for fn in open(fn_path)]

    def _input_data(self, data_root):
        return ((x, True) for x in glob.glob(data_root + '/*.jpg'))

    def initial_setup(self, data_root):
        self.images_to_answer = set()
        self.images_cached = set()
        self.cache = {}
        self.path_to_key_db.flushdb()
        self.key_to_path_db.flushdb()
        self.image_db.flushdb()
        path_to_key_db = self.path_to_key_db.pipeline()
        key_to_path_db = self.key_to_path_db.pipeline()
        image_db = self.image_db.pipeline()
        for fn, is_image in self._input_data(data_root):
            key = self.urlsafe_uuid()
            path_to_key_db.set(fn, key)
            key_to_path_db.set(key, fn)
            if is_image:
                image_db.set(fn, '')
        path_to_key_db.execute()
        key_to_path_db.execute()
        image_db.execute()
        self.cache = {}
        self.images_cached = set()
        self.random_images()  # Warm cache

    def _image_paths(self, image):
        return [image]

    def random_images(self, num_images=1):
        # Build up a random sample of images to cache
        if not self.images_to_answer:
            self.images_to_answer = set(self.image_db.keys('*'))
        uncached = list(self.images_to_answer - self.images_cached)
        needed_images = max(self.num_cached - len(self.cache), 0)
        images = random.sample(uncached,
                               min(len(uncached), needed_images))
        needed_images -= len(images)
        if needed_images:
            self.images_to_answer = set(self.image_db.keys('*'))
        for image in images:
            self.images_cached.add(image)
            for path in self._image_paths(image):
                self.cache_path(path)
        print('num_images:%d images_to_answer:%d' % (num_images, len(self.images_to_answer)))
        try:
            available_images = list(self.images_cached.intersection(self.cache))
            return random.sample(available_images, num_images)
        except ValueError:  # Fall back to picking any item
            print('Cache miss!')
            available_images = list(self.images_to_answer)
            return random.sample(available_images, min(len(available_images), num_images))

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        image = self.random_images()[0]
        out = {"images": [],
               "data_id": self.urlsafe_uuid()}
        self.response_db.hmset(out['data_id'], {'image': image,
                                                'user_id': user_id, 'start_time': time.time()})
        out['images'].append({"src": 'image/%s' % self.path_to_key_db.get(image), "width": 250})
        return out

    def admin_results(self, secret):
        """Return contents of response_db"""
        if secret == self.secret:
            keys = self.response_db.keys('*')
            return json.dumps(dict(zip(keys, self.response_db.mget(keys))))

    def result(self, user_id, data_id, data):
        assert self.response_db.hget(data_id, 'user_id') == user_id
        # Don't double count old submissions
        if self.response_db.hget(data_id, 'user_data') is None:
            self.response_db.hset(data_id, 'user_data', data)
            image = self.response_db.hget(data_id, 'image')
            # Remove image to answer, and evict from cache
            try:
                self.images_to_answer.remove(image)
            except KeyError:
                pass
            try:
                self.images_cached.remove(image)
            except KeyError:
                pass
            for path in self._image_paths(image):
                try:
                    del self.cache[path]
                    print('Cache evicted[%s]' % path)
                except KeyError:
                    pass
            super(AMTImageClassificationManager, self).result(user_id)
            self.response_db.hset(data_id, 'end_time', time.time())
        return self.make_data(user_id)
