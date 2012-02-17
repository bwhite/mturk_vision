from distutils.core import setup

setup(name='mturk_vision',
      version='.01',
      packages=['mturk_vision'],
      package_data={'mturk_vision': ['data/*', 'static/*', 'static_private/*']})
