def quote(x):
    import cgi
    return cgi.escape(x, quote=True)

from base import AMTManager, UserNotFinishedException
from image import AMTImageClassificationManager
from image_class import AMTImageClassManager
from image_query_batch import AMTImageQueryBatchManager
from tools import create_hit
from manager import manager
