import boto
import boto.mturk.qualification
import os

kw = {}
#kw = {'host': 'mechanicalturk.sandbox.amazonaws.com'}  # Uncomment for sandbox
mtc = boto.connect_mturk(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'], **kw)
