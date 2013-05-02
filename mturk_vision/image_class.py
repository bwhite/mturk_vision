import mturk_vision
import time
import json


class AMTImageClassManager(mturk_vision.AMTImageClassificationManager):

    def __init__(self, *args, **kw):
        super(AMTImageClassManager, self).__init__(*args, **kw)
        self.class_descriptions = json.loads(kw.get('class_descriptions', '{}'))
        self.class_thumbnails = json.loads(kw.get('class_thumbnails', '{}'))

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        images = self.random_images()
        if not images:
            return {'submit_url': 'data:,Done%20annotating'}
        image = images[0]
        class_name = self.read_row_column(image, 'entity')
        out = {"images": [],
               "data_id": self.urlsafe_uuid(),
               "entity_name": '<h2>Class: %s</h2>' % class_name}
        if class_name in self.class_descriptions:
            out['description'] = self.class_descriptions[class_name]
        if class_name in self.class_thumbnails:
            out['class_thumbnails'] = self.class_thumbnails[class_name]
        self.response_db.hmset(out['data_id'], {'image': image,
                                                'user_id': user_id, 'start_time': time.time(),
                                                'entity': class_name})
        out['images'].append({"src": 'image/%s' % self.path_to_key_db.get(self.row_column_encode(image, 'image')), "width": 250})
        return out
