import mturk_vision
import time
import json
from mturk_vision import quote


class AMTImageQAManager(mturk_vision.AMTManager):

    def __init__(self, *args, **kw):
        super(AMTImageQAManager, self).__init__(*args, **kw)
        self.required_columns = set(['image', 'question'])

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        row = self.get_row(user_id)
        if not row:
            return {'submitUrl': 'data:,Done%20annotating'}
        question = quote(self.read_row_column(row, 'question'))
        out = {"images": [],
               "dataId": self.urlsafe_uuid(),
               "question": '<h3>%s</h3>' % question}
        self.response_db.hmset(self.prefix + out['dataId'], {'image': row,
                                                             'userId': user_id,
                                                             'startTime': time.time(),
                                                             'question': question})
        out['images'].append({"src": 'image/%s' % self.path_to_key_db.get(self.prefix + self.row_column_encode(row, 'image')), "width": 250})
        return out

    def result(self, user_id, data_id, data):
        assert self.response_db.hget(self.prefix + data_id, 'userId') == user_id
        # Don't double count old submissions
        if self.response_db.hget(self.prefix + data_id, 'userData') is None:
            self.response_db.hset(self.prefix + data_id, 'userData', json.dumps(data))
            super(AMTImageQAManager, self).result(user_id)
            self.response_db.hset(self.prefix + data_id, 'endTime', time.time())
        return self.make_data(user_id)
