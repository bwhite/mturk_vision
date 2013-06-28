import mturk_vision
import time
import json
from mturk_vision import quote


class AMTImageQAManager(mturk_vision.AMTManager):

    def __init__(self, *args, **kw):
        super(AMTImageQAManager, self).__init__(*args, **kw)
        self.required_columns = set(['question', 'responseType'])

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        row = self.get_row(user_id)
        if not row:
            return {'submitUrl': 'data:,Done%20annotating'}
        question = quote(self.read_row_column(row, 'question'))
        responseType = self.read_row_column(row, 'responseType')
        out = {"images": [],
               "dataId": self.urlsafe_uuid(),
               "question": quote(question)}
        data = {'image': row,
                'userId': user_id,
                'startTime': time.time(),
                'responseType': responseType,
                'question': question}
        try:
            latitude = quote(self.read_row_column(row, 'latitude'))
            longitude = quote(self.read_row_column(row, 'longitude'))
            out['latitude'] = data['latitude'] = latitude
            out['longitude'] = data['longitude'] = longitude
        except ValueError:
            pass
        self.response_db.hmset(self.prefix + out['dataId'], data)
        image = self.path_to_key_db.get(self.prefix + self.row_column_encode(row, 'image'))
        if image:
            out['image'] = image
        return out

    def result(self, user_id, data_id, data):
        assert self.response_db.hget(self.prefix + data_id, 'userId') == user_id
        # Don't double count old submissions
        if self.response_db.hget(self.prefix + data_id, 'userData') is None:
            self.response_db.hset(self.prefix + data_id, 'userData', json.dumps(data))
            super(AMTImageQAManager, self).result(user_id)
            self.response_db.hset(self.prefix + data_id, 'endTime', time.time())
        return self.make_data(user_id)
