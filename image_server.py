import os
import io
import time

from PIL import Image

parent_dir = os.path.dirname(os.path.abspath(__file__))
IMAGES_PATH = os.path.join(parent_dir, "balls(20fps)-jpg")
DEBUG_IMAGES_PATH = os.path.join(parent_dir, "debug(20fps)-jpg")

def load_images(dirname):
    images = []
    for f in os.listdir(dirname):
        image_path = os.path.join(dirname, f)
        image = Image.open(image_path)
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        images.append(buffer.getvalue())
    return images


def gen_frames_v1(images_obj):
    img_list = images_obj['list']
    if images_obj['index'] >= len(img_list):
        images_obj['index'] = 0

    index = images_obj['index']
    images_obj['index'] += 1

    return img_list[index]

image_gen = {
    "index": 0,
    "list": load_images(IMAGES_PATH),
}
debug_image_gen = {
    "index": 0,
    "list": load_images(DEBUG_IMAGES_PATH),
}

def gen_frames_v2(fps, debug=False):
    if debug:
        img_list = debug_image_gen['list']
        index = debug_image_gen['index']
    else:
        img_list = image_gen['list']
        index = image_gen['index']
    while True:
        index += 1
        if index >= len(img_list):
            index = 0

        frame = img_list[index]
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
        )
        time.sleep(1 / fps)
