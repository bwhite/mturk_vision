import mturk_vision
import time


class AMTImageEntityManager(mturk_vision.AMTImageClassificationManager):

    def __init__(self, *args, **kw):
        super(AMTImageEntityManager, self).__init__(*args, **kw)

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        images = self.random_images()
        if not images:
            return {'submit_url': 'data:,Done%20annotating'}
        image = images[0]
        entity = self.read_row_column(image, 'entity')
        out = {"images": [],
               "data_id": self.urlsafe_uuid(),
               "entity_name": '<h2>Entity Name: %s</h2>' % entity}
        self.response_db.hmset(out['data_id'], {'image': image,
                                                'user_id': user_id, 'start_time': time.time(),
                                                'entity': entity})
        out['images'].append({"src": 'image/%s' % self.path_to_key_db.get(self.row_column_encode(image, 'image')), "width": 250})
        return out
