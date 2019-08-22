import base64
import cv2
import json
import numpy as np
import os
from shapely.geometry import Polygon
import tripy
import xml.etree.ElementTree as ET


XML_FILTER = ".xml"
PNG_FILTER = ".png"


def open_json(path_to_json):
    if not os.path.exists(path_to_json):
        return None
    with open(path_to_json, 'r') as f:
        layout = json.load(f)
    return layout


def get_path_to_img(path_to_xml):
    return os.path.abspath(path_to_xml)[:-len(XML_FILTER)] + PNG_FILTER


def add_base_information(root, path_to_xml, layout):
    folder_element = ET.Element('folder')
    folder_element.text = os.path.basename(os.path.split(path_to_xml)[0])
    filename_element = ET.Element('filename')
    filename_element.text = os.path.basename(path_to_xml)[:-len(XML_FILTER)] + PNG_FILTER
    path_element = ET.Element('path')
    path_element.text = get_path_to_img(path_to_xml)
    source_element = ET.Element('source')
    ET.SubElement(source_element, 'database').text = "Unknown"
    size_element = ET.Element('size')
    ET.SubElement(size_element, 'width').text = str(layout['imageWidth'])
    ET.SubElement(size_element, 'height').text = str(layout['imageHeight'])
    ET.SubElement(size_element, 'depth').text = "3"
    segmented_element = ET.Element('segmented')
    segmented_element.text = "0"
    root.append(folder_element)
    root.append(filename_element)
    root.append(path_element)
    root.append(source_element)
    root.append(size_element)
    root.append(segmented_element)


def add_object(root, name, bbox):
    object_element = ET.Element('object')
    ET.SubElement(object_element, 'name').text = name
    ET.SubElement(object_element, 'pose').text = "Unspecified"
    ET.SubElement(object_element, 'truncated').text = "0"
    ET.SubElement(object_element, 'difficult').text = "0"
    bbox_element = ET.SubElement(object_element, 'bndbox')
    ET.SubElement(bbox_element, 'xmin').text = str(bbox[0])
    ET.SubElement(bbox_element, 'ymin').text = str(bbox[1])
    ET.SubElement(bbox_element, 'xmax').text = str(bbox[2])
    ET.SubElement(bbox_element, 'ymax').text = str(bbox[3])
    root.append(object_element)


def get_polygon_from_polygon(points):
    return Polygon(points)


def get_polygon_from_rectangle(points):
    return Polygon([points[0], [points[0][0], points[1][1]], points[1], [points[1][0], points[0][1]]])


def easy_convert(layout):
    shape_map = {
        'polygon': get_polygon_from_polygon,
        'rectangle': get_polygon_from_rectangle
    }
    labels = []
    for _ in layout:
        points = np.round(_['points'])
        poly = shape_map[_['shape_type']](points)
        bbox = poly.bounds
        label = {'name': _['label'], 'bbox': np.asarray(bbox, int), 'poly': poly}
        labels.append(label)
    return labels


def create_xml(path_to_xml, layout, labels):
    tree = ET.ElementTree(element=ET.Element('annotation'))
    root = tree.getroot()
    add_base_information(root, path_to_xml, layout)
    for _ in labels:
        add_object(root, _['name'], _['bbox'])
    tree.write(path_to_xml)


def get_image(data):
    img_bytes = base64.b64decode(data)
    return cv2.imdecode(np.fromstring(img_bytes, np.uint8), cv2.IMREAD_COLOR)


def create_rect(bbox):
    return [[bbox[0], bbox[1]], [bbox[2], bbox[1]], [bbox[2], bbox[3]], [bbox[0], bbox[3]]]


def merge_walls(labels):
    flag = True
    coef = 0.5
    while flag:
        flag = False
        for _ in labels:
            for i, other in enumerate(labels):
                if other is _:
                    continue
                intersection = _['poly'].intersection(other['poly'])
                if intersection.is_empty:
                    continue
                if intersection.area / _['poly'].area >= coef or intersection.area / other['poly'].area >= coef:
                    union = _['poly'].union(other['poly'])
                    bbox = np.asarray(union.bounds, np.int32)
                    _['bbox'] = bbox
                    _['poly'] = Polygon(create_rect(bbox))
                    del labels[i]
                    flag = True
                    break
            if flag:
                break
    return labels


def get_splitted_images(img, labels):
    image1 = np.full(img.shape, np.uint8(255))
    image2 = image1.copy()
    new_labels1, new_labels2 = [], []
    for _ in labels:
        tmp = np.zeros(img.shape, np.uint8)
        poly = np.column_stack(_['poly'].exterior.coords.xy).astype(np.int32)[:-1]
        cv2.fillPoly(tmp, [poly], (255, 255, 255))
        mask_out = cv2.subtract(tmp, img)
        mask_out = cv2.subtract(tmp, mask_out)
        if 'wall' in _['name']:
            cv2.fillPoly(image1, [poly], 0)
            image1 = cv2.add(image1, mask_out)
            triangles = tripy.earclip(poly)
            wall_labels = []
            for tr in triangles:
                polygon = Polygon(tr)
                bbox = np.asarray(polygon.bounds, np.int32)
                label = {'name': _['name'], 'bbox': bbox, 'poly': Polygon(create_rect(bbox))}
                wall_labels.append(label)
            new_labels1.extend(merge_walls(wall_labels))
        else:
            cv2.fillPoly(image2, [poly], 0)
            image2 = cv2.add(image2, mask_out)
            new_labels2.append(_)
    return [image1, image2], [new_labels1, new_labels2]


def change_size_image(img, layout, rect):
    height, width, channels = img.shape
    h = rect[1]
    w = int(h * width / height)
    if w > rect[0]:
        w = rect[0]
        h = int(height / width * w)
    new_img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    s = np.full((rect[1], rect[0], 3), np.uint8(255))
    sy = int((rect[1] - h) / 2)
    sx = int((rect[0] - w) / 2)
    s[sy:sy + h, sx:sx + w] = new_img

    for shape in layout['shapes']:
        points = shape['points']
        for i, _ in enumerate(points):
            points[i] = (int(sx + _[0] * w / width), int(sy + _[1] * h / height))
    return s


def convert(path_to_json, path_to_xml, easy_mode=True, rect=None):
    print("Filename `%s`" % path_to_json)
    layout = open_json(path_to_json)
    if layout is None:
        return
    img = get_image(layout['imageData'])
    if rect is not None:
        img = change_size_image(img, layout, rect)
    labels = easy_convert(layout['shapes'])
    if easy_mode:
        create_xml(path_to_xml, layout, labels)
        cv2.imwrite(get_path_to_img(path_to_xml), img)
    else:
        images, labels = get_splitted_images(img, labels)
        paths = [path_to_xml[:-len(XML_FILTER)] + "_" + str(i) + XML_FILTER for i in range(len(images))]
        for i in range(len(images)):
            create_xml(paths[i], layout, labels[i])
            cv2.imwrite(get_path_to_img(paths[i]), images[i])
