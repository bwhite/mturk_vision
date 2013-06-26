import base64
import uuid
import json
import time
import hashlib
import gevent
import gevent.coros
from mturk_vision import quote


class UserNotFinishedException(Exception):
    """Exception thrown when a user isn't finished"""


class AMTManager(object):

    def __init__(self, mode, num_tasks, index_path, config_path, task_key,
                 users_db, response_db, state_db, key_to_path_db, path_to_key_db,
                 data_source, secret=None, **kw):
        self.prefix = task_key + ':'
        self.mode = mode
        self.num_tasks = num_tasks
        self.users_db = users_db
        self.response_db = response_db
        self.state_db = state_db
        self.key_to_path_db = key_to_path_db
        self.path_to_key_db = path_to_key_db
        self.dbs = [self.users_db, self.response_db, self.state_db,
                    self.key_to_path_db, self.path_to_key_db]
        self.index_path = index_path
        self.config_path = config_path
        self.data_source = data_source
        self._make_secret(secret)
        self.data_source_lock = gevent.coros.RLock()  # Used to protect the data_source from simultaneous access
        self.lock_expire = 60
        self.random_prefix = 4
        if 'instructions' in kw:
            self.instructions = '<pre>%s</pre>' % quote(kw['instructions'])

    @property
    def index(self):
        # Reload each time to simplify development
        return open(self.index_path).read()

    @property
    def config(self):
        # Reload each time to simplify development
        config = open(self.config_path).read()
        if hasattr(self, 'instructions'):
            config_js = json.loads(config)
            config_js['instructions'] = self.instructions
            config = json.dumps(config_js)
        return config

    def _flush_db(self, db, keep_rows=None):
        keys = db.keys(self.prefix + '*')
        if keep_rows:
            keep_rows = set(self.prefix + x for x in keep_rows)
            keys = [x for x in keys if x not in keep_rows]
        print('Deleting [%d] keys' % len(keys))
        if keys:
            db.delete(*keys)

    def row_increment_priority(self, row, priority):
        # TODO: Minor race here, redo in Lua
        if self.state_db.zscore(self.prefix + 'rows', self._row(row)) is None:
            return
        self.state_db.zincrby(self.prefix + 'rows', priority, self._row(row))

    def row_delete(self, row, state_db=None):
        if state_db is None:
            state_db = self.state_db
        # NOTE: We just leave the column forward/backward mappings for simplicity
        state_db.zrem(self.prefix + 'rows', self._row(row))

    def _add_row(self, row, columns, state_db, key_to_path_db, path_to_key_db, priority=0):
        state_db.zadd(self.prefix + 'rows', priority, self._row(row))
        for column in columns:
            row_column_code = self.row_column_encode(row, column)
            key = self.urlsafe_uuid()
            path_to_key_db.set(self.prefix + row_column_code, key)
            key_to_path_db.set(self.prefix + key, row_column_code)

    def _row(self, row):
        return hashlib.md5(row).digest()[:self.random_prefix] + row

    def valid_user(self, user_id):
        return (self.mode == 'amt' and self.users_db.hget(self.prefix + user_id, 'workerId') is not None) or self.mode != 'amt'

    def get_row(self, user_id):
        # TODO: Do this in lua (high priority)
        num = 1
        while 1:
            rows = self.state_db.zrevrangebyscore(self.prefix + 'rows', float('inf'), float('-inf'), num=num, start=0)
            for row in rows:
                row = row[self.random_prefix:]
                if not self.state_db.sismember(self.prefix + 'seen:' + user_id, row):
                    self.state_db.sadd(self.prefix + 'seen:' + user_id, row)
                    if self.valid_user(user_id):
                        self.state_db.zincrby(self.prefix + 'rows', self._row(row), -1)
                    return row
            if num >= self.num_tasks:
                return
            num = min(num * 2, self.num_tasks)

    def data_lock(self):
        locked = 0
        data_lock = self.urlsafe_uuid()
        while 1:
            locked = self.state_db.set(self.prefix + 'data_lock', data_lock, nx=True, ex=self.lock_expire)
            if locked:
                break
            time.sleep(1.)
        print('Locked[%s]' % self.prefix)
        state_db = self.state_db.pipeline()
        key_to_path_db = self.key_to_path_db.pipeline()
        path_to_key_db = self.path_to_key_db.pipeline()
        return data_lock, state_db, key_to_path_db, path_to_key_db

    def data_locked(self, data_lock):
        return self.state_db.get(self.prefix + 'data_lock') == data_lock

    def data_lock_extend(self):
        self.state_db.expire(self.prefix + 'data_lock', self.lock_expire)

    def data_unlock(self, data_lock, state_db, key_to_path_db, path_to_key_db):
        self.data_lock_extend()
        if self.state_db.get(self.prefix + 'data_lock') == data_lock:
            state_db.execute()
            key_to_path_db.execute()
            path_to_key_db.execute()
            self.state_db.delete(self.prefix + 'data_lock')
        else:
            print('Could not unlock[%s]' % self.prefix)

    def sync(self):
        # Remove rows from the PQ that are no longer available, add new rows
        # NOTE: This gets us close to allowing arbitrary deletion during annotation;
        # however, we may just have given a user that row to annotate.  If a
        # file isn't found, the UI should just skip automatically.
        try:
            self.data_source_lock.acquire()
            data_lock, state_db, key_to_path_db, path_to_key_db = self.data_lock()
            del_rows = set(x[self.random_prefix:] for x in self.state_db.zrange(self.prefix + 'rows', 0, -1))
            add_rows = set()
            st = time.time() + self.lock_expire / 2
            for row, columns in self.data_source.row_columns():
                columns = set(columns)
                if time.time() >= st:
                    self.data_lock_extend()
                    st = time.time() + self.lock_expire / 2
                if self.required_columns.issubset(columns):
                    if row not in del_rows:
                        self._add_row(row, columns, state_db, key_to_path_db, path_to_key_db)
                        add_rows.add(row)
                    del_rows.discard(row)
            for x in del_rows:
                self.row_delete(x, state_db)
            print('Sync: Add[%d] Del[%d]' % (len(add_rows),
                                             len(del_rows)))
            self.data_unlock(data_lock, state_db, key_to_path_db, path_to_key_db)
        finally:
            self.data_source_lock.release()

    def destroy(self):
        data_lock, state_db, key_to_path_db, path_to_key_db = self.data_lock()
        self._flush_db(self.state_db, keep_rows=['data_lock'])
        for db in [self.users_db, self.response_db, self.key_to_path_db, self.path_to_key_db]:
            self.data_lock_extend()
            self._flush_db(db)
        self.data_unlock(data_lock, state_db, key_to_path_db, path_to_key_db)

    def _make_secret(self, secret=None):
        """Make secret used for admin functions"""
        if secret is None:
            self.secret = self.urlsafe_uuid()
        else:
            self.secret = secret
        print('Results URL:  /admin/%s/results.js' % self.secret)
        print('Users URL:  /admin/%s/users.js' % self.secret)
        print('Quit URL:  /admin/%s/stop' % self.secret)

    def urlsafe_uuid(self):
        """Make a urlsafe uuid"""
        return base64.urlsafe_b64encode(uuid.uuid4().bytes)[:-2]

    def user(self, bottle_request):
        """Make a new user entry"""
        user_id = self.urlsafe_uuid()
        out = {'queryString': bottle_request.query_string,
               'remoteAddr': bottle_request.remote_addr,
               'tasksFinished': 0,
               'tasksViewed': 0,
               'startTime': time.time()}
        out.update(dict(bottle_request.query))
        self.users_db.hmset(self.prefix + user_id, out)
        return {"userId": user_id}

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
        path = self.key_to_path_db.get(self.prefix + data_key)
        if path is None:
            raise KeyError
        row, column = self.row_column_decode(path)
        return self.read_row_column(row, column)

    def read_row_column(self, row, column):
        try:
            print('MTURK: Waiting for lock')
            self.data_source_lock.acquire()
            print('MTURK: Got lock')
            return self.data_source.value(row, column)
        finally:
            self.data_source_lock.release()

    def admin_users(self, secret):
        """Return contents of users_db"""
        if secret == self.secret:
            return {k.split(':', 1)[1]: self.users_db.hgetall(k) for k in self.users_db.keys(self.prefix + '*') if k.startswith(self.prefix)}

    def admin_results(self, secret):
        """Return contents of response_db"""
        if secret == self.secret:
            return {k.split(':', 1)[1]: self.response_db.hgetall(k) for k in self.response_db.keys(self.prefix + '*') if k.startswith(self.prefix)}

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
        cur_user = self.users_db.hgetall(self.prefix + user_id)
        if int(cur_user['tasksFinished']) >= self.num_tasks or force:
            end_time = time.time()
            self.users_db.hset(self.prefix + user_id, 'endTime', end_time)
            if self.mode == 'amt':
                pct_finished = int(cur_user['tasksFinished']) / float(cur_user['tasksViewed'])
                query_string = '&'.join(['%s=%s' % x for x in [('assignmentId', cur_user.get('assignmentId', 'NoId')),
                                                               ('pctFinished', pct_finished),
                                                               ('tasksFinished', cur_user['tasksFinished']),
                                                               ('tasksViewed', cur_user['tasksViewed']),
                                                               ('timeTaken', end_time - float(cur_user['startTime']))]])
                return {'submitUrl': '%s/mturk/externalSubmit?%s' % (cur_user.get('turkSubmitTo', 'http://www.mturk.com'), query_string)}
            else:
                return {'submitUrl': 'data:,Done%20annotating'}
        self.users_db.hincrby(self.prefix + user_id, 'tasksViewed')
        raise UserNotFinishedException

    def result(self, user_id):
        self.users_db.hincrby(self.prefix + user_id, 'tasksFinished')
