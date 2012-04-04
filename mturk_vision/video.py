import mturk_vision
from shove import Shove
import random
import math
import glob
import os
import time
import json


class AMTVideoClassificationManager(mturk_vision.AMTManager):

    def __init__(self, frame_db, response_db, *args, **kw):
        super(AMTVideoClassificationManager, self).__init__(*args, **kw)
        self.frame_db = frame_db  # [event][video] = frames
        self.response_db = response_db
        self.dbs += [self.frame_db, self.response_db]

    def _prune_frame_paths(self, frame_paths, target_frames=10):
        target_frames = float(target_frames)
        # Remove every other path - + - +
        frame_paths = frame_paths[::2]
        return frame_paths[::int(max(1, math.ceil(len(frame_paths) / target_frames)))]

    def initial_setup(self, data_root):
        if data_root == None:
            data_root ='./data/'
        # Build initial frame structure
        path_to_key_db = self.path_to_key_db.pipeline()
        key_to_path_db = self.key_to_path_db.pipeline()
        frame_db = self.frame_db.pipeline()
        frame_db_local = {}  # [event][video] = frames
        for event_path in glob.glob('%s/*' % data_root):
            if not os.path.isdir(event_path):
                continue
            event = os.path.basename(event_path)
            frame_db_local[event] = {}
            for video_path in glob.glob(event_path + '/*'):
                if not os.path.isdir(video_path):
                    continue
                video = os.path.basename(video_path)
                frame_db_local[event][video] = []
                frame_paths = self._prune_frame_paths(sorted(glob.glob(video_path + '/*.jpg')))
                for frame_path in frame_paths:
                    frame_db_local[event][video].append(os.path.abspath(frame_path))
        for event, data in frame_db_local.items():
            frame_db.hmset(event, dict((x, json.dumps(y)) for x, y in data.items()))
            print(event)
        for event in frame_db_local:
            for video in frame_db_local[event]:
                for fn in frame_db_local[event][video]:
                    key = self.urlsafe_uuid()
                    path_to_key_db.set(fn, key)
                    key_to_path_db.set(key, fn)
        path_to_key_db.execute()
        key_to_path_db.execute()
        frame_db.execute()

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        event = self.frame_db.randomkey()
        video = random.choice(self.frame_db.hkeys(event))
        out = {"images": [],
               "data_id": self.urlsafe_uuid()}
        self.response_db.hmset(out['data_id'], {'event': event, 'video': video,
                                                'user_id': user_id, 'start_time': time.time()})
        for frame in json.loads(self.frame_db.hget(event, video)):
            out['images'].append({"src": 'image/%s.jpg' % self.path_to_key_db.get(frame), "width": 250})  # TODO(brandyn): batch this
        return out

    def admin_results(self, secret):
        """Return contents of response_db"""
        if secret == self.secret:
            keys = self.response_db.keys('*')
            return json.dumps(dict(zip(keys, self.response_db.mget(keys))))

    def result(self, user_id, data_id, data):
        #assert request['user_id'] in USERS_DB
        assert self.response_db.hget(data_id, 'user_id') == user_id
        # Don't double count old submissions
        if not self.response_db.hexists(data_id, 'user_event'):
            if data == self.response_db.hget(data_id, 'event'):
                super(AMTVideoClassificationManager, self).result(user_id, True)
            else:
                super(AMTVideoClassificationManager, self).result(user_id, False)
            self.response_db.hmset(data_id, {'user_event': data, 'end_time': time.time()})
        return self.make_data(user_id)


