def quote(x):
    import cgi
    return cgi.quote(x, quote=True)

from base import AMTManager, UserNotFinishedException
from video import AMTVideoClassificationManager, AMTVideoTextMatchManager, AMTVideoDescriptionManager
from image import AMTImageClassificationManager
from image_entity import AMTImageEntityManager
from image_class import AMTImageClassManager
from image_segments import AMTImageSegmentsManager
from image_query import AMTImageQueryManager
from image_query_batch import AMTImageQueryBatchManager
from tools import create_hit
from manager import manager
