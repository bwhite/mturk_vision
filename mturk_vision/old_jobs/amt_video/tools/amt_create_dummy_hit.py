import boto
import boto.mturk.qualification
import os

kw = {}
#kw = {'host': 'mechanicalturk.sandbox.amazonaws.com'}  # Uncomment for sandbox
mtc = boto.connect_mturk(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'], **kw)

question = boto.mturk.question.ExternalQuestion('http://api.dappervision.com:8001', 1500)
qualifications = boto.mturk.qualification.Qualifications()
qualifications.add(boto.mturk.qualification.PercentAssignmentsApprovedRequirement('GreaterThan', 80, True))
qualifications.add(boto.mturk.qualification.NumberHitsApprovedRequirement('GreaterThan', 100, True))
out = mtc.create_hit(question=question,
                     max_assignments=20,
                     qualifications=qualifications,
                     title='Do not attempt, No Reward oyGXb8ynEkNMLic',
                     description='Do not attempt, no reward oyGXb8ynEkNMLic',
                     keywords='dummy'.split(),
                     duration=int(60 * 30),
                     reward=0.0)
