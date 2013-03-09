import mturk_vision
import json
import time
import base64


class AMTImageQueryBatchManager(mturk_vision.AMTImageClassificationManager):

    def __init__(self, query, *args, **kw):
        super(AMTImageQueryBatchManager, self).__init__(*args, **kw)
        self.images_per_batch = 64
        self.query = '<h2>%s</h2>' % query

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        images = self.random_images(num_images=self.images_per_batch)
        if not images:
            return {'submit_url': 'data:,Done%20annotating'}
        out = {"images": [],
               "data_id": self.urlsafe_uuid(),
               "query": self.query}
        self.response_db.hmset(out['data_id'], {'images': json.dumps(map(base64.urlsafe_b64encode, images)),
                                                'user_id': user_id, 'start_time': time.time()})
        for image in images:
            out['images'].append({"src": 'image/%s' % self.path_to_key_db.get(self.row_column_encode(image, 'image')), "width": 150})
        return out

    def result(self, user_id, data_id, data):
        assert self.response_db.hget(data_id, 'user_id') == user_id
        # Don't double count old submissions
        if self.response_db.hget(data_id, 'user_data') is None:
            self.response_db.hset(data_id, 'user_data', json.dumps(data))
            images = [base64.urlsafe_b64decode(str(x)) for x in json.loads(self.response_db.hget(data_id, 'images'))]
            for image in images:
                # Remove image to answer, and evict from cache
                try:
                    self.state_db.srem('images_to_answer', image)
                except KeyError:
                    pass
                try:
                    del self.cache[image]
                except KeyError:
                    pass
            super(mturk_vision.AMTImageClassificationManager, self).result(user_id)
            self.response_db.hset(data_id, 'end_time', time.time())
        return self.make_data(user_id)
