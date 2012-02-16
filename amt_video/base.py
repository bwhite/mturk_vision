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


class NotFinished(Exception):
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
            NotFinished: User hasn't finished their tasks
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
        self.dbs += [self.frame_db, self.response_db]

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
                frame_paths = self._prune_frame_paths(sorted(glob.glob(video_path + '/*.jpg')))
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
        try:
            return self._user_finished(user_id)
        except NotFinished:
            pass
        event = random.choice(list(self.frame_db))
        video = random.choice(list(self.frame_db[event]))
        out = {"images": [],
               "data_id": self.urlsafe_uuid()}
        self.response_db[out['data_id']] = {'event': event, 'video': video,
                                            'user_id': user_id, 'start_time': time.time()}
        for frame in self.frame_db[event][video]:
            out['images'].append({"src": 'frames/%s.jpg' % self.path_to_key_db[frame], "width": 250})
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
            response['end_time'] = time.time()
            self.response_db[data_id] = response
        return self.make_data(user_id)


class AMTVideoTextMatchManager(AMTVideoClassificationManager):

    def __init__(self, description_db_uri, extra_same_class=4, extra_other_class=5, *args, **kw):
        super(AMTVideoTextMatchManager, self).__init__(*args, **kw)
        self.description_db = Shove(description_db_uri)  # [video] = {event, description}
        self.extra_same_class = extra_same_class
        self.extra_other_class = extra_other_class
        self.dbs += [self.description_db]

    def _random_videos(self, events, previous=()):
        """Provides an iterator of videos corresponding to the provided events without duplicates

        Args:
            events:  Iterator of events

        Yields:
            (event, video_id)
        """
        previous = set(previous)
        for event in events:
            while 1:
                out = random.choice(list(self.frame_db[event]))
                if out not in previous:
                    break
            previous.add(out)
            yield event, out

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except NotFinished:
            pass
        # Select a description
        user = self.users_db[user_id]
        previous_video_descriptions = user.get('previous_video_descriptions', set())
        try:
            available_videos = list(set(self.description_db) - previous_video_descriptions)
            print('Videos Left[%d]' % len(available_videos))
            positive_video = random.choice(available_videos)
        except IndexError:  # There are no more left
            return self._user_finished(user_id, force=True)
        # Write the updated prev descriptions to the user db
        previous_video_descriptions.add(positive_video)
        user['previous_video_descriptions'] = previous_video_descriptions
        self.users_db[user_id] = user
        # Select other videos from the same class
        positive_event = self.description_db[positive_video]['event']
        event_videos = [(positive_event, positive_video)]
        event_videos += list(self._random_videos([positive_event] * self.extra_same_class))
        other_classes = list(set(self.frame_db) - set(positive_event))
        event_videos += list(self._random_videos(random.choice(other_classes) for x in range(self.extra_other_class)))
        random.shuffle(event_videos)
        out = {'images': [],
               'data_id': self.urlsafe_uuid(),
               'description': self.description_db[positive_video]['description']}
        self.response_db[out['data_id']] = {'event_videos': event_videos, 'positive_video': positive_video,
                                            'positive_event': positive_event,
                                            'user_id': user_id, 'start_time': time.time()}
        for event, video in event_videos:
            cur_out = []
            for frame in self.frame_db[event][video]:
                cur_out.append({"src": 'frames/%s.jpg' % self.path_to_key_db[frame], "width": 250})
            out['images'].append(cur_out)
        return out

    def result(self, user_id, data_id, video_index):
        #{u'video_index': 6, u'user_id': u'zXIJYA5LSFOxcuuSoKRJWQ', u'data_id': u'C6CGNbZJRlKsFnVWI078_Q'}
        #assert request['user_id'] in USERS_DB
        response = self.response_db[data_id]
        assert response['user_id'] == user_id
        assert 0 <= video_index < len(response['event_videos'])
        # Don't double count old submissions
        if 'video_index' not in response:
            response['video_index'] = video_index
            if response['event_videos'][video_index][1] == response['positive_video']:
                super(AMTVideoClassificationManager, self).result(user_id, True)
            else:
                super(AMTVideoClassificationManager, self).result(user_id, False)
            response['end_time'] = time.time()
            self.response_db[data_id] = response
        return self.make_data(user_id)


class AMTVideoDescriptionManager(AMTVideoClassificationManager):

    def __init__(self, description_db_uri, *args, **kw):
        super(AMTVideoDescriptionManager, self).__init__(*args, **kw)
        self.description_db = Shove(description_db_uri)  # [video] = {event, description}
        self.dbs += [self.description_db]

    def _generate_description_type(self):
        desc_types = [{'color_adj': {'description': 'Dominant colors', 'example': 'blue, red, green, yellow, purple, orange', 'type': 'Colors (adjectives)'}},
                      {'thing_noun': {'description': 'Important objects', 'example': 'person, bird, bus, car, knife, ball', 'type': 'Foreground Objects (nouns)'}},
                      {'stuff_noun': {'description': 'Background details, textures, and materials.  Not foreground objects.', 'example': 'sky, grass, trees, water, road, carpet, brick wall, wood floor, rocks', 'type': 'Background Objects (nouns)'}},
                      {'scene': {'description': 'Name of the scene', 'example': 'outdoors, indoors, cricket field, skateboard park', 'type': 'Scene Name (nouns)'}}]
        d = random.choice(desc_types)
        s = {}
        s['words'] = {'type': 'Words by Priority', 'example': 'word0, word1, word2a word2b, word3', 'description': 'The first word (e.g., word0 in the example) is the most noticeable in the video and the words are of the detail type(s) requested.  Separate words by commas, multiple related words are allowed together (e.g., word2a word2b).  The description should be less than 140 characters.'}
        return {'details': d, 'styles': s}

    def make_data(self, user_id, description_type=None):
        out = super(AMTVideoDescriptionManager, self).make_data(user_id)
        if description_type is None:
            description_type = self._generate_description_type()
        print(out)
        response = self.response_db[out['data_id']]
        response['description_type'] = out['description_type'] = description_type
        self.response_db[out['data_id']] = response
        return out
    
    def result(self, user_id, data_id, description):
        response = self.response_db[data_id]
        assert response['user_id'] == user_id
        # Don't double count old submissions
        if 'description' not in response:
            response['description'] = description
            super(AMTVideoClassificationManager, self).result(user_id, False)
            response['end_time'] = time.time()
            self.response_db[data_id] = response
        description_type = response['description_type']
        if response['video'] not in self.description_db:
            self.description_db[response['video']] = [{'event': response['event'],
                                                       'description': response['description'],
                                                       'description_type': description_type}]
        return self.make_data(user_id, description_type)
