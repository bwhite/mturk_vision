import mturk_vision


class AMTImageEntityManager(mturk_vision.AMTImageClassificationManager):

    def __init__(self, *args, **kw):
        super(AMTImageEntityManager, self).__init__(*args, **kw)

    def make_data(self, user_id):
        out = super(AMTImageEntityManager, self).make_data(user_id)
        if 'submit_url' in out:
            return out
        row, column = self.row_column_decode(self.key_to_path_db.get(out['images'][0]['src'].split('/', 1)[1]))
        out['entity_name'] = '<h2>Entity Name: %s</h2>' % self.read_row_column(row, 'entity')
        return out
