import base64
import uuid
import json
import time


class UserNotFinishedException(Exception):
    """Exception thrown when a user isn't finished"""


class AMTManager(object):
    
    def __init__(self, mode, num_tasks, index_path, config_path, users_db,
                 key_to_path_db, path_to_key_db, **kw):
        self.mode = mode
        self.num_tasks = num_tasks
        self.users_db = users_db
        self.key_to_path_db = key_to_path_db
        self.path_to_key_db = path_to_key_db
        self.dbs = [self.key_to_path_db, self.path_to_key_db, self.users_db]
        self.index_path = index_path
        self.config_path = config_path
        self._make_secret()

    @property
    def index(self):
        # Reload each time to simplify development
        return open(self.index_path).read()

    @property
    def config(self):
        # Reload each time to simplify development
        return open(self.config_path).read()

    def _make_secret(self):
        """Make secret used for admin functions"""
        self.secret = self.urlsafe_uuid()
        open('SECRET', 'w').write(self.secret)
        print('Results URL:  /%s/results.js' % self.secret)
        print('Users URL:  /%s/users.js' % self.secret)
        print('Quit URL:  /%s/quit' % self.secret)

    def make_data(self, user_id):
        pass

    def urlsafe_uuid(self):
        """Make a urlsafe uuid"""
        return base64.urlsafe_b64encode(uuid.uuid4().bytes)[:-2]

    def user(self, bottle_request):
        """Make a new user entry"""
        user_id = self.urlsafe_uuid()
        out = {'query_string': bottle_request.query_string,
               'remote_addr': bottle_request.remote_addr,
               'tasks_finished': 0,
               'tasks_correct': 0,
               'tasks_viewed': 0,
               'start_time': time.time()}
        out.update(dict(bottle_request.query))
        self.users_db.hmset(user_id, out)
        return {"user_id": user_id}

    def read_data(self, data_key):
        """Get data from disk corresponding to data_key

        Args:
            data_key: String data key

        Raises:
            KeyError: Data key not in DB
        """
        return open(self.key_to_path_db.get(data_key)).read()

    def admin_users(self, secret):
        """Return contents of users_db"""
        if secret == self.secret:
            keys = self.users_db.keys()
            return json.dumps(dict((k, self.users_db.hgetall(k)) for k in keys))

    def _user_finished(self, user_id, force=False):
        """Check if the user has finished their tasks, if so output the return dictionary.

        Updates tasks_viewed if we aren't finished.

        Args:
            user_id: User ID string

        Returns:
            A dictionary of the result.

        Raises:
            UserNotFinishedException: User hasn't finished their tasks
        """
        cur_user = self.users_db.hgetall(user_id)
        if (self.mode != 'standalone' and int(cur_user['tasks_finished']) >= self.num_tasks) or force:
            end_time = time.time()
            self.users_db.hset(user_id, 'end_time', end_time)
            pct_correct = int(cur_user['tasks_correct']) / float(cur_user['tasks_finished'])
            pct_completed = int(cur_user['tasks_finished']) / float(cur_user['tasks_viewed'])
            query_string = '&'.join(['%s=%s' % x for x in [('assignmentId', cur_user.get('assignmentId', 'NoId')),
                                                           ('pct_correct', pct_correct),
                                                           ('pct_completed', pct_completed),
                                                           ('tasks_finished', cur_user['tasks_finished']),
                                                           ('tasks_viewed', cur_user['tasks_viewed']),
                                                           ('tasks_correct', cur_user['tasks_correct']),
                                                           ('time_taken', end_time - float(cur_user['start_time']))]])
            return {'submit_url': '%s/mturk/externalSubmit?%s' % (cur_user.get('turkSubmitTo', 'http://www.mturk.com'), query_string)}
        self.users_db.hincrby(user_id, 'tasks_viewed')
        raise UserNotFinishedException

    def result(self, user_id, correct=False):
        self.users_db.hincrby(user_id, 'tasks_finished')
        if correct:
            self.users_db.hincrby(user_id, 'tasks_correct')
