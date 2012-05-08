import boto
import boto.mturk.qualification
import os


def create_hit(title, description, duration, reward, max_assignments, keywords, url,
               max_spend=10, sandbox=False):
    kw = {}
    if sandbox:
        kw = {'host': 'mechanicalturk.sandbox.amazonaws.com'}
    mtc = boto.connect_mturk(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'], **kw)

    question = boto.mturk.question.ExternalQuestion(url, 2000)
    qualifications = boto.mturk.qualification.Qualifications()
    qualifications.add(boto.mturk.qualification.PercentAssignmentsApprovedRequirement('GreaterThan', 80, True))
    qualifications.add(boto.mturk.qualification.NumberHitsApprovedRequirement('GreaterThan', 100, True))
    assert reward * max_assignments <= max_spend  # NOTE(brandyn): Simple safety mechanism to prevent one type of error
    mtc.create_hit(question=question,
                   max_assignments=max_assignments,
                   qualifications=qualifications,
                   title=title,
                   description=description,
                   keywords=keywords,
                   duration=duration,
                   reward=reward)
