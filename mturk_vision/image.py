import mturk_vision
import random
import json
import time


class AMTImageClassificationManager(mturk_vision.AMTManager):

    def __init__(self, image_db, response_db, *args, **kw):
        super(AMTImageClassificationManager, self).__init__(*args, **kw)
        self.image_db = image_db  # [image_path] = ''
        self.response_db = response_db
        self.images_to_answer = set()  # Represents which images need to been answered, once there are none left we reset
        self.num_cached = 1000
        self.dbs += [self.image_db, self.response_db]
        self.initialize_images_to_answer()

    def _parse_fns(self, fn_path):
        return [fn.rstrip() for fn in open(fn_path)]

    def initial_setup(self):
        self.images_to_answer = set()
        self.path_to_key_db.flushdb()
        self.key_to_path_db.flushdb()
        self.image_db.flushdb()
        path_to_key_db = self.path_to_key_db.pipeline()
        key_to_path_db = self.key_to_path_db.pipeline()
        image_db = self.image_db.pipeline()
        for row, columns in self.data_source.row_columns():
            image_db.set(row, '')
            for column in columns:
                row_column_code = self.row_column_encode(row, column)
                key = self.urlsafe_uuid()
                path_to_key_db.set(row_column_code, key)
                key_to_path_db.set(key, row_column_code)
        path_to_key_db.execute()
        key_to_path_db.execute()
        image_db.execute()
        self.cache = {}
        self.initialize_images_to_answer()

    def initialize_images_to_answer(self):
        self.images_to_answer = set(self.image_db.keys('*'))

    def random_images(self, num_images=1):
        if not self.images_to_answer:
            # Single mode only lets each image get annotated once
            if self.mode == 'single':
                return []
            self.initialize_images_to_answer()
        available_images = list(self.images_to_answer)
        return random.sample(available_images, min(len(available_images), num_images))

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        images = self.random_images()
        if not images:
            return {'submit_url': 'data:,Done%20annotating'}
        image = images[0]
        out = {"images": [],
               "data_id": self.urlsafe_uuid()}
        self.response_db.hmset(out['data_id'], {'image': image,
                                                'user_id': user_id, 'start_time': time.time()})
        out['images'].append({"src": 'image/%s' % self.path_to_key_db.get(self.row_column_encode(image, 'image')), "width": 250})
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
                del self.cache[image]
            except KeyError:
                pass
            super(AMTImageClassificationManager, self).result(user_id)
            self.response_db.hset(data_id, 'end_time', time.time())
        return self.make_data(user_id)
