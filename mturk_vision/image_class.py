import mturk_vision
import time
import json
from mturk_vision import quote


class AMTImageClassManager(mturk_vision.AMTImageClassificationManager):

    def __init__(self, *args, **kw):
        super(AMTImageClassManager, self).__init__(*args, **kw)
        self.class_descriptions = json.loads(kw.get('class_descriptions', '{}'))
        self.class_descriptions = {x: quote(y) for x, y in self.class_descriptions.items()}
        self.class_thumbnails = json.loads(kw.get('class_thumbnails', '{}'))
        self.class_thumbnails = {x: map(quote, y) for x, y in self.class_thumbnails.items()}

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        images = self.random_images()
        if not images:
            return {'submit_url': 'data:,Done%20annotating'}
        image = images[0]
        class_name = quote(self.read_row_column(image, 'entity'))
        out = {"images": [],
               "data_id": self.urlsafe_uuid(),
               "entity_name": '<h3>Class: %s</h3>' % class_name}
        h = ''
        if class_name in self.class_descriptions:
            h = '<pre>Description: '+ self.class_descriptions[class_name] + '</pre>'
        if class_name in self.class_thumbnails:
            h += '<h3>Class Examples</h3>'
            for x in self.class_thumbnails[class_name]:
                h += '<img src="%s" height="75px" width="75px">' % x
        if h:
            out['help'] = h
        self.response_db.hmset(out['data_id'], {'image': image,
                                                'user_id': user_id, 'start_time': time.time(),
                                                'entity': class_name})
        out['images'].append({"src": 'image/%s' % self.path_to_key_db.get(self.row_column_encode(image, 'image')), "width": 250})
        return out
