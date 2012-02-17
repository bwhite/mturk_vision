import base64
import uuid
import json
import time
from shove import Shove


class UserNotFinishedException(Exception):
    """Exception thrown when a user isn't finished"""


class AMTManager(object):
    
    def __init__(self, mode, num_tasks, index_path, config_path, user_db_uri,
                 key_to_path_db_uri, path_to_key_db_uri, **kw):
        self.mode = mode
        self.num_tasks = num_tasks
        self.users_db = Shove(user_db_uri)
        self.key_to_path_db = Shove(key_to_path_db_uri)
        self.path_to_key_db = Shove(path_to_key_db_uri)
        self.dbs = [self.key_to_path_db, self.path_to_key_db, self.users_db]
        self.index_path = index_path
        self.config_path = config_path
        self._make_secret()

    def sync(self):
        for db in self.dbs:
            db.sync()

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
        self.users_db[user_id] = out
        return {"user_id": user_id}

    def read_data(self, data_key):
        """Get data from disk corresponding to data_key

        Args:
            data_key: String data key

        Raises:
            KeyError: Data key not in DB
        """
        return open(self.key_to_path_db[data_key]).read()

    def admin_users(self, secret):
        """Return contents of users_db"""
        if secret == self.secret:
            return json.dumps(dict(self.users_db))

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
        cur_user = self.users_db[user_id]
        if (self.mode != 'standalone' and cur_user['tasks_finished'] >= self.num_tasks) or force:
            cur_user['end_time'] = time.time()
            self.users_db[user_id] = cur_user
            pct_correct = cur_user['tasks_correct'] / float(cur_user['tasks_finished'])
            pct_completed = cur_user['tasks_finished'] / float(cur_user['tasks_viewed'])
            query_string = '&'.join(['%s=%s' % x for x in [('assignmentId', cur_user.get('assignmentId', 'NoId')),
                                                           ('pct_correct', pct_correct),
                                                           ('pct_completed', pct_completed),
                                                           ('tasks_finished', cur_user['tasks_finished']),
                                                           ('tasks_viewed', cur_user['tasks_viewed']),
                                                           ('tasks_correct', cur_user['tasks_correct']),
                                                           ('time_taken', cur_user['end_time'] - cur_user['start_time'])]])
            return {'submit_url': '%s/mturk/externalSubmit?%s' % (cur_user.get('turkSubmitTo', 'http://www.mturk.com'), query_string)}
        self.users_db[user_id]['tasks_viewed'] = cur_user['tasks_viewed'] + 1
        raise UserNotFinishedException

    def result(self, user_id, correct):
        user = self.users_db[user_id]
        user['tasks_finished'] += 1
        if correct:
            user['tasks_correct'] += 1
        self.users_db[user_id] = user
