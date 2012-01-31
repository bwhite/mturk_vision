import bottle
import base64
import uuid
import json
import time
import random
import math
import glob
import os
from shove import Shove
import cPickle as pickle


class NotFinished(Exception):
    """Exception thrown when a user isn't finished"""


class AMTManager(object):
    
    def __init__(self, mode, num_tasks, index_path, config_path, user_db_uri,
                 key_to_path_db_uri, path_to_key_db_uri, **kw):
        self.mode = mode
        self.num_tasks = num_tasks
        self.index = open(index_path).read()
        self.config = json.load(open(config_path))
        self.users_db = Shove(user_db_uri)
        self.key_to_path_db = Shove(key_to_path_db_uri)
        self.path_to_key_db = Shove(path_to_key_db_uri)
        self._make_secret()

    def _make_secret(self):
        """Make secret used for admin functions"""
        self.secret = self.urlsafe_uuid()
        open('SECRET', 'w').write(self.secret)
        print('Results URL:  /%s/results.js' % self.secret)
        print('Users URL:  /%s/users.js' % self.secret)

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

    def _user_finished(self, user_id):
        """Check if the user has finished their tasks, if so output the return dictionary

        Args:
            user_id: User ID string

        Returns:
            A dictionary of the result.

        Raises:
            NotFinished: User hasn't finished their tasks
        """
        cur_user = self.users_db[user_id]
        if self.mode != 'standalone' and cur_user['tasks_finished'] >= self.num_tasks:
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
        raise NotFinished

    def result(self, user_id, correct):
        user = self.users_db[user_id]
        user['tasks_finished'] += 1
        if correct:
            user['tasks_correct'] += 1
        self.users_db[user_id] = user
    

class AMTVideoClassificationManager(AMTManager):

    def __init__(self, frame_db_uri, response_db_uri, *args, **kw):
        super(AMTVideoClassificationManager, self).__init__(*args, **kw)
        self.frame_db = Shove(frame_db_uri)  # [event][video] = frames
        self.response_db = Shove(response_db_uri)

    def _prune_frame_paths(self, frame_paths, target_frames=10):
        target_frames = float(target_frames)
        # Remove every other path - + - +
        frame_paths = frame_paths[::2]
        return frame_paths[::int(max(1, math.ceil(len(frame_paths) / target_frames)))]

    def initial_setup(self, data_root='./data/'):
        # Build initial frame structure
        frame_db = {}  # [event][video] = frames
        for event_path in glob.glob('%s/*' % data_root):
            if not os.path.isdir(event_path):
                continue
            event = os.path.basename(event_path)
            frame_db[event] = {}
            for video_path in glob.glob(event_path + '/*'):
                if not os.path.isdir(video_path):
                    continue
                video = os.path.basename(video_path)
                frame_db[event][video] = []
                frame_paths = self._prune_frame_paths(sorted(glob.glob(video_path + '/*')))
                for frame_path in frame_paths:
                    frame_db[event][video].append(frame_path)
        self.frame_db.update(frame_db)
        frames = []
        for event in frame_db:
            for video in frame_db[event]:
                for frame in frame_db[event][video]:
                    frames.append(frame)
        for frame in frames:
            key = self.urlsafe_uuid()
            self.path_to_key_db[frame] = key
            self.key_to_path_db[key] = frame

    def make_data(self, user_id):
        event = random.choice(list(self.frame_db))
        video = random.choice(list(self.frame_db[event]))
        try:
            return self._user_finished(user_id)
        except NotFinished:
            pass
        out = {"images": [],
               "data_id": self.urlsafe_uuid()}
        self.response_db[out['data_id']] = {'event': event, 'video': video,
                                            'user_id': user_id, 'start_time': time.time()}
        for frame in self.frame_db[event][video]:
            out['images'].append({"src": 'frames/%s.jpg' % self.path_to_key_db[frame], "width": 250})
        self.users_db[user_id]['tasks_viewed'] = self.users_db[user_id]['tasks_viewed'] + 1
        return out

    def admin_results(self, secret):
        """Return contents of response_db"""
        if secret == self.secret:
            return json.dumps(dict(self.response_db))

    def result(self, user_id, data_id, event):
        #assert request['user_id'] in USERS_DB
        response = self.response_db[data_id]
        assert response['user_id'] == user_id
        # Don't double count old submissions
        if 'user_event' not in response:
            response['user_event'] = event
            if event == response['event']:
                super(AMTVideoClassificationManager, self).result(user_id, True)
            else:
                super(AMTVideoClassificationManager, self).result(user_id, False)
        self.response_db[data_id] = response
        return self.make_data(user_id)
