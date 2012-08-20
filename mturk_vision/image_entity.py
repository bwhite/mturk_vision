import mturk_vision
import glob
import os


class AMTImageEntityManager(mturk_vision.AMTImageClassificationManager):

    def __init__(self, *args, **kw):
        super(AMTImageEntityManager, self).__init__(*args, **kw)

    def initial_setup(self, data_root):
        path_to_key_db = self.path_to_key_db.pipeline()
        key_to_path_db = self.key_to_path_db.pipeline()
        image_db = self.image_db.pipeline()
        for d in glob.glob(data_root + '/*'):
            for fn in glob.glob(d + '/*'):
                key = self.urlsafe_uuid()
                path_to_key_db.set(fn, key)
                key_to_path_db.set(key, fn)
                image_db.set(fn, '')
        path_to_key_db.execute()
        key_to_path_db.execute()
        image_db.execute()

    def make_data(self, user_id):
        out = super(AMTImageEntityManager, self).make_data(user_id)
        path = self.key_to_path_db.get(out['images'][0]['src'].split('/', 1)[1])
        print(path)
        entity_name = os.path.basename(os.path.dirname(path))
        out['name'] = entity_name
        return out
