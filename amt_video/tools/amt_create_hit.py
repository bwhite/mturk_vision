import boto
import boto.mturk.qualification
import os

kw = {}
#kw = {'host': 'mechanicalturk.sandbox.amazonaws.com'}  # Uncomment for sandbox
mtc = boto.connect_mturk(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'], **kw)

question = boto.mturk.question.ExternalQuestion('http://api.dappervision.com:8000', 2000)
qualifications = boto.mturk.qualification.Qualifications()
#qualifications.add(boto.mturk.qualification.PercentAssignmentsApprovedRequirement('GreaterThan', 80, True))
#qualifications.add(boto.mturk.qualification.NumberHitsApprovedRequirement('GreaterThan', 100, True))
out = mtc.create_hit(question=question,
                     max_assignments=10,
                     qualifications=qualifications,
                     title='Write a short description for 5 videos',
                     description='Write a short description for 5 videos',
                     keywords='video annotation write quick fun'.split(),
                     duration=int(60 * 5),
                     reward=0.5)
