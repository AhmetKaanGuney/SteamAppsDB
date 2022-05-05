import os
import io
import time

from PIL import Image

parent_dir = os.path.dirname(os.path.abspath(__file__))
IMAGES_PATH = os.path.join(parent_dir, "balls(20fps)-jpg")

def load_images():
    images = []
    for f in os.listdir(IMAGES_PATH):
        image_path = os.path.join(IMAGES_PATH, f)
        image = Image.open(image_path)
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        images.append(buffer.getvalue())
    return images

images = {
    "index": 0,
    "list": load_images(),
}

def yield_image(images_obj):
    img_list = images_obj['list']
    images_obj['index'] += 1
    if images_obj['index'] >= len(img_list):
        images_obj['index'] = 0

    index = images_obj['index']

    return img_list[index]


def gen_frames():
    img_list = images['list']
    index = images['index']
    while True:
        index += 1
        if index >= len(img_list):
            index = 0

        frame = img_list[index]
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
        )
        time.sleep(1 / 20)