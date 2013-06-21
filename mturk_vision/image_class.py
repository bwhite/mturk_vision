import mturk_vision
import time
import json
from mturk_vision import quote


class AMTImageClassManager(mturk_vision.AMTManager):

    def __init__(self, *args, **kw):
        super(AMTImageClassManager, self).__init__(*args, **kw)
        self.class_descriptions = json.loads(kw.get('class_descriptions', '{}'))
        self.class_descriptions = {x: quote(y) for x, y in self.class_descriptions.items()}
        self.class_thumbnails = json.loads(kw.get('class_thumbnails', '{}'))
        self.class_thumbnails = {x: map(quote, y) for x, y in self.class_thumbnails.items()}
        self.required_columns = set(['image', 'class'])

    def make_data(self, user_id):
        print('In image_class.make_data')
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        row = self.get_row(user_id)
        if not row:
            return {'submitUrl': 'data:,Done%20annotating'}
        class_name = quote(self.read_row_column(row, 'class'))
        out = {"images": [],
               "dataId": self.urlsafe_uuid(),
               "className": '<h3>Class: %s</h3>' % class_name}
        h = ''
        if class_name in self.class_descriptions:
            h = '<pre>Description: '+ self.class_descriptions[class_name] + '</pre>'
        if class_name in self.class_thumbnails:
            h += '<h3>Class Examples</h3>'
            for x in self.class_thumbnails[class_name]:
                h += '<img src="%s" height="75px" width="75px">' % x
        if h:
            out['help'] = h
        self.response_db.hmset(self.prefix + out['dataId'], {'image': row,
                                                             'userId': user_id, 'startTime': time.time(),
                                                             'class': class_name})
        print('row[%r]' % row)
        out['images'].append({"src": 'image/%s' % self.path_to_key_db.get(self.prefix + self.row_column_encode(row, 'image')), "width": 250})
        print(out)
        return out

    def result(self, user_id, data_id, data):
        assert self.response_db.hget(self.prefix + data_id, 'userId') == user_id
        # Don't double count old submissions
        if self.response_db.hget(self.prefix + data_id, 'userData') is None:
            self.response_db.hset(self.prefix + data_id, 'userData', json.dumps(data))
            super(AMTImageClassManager, self).result(user_id)
            self.response_db.hset(self.prefix + data_id, 'endTime', time.time())
        return self.make_data(user_id)
