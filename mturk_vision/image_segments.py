import mturk_vision
import random
import json
import time
from . import __path__


class AMTImageSegmentsManager(mturk_vision.AMTImageClassificationManager):

    def __init__(self, *args, **kw):
        super(AMTImageSegmentsManager, self).__init__(required_columns=['image', 'segments'], *args, **kw)
        self.image_segments_config = json.load(open(__path__[0] + '/static_private/image_segments_config.js'))
        self.classes = self.image_segments_config['classes']
        self.num_random_ilp = 100
        self.ilps = self.collect_ilps()  # [row] = ilp

    def collect_ilps(self):
        ilps = {}
        try:
            for row, columns in self.data_source.row_column_values(columns=['ilp']):
                print('Getting ILP[%s]' % row)
                columns = dict(columns)
                ilps[row] = json.loads(columns['ilp'])
                print(ilps[row])
        except KeyError:
            pass
        return ilps

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
        # Half of the time do a true random sample
        if random.random() < .5 or not self.ilps:
            image = self.random_images()[0]
        else:
            images = self.random_images(self.num_random_ilp)
            image_ilps = [(self.ilps[x][user_class['num']], x) for x in images if x in self.ilps]
            print(image_ilps)
            image = max(image_ilps,
                        key=lambda x: x[0])[1]
        image_out = 'image/' + self.path_to_key_db.get(self.row_column_encode(image, 'image'))
        segments_out = 'data/' + self.path_to_key_db.get(self.row_column_encode(image, 'segments'))
        out = {"image": image_out,
               "segments": segments_out,
               "data_id": self.urlsafe_uuid(),
               "user_class": user_class}
        self.response_db.hmset(out['data_id'], {'image': image, 'user_id': user_id, 'start_time': time.time()})
        return out
