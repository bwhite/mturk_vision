import mturk_vision

description = 'You are given a single category, you are to only select segments that belong to this category.  Segments are selected/deselected by clicking on the image with your mouse, when you are done press enter or click the submit button. Segments you select should be mostly (>75%) the category you are given.  Only select segments that you are confident about.  Not all images will have the category you are given, just press submit.'
mturk_vision.create_hit('Label image segments for 25 images', description, duration=25 * 60, reward=.15, max_assignments=10, keywords=['image', 'segments'], url='http://api0.picar.us:16000/')
