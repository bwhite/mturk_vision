def quote(x):
    import cgi
    return cgi.escape(x, quote=True)

from base import AMTManager, UserNotFinishedException
from image_class import AMTImageClassManager
from image_qa import AMTImageQAManager
from tools import create_hit
from manager import manager
