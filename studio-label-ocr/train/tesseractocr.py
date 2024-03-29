import os
import json
import pytesseract
from PIL import Image
from pathlib import Path
from uuid import uuid4
import glob

import ctypes
from ctypes.util import find_library
find_library("".join(("gsdll", str(ctypes.sizeof(ctypes.c_voidp) * 8), ".dll")))
# Define Paths
poppler_path = r'C:\\Program Files\\poppler-0.68.0\\bin'
pytesseract.pytesseract.tesseract_cmd =r'C:/Program Files/Tesseract-OCR/tesseract.exe'

# pytesseract.pytesseract.tesseract_cmd = 'C:/Program Files (x86)/Tesseract- OCR/tesseract'
# TESSDATA_PREFIX = 'C:/Program Files (x86)/Tesseract-OCR'


def create_image_url(filepath):
    """
    Label Studio requires image URLs, so this defines the mapping from filesystem to URLs
    if you use ./serve_local_files.sh <my-images-dir>, the image URLs are localhost:8081/filename.png
    Otherwise you can build links like /data/upload/filename.png to refer to the files
    """
    filename = os.path.basename(filepath)
    # return f'http://localhost:8081/{filename}'
    return filename


def convert_to_ls(image, tesseract_output, LEVELS, per_level):
    """
    :param image: PIL image object
    :param tesseract_output: the output from tesseract
    :param per_level: control the granularity of bboxes from tesseract
    :return: tasks.json ready to be imported into Label Studio with "Optical Character Recognition" template
    """
    image_width, image_height = image.size
    per_level_idx = LEVELS[per_level]
    results = []
    all_scores = []
    for i, level_idx in enumerate(tesseract_output['level']):
        if level_idx == per_level_idx:
            bbox = {
                'x': 1000 * tesseract_output['left'][i] / image_width,
                'y': 1000 * tesseract_output['top'][i] / image_height,
                'width': 1000 * tesseract_output['width'][i] / image_width,
                'height': 1000 * tesseract_output['height'][i] / image_height,
                'rotation': 0
            }
            words, confidences = [], []
            for j, curr_id in enumerate(tesseract_output[per_level]):
                if curr_id != tesseract_output[per_level][i]:
                    continue
                word = tesseract_output['text'][j]
                confidence = tesseract_output['conf'][j]
                words.append(word)
                if confidence != '-1':
                    confidences.append(float(float(confidence) / 100.0))

            text = ' '.join(words).strip()
            if not text:
                continue
            region_id = str(uuid4())[:10]
            score = sum(confidences) / len(confidences) if confidences else 0
            bbox_result = {
                'id': region_id, 'from_name': 'bbox', 'to_name': 'image', 'type': 'rectangle',
                'value': bbox}
            transcription_result = {
                'id': region_id, 'from_name': 'transcription', 'to_name': 'image', 'type': 'textarea',
                'value': dict(text=[text], **bbox), 'score': score}
            results.extend([bbox_result, transcription_result])
            all_scores.append(score)

    return {
        'data': {
            'ocr': create_image_url(image.filename)
        },
        'predictions': [{
            'result': results,
            'score': sum(all_scores) / len(all_scores) if all_scores else 0
        }]
    }

def main():
    # tesseract output levels for the level of detail for the bounding boxes
    with open('output.txt', 'w') as www:
        www.write('start'+'\n')
    LEVELS = {
        'page_num': 1,
        'block_num': 2,
        'par_num': 3,
        'line_num': 4,
        'word_num': 5
    }
    tasks = []
    y = glob.glob('*.*')
    # collect the receipt images from the image directory
    for f in glob.glob('*.jpg'):
        with Image.open(f) as image:
            tesseract_output = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            with open('output.txt', 'a') as www:
                www.write(str(tesseract_output)+'='*10+'\n')
            task = convert_to_ls(image, tesseract_output, LEVELS,per_level='page_num')
            tasks.append(task)
            with open('output.txt', 'a') as www:
                www.write(str(tasks)+'\n')
        break
    # create a file to import into Label Studio
    with open('ocr_tasks.json', mode='w') as f:
        json.dump(tasks, f, indent=2)

if __name__ == "__main__":
    main()  