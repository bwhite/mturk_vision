import mturk_vision


class AMTImageQueryManager(mturk_vision.AMTImageClassificationManager):

    def __init__(self, query, *args, **kw):
        super(AMTImageQueryManager, self).__init__(*args, **kw)
        self.query = '<h2>%s</h2>' % query

    def make_data(self, user_id):
        out = super(AMTImageQueryManager, self).make_data(user_id)
        if 'submit_url' in out:
            return out
        out['query'] = self.query
        return out
