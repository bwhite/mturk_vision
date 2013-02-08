import base64
import uuid
import json
import time
import gevent
import random


class UserNotFinishedException(Exception):
    """Exception thrown when a user isn't finished"""


class AMTManager(object):

    def __init__(self, mode, num_tasks, index_path, config_path, users_db,
                 key_to_path_db, path_to_key_db, data_source, server, secret=None, **kw):
        self.mode = mode
        self.num_tasks = num_tasks
        self.users_db = users_db
        self.key_to_path_db = key_to_path_db
        self.path_to_key_db = path_to_key_db
        self.dbs = [self.key_to_path_db, self.path_to_key_db, self.users_db]
        self.index_path = index_path
        self.config_path = config_path
        self.server = server
        self.cache = {}
        self.data_source = data_source
        self._make_secret(secret)
        self.data_source_lock = gevent.coros.RLock()

    @property
    def index(self):
        # Reload each time to simplify development
        return open(self.index_path).read()

    @property
    def config(self):
        # Reload each time to simplify development
        return open(self.config_path).read()

    def reset(self):
        for db in self.dbs:
            db.flushdb()

    def _make_secret(self, secret=None):
        """Make secret used for admin functions"""
        if secret is None:
            self.secret = self.urlsafe_uuid()
        else:
            self.secret = secret
        print('Results URL:  /admin/%s/results.js' % self.secret)
        print('Users URL:  /admin/%s/users.js' % self.secret)
        print('Quit URL:  /admin/%s/stop' % self.secret)

    def stop_server(self):
        self.server.stop()

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

    def row_column_encode(self, row, column):
        return base64.b64encode(row) + ' ' + base64.b64encode(column)

    def row_column_decode(self, row_column_code):
        return map(base64.b64decode, row_column_code.split(' ', 1))

    def read_data(self, data_key):
        """Get data from disk corresponding to data_key

        Args:
            data_key: String data key

        Raises:
            KeyError: Data key not in DB
        """
        path = self.key_to_path_db.get(data_key)
        if path is None:
            raise KeyError
        row, column = self.row_column_decode(path)
        return self.read_row_column(row, column)

    def read_row_column(self, row, column):
        try:
            return self.cache[row][column]
        except KeyError:
            try:
                self.data_source_lock.acquire()
                return self.data_source.value(row, column)
            finally:
                self.data_source_lock.release()

    def _cache_row(self, row):
        st = time.time()
        try:
            self.data_source_lock.acquire()
            self.cache[row] = dict(self.data_source.column_values())
        finally:
            self.data_source_lock.release()
        print('Loaded[%s][%f]' % (row, time.time() - st))

    def cache_row(self, row, delay=.25):
        gevent.spawn_later(delay, self._cache_row, row)

    def admin_users(self, secret):
        """Return contents of users_db"""
        if secret == self.secret:
            return json.dumps({k: self.users_db.hgetall(k) for k in self.users_db.keys('*')})

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
        if (self.mode == 'amt' and int(cur_user['tasks_finished']) >= self.num_tasks) or force:
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