class AMTVideoTextMatchManager(AMTVideoClassificationManager):

    def __init__(self, description_db, extra_same_class=4, extra_other_class=5, *args, **kw):
        super(AMTVideoTextMatchManager, self).__init__(*args, **kw)
        self.description_db = description_db  # [video] = {event, description}
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
            out = random.choice(list(set(self.frame_db.hkeys(event)) - previous))
            previous.add(out)
            yield event, out

    def make_data(self, user_id):
        try:
            return self._user_finished(user_id)
        except mturk_vision.UserNotFinishedException:
            pass
        # Select a description
        previous_video_descriptions = self.users_db.hget(user_id, 'previous_video_descriptions')
        previous_video_descriptions = set() if previous_video_descriptions is None else set(json.loads(previous_video_descriptions))
        try:
            available_videos = list(set(self.description_db.keys()) - previous_video_descriptions)
            print('Videos Left[%d]' % len(available_videos))
            positive_video = random.choice(available_videos)
        except IndexError:  # There are no more left
            return self._user_finished(user_id, force=True)
        # Write the updated prev descriptions to the user db
        previous_video_descriptions.add(positive_video)
        self.users_db.hset(user_id, 'previous_video_description', json.dumps(list(previous_video_descriptions)))
        # Select other videos from the same class
        positive_event = self.description_db.hget(positive_video, 'event')
        event_videos = [(positive_event, positive_video)]
        event_videos += list(self._random_videos([positive_event] * self.extra_same_class))
        other_classes = list(set(self.frame_db.keys()) - set(positive_event))
        event_videos += list(self._random_videos(random.choice(other_classes) for x in range(self.extra_other_class)))
        random.shuffle(event_videos)
        out = {'images': [],
               'data_id': self.urlsafe_uuid(),
               'description': self.description_db.hget(positive_video, 'description')}
        self.response_db.hmset(out['data_id'], {'event_videos': json.dumps(event_videos), 'positive_video': positive_video,
                                                'positive_event': positive_event,
                                                'user_id': user_id, 'start_time': time.time()})
        for event, video in event_videos:
            cur_out = []
            for frame in json.loads(self.frame_db.hget(event, video)):
                cur_out.append({"src": 'image/%s.jpg' % self.path_to_key.get(frame), "width": 250})
            out['images'].append(cur_out)
        return out

    def result(self, user_id, data_id, video_index):
        #{u'video_index': 6, u'user_id': u'zXIJYA5LSFOxcuuSoKRJWQ', u'data_id': u'C6CGNbZJRlKsFnVWI078_Q'}
        #assert request['user_id'] in USERS_DB
        assert self.resonse_db.hget(data_id, 'user_id') == user_id
        assert 0 <= video_index < len(self.response_db.hget(data_id, 'event_videos'))
        # Don't double count old submissions
        if not self.response_db.hexists(data_id, 'video_index'):
            if json.loads(self.response_db.hget(data_id, 'event_videos'))[video_index][1] == self.response_db.hget(data_id, 'positive_video'):
                super(AMTVideoClassificationManager, self).result(user_id, True)
            else:
                super(AMTVideoClassificationManager, self).result(user_id, False)
            self.response_db.hmset(data_id, {'video_index': video_index, 'end_time': time.time()})
        return self.make_data(user_id)


class AMTVideoDescriptionManager(AMTVideoClassificationManager):

    def __init__(self, description_db, *args, **kw):
        super(AMTVideoDescriptionManager, self).__init__(*args, **kw)
        self.description_db = description_db  # [video] = {event, description, description_type}
        self.dbs += [self.description_db]

    def _generate_description_type(self):
        d = {'color_adj': {'description': 'Dominant colors', 'example': 'blue, red, green, yellow, purple, orange', 'type': 'Colors (adjectives)'},
                      'thing_noun': {'description': 'Important objects', 'example': 'person, bird, bus, car, knife, ball', 'type': 'Foreground Objects (nouns)'},
                      'stuff_noun': {'description': 'Background details, textures, and materials.', 'example': 'sky, grass, trees, water, road, carpet, brick wall, wood floor, rocks', 'type': 'Background Objects (nouns)'},
                      'scene': {'description': 'Name of the scene', 'example': 'outdoors, indoors, cricket field, skateboard park', 'type': 'Scene Name (nouns)'}}
        s = {}
        s['words'] = {'type': 'Freeform Text', 'example': 'The man does a skateboard trick outdoors on a ramp using a red board under a blue sky near a green tree', 'description': 'The description should be less than 140 characters and you do not need formatting.'}
        return {'details': d, 'styles': s}

    def make_data(self, user_id, description_type=None):
        out = super(AMTVideoDescriptionManager, self).make_data(user_id)
        if 'data_id' not in out:  # User is done
            return out
        if description_type is None:
            description_type = self._generate_description_type()
        out['description_type'] = description_type
        self.response_db.hset(out['data_id'], 'description_type', json.dumps(description_type))
        return out
    
    def result(self, user_id, data_id, description):
        assert self.response_db.hget(data_id, 'user_id') == user_id
        # Don't double count old submissions
        if not self.response_db.hexists(data_id, 'description'):
            super(AMTVideoClassificationManager, self).result(user_id, False)
            self.response_db.hmset(data_id, {'description': description, 'end_time': time.time()})
        description_type = self.response_db.hget(data_id, 'description_type')
        video = self.response_db.hget(data_id, 'video')
        if not self.description_db.exists(video):
            self.description_db.hmset(video, {'event': self.response_db.hget(data_id, 'event'),
                                              'description': self.response_db.hget(data_id, 'description'),
                                              'description_type': description_type})
        return self.make_data(user_id, json.loads(description_type))
