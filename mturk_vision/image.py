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
        self.dbs += [self.image_db, self.response_db]

    def _parse_fns(self, fn_path):
        return [fn.rstrip() for fn in open(fn_path)]

    def initial_setup(self, data_root):
        path_to_key_db = self.path_to_key_db.pipeline()
        key_to_path_db = self.key_to_path_db.pipeline()
        image_db = self.image_db.pipeline()
        for fn in glob.glob(data_root + '/*.jpg'):
            key = self.urlsafe_uuid()
            path_to_key_db.set(fn, key)
            key_to_path_db.set(key, fn)
            image_db.set(fn, '')
        path_to_key_db.execute()
        key_to_path_db.execute()
        image_db.execute()

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        try:
            image = random.choice(list(self.images_to_answer))
        except IndexError:
            self.images_to_answer = set(self.image_db.keys('*'))
            image = random.choice(list(self.images_to_answer))
        out = {"images": [],
               "data_id": self.urlsafe_uuid()}
        self.response_db.hmset(out['data_id'], {'image': image,
                                                'user_id': user_id, 'start_time': time.time()})
        out['images'].append({"src": 'image/%s.jpg' % self.path_to_key_db.get(image), "width": 250})
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
            try:
                self.images_to_answer.remove(self.response_db.hget(data_id, 'image'))
            except KeyError:
                pass
            super(AMTImageClassificationManager, self).result(user_id)
            self.response_db.hset(data_id, 'end_time', time.time())
        return self.make_data(user_id)
