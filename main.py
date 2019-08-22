import argparse
import os
import traceback

from converter import convert


FILE_FILTER = '.json'


def register_launch_arguments():
    parser = argparse.ArgumentParser(description='Serve the application')
    parser.add_argument('-i', '--input', help='input path - folder with json files or file from labelme', required=True)
    parser.add_argument('-o', '--output', help='output path - folder for xml files for labelImg', required=True)
    parser.add_argument('-e', '--easy', help='easy converter', action="store_true")
    parser.add_argument('-t', '--tree', help='iterate in tree of folders', action="store_true")
    parser.add_argument('-r', '--rect', help='new size of the image', nargs=2, type=int)

    return parser.parse_args()


def create_xml_path(path_to_json, output):
    return os.path.join(output, "%s.xml" % os.path.basename(path_to_json)[:-len(FILE_FILTER)])


def wrapper_convert(path_to_json, path_to_xml, easy_mode=True, rect=None):
    print("Filename `%s`" % path_to_json)
    try:
        convert(path_to_json, path_to_xml, easy_mode, rect)
        print("OK")
    except:
        print("FAILURE")
        traceback.print_exc()
        return 1
    return 0


if __name__ == '__main__':
    args = register_launch_arguments()

    input_path = args.input
    output_path = args.output
    easy_converter = args.easy
    rect = args.rect
    if rect is not None:
        rect = [abs(_) for _ in rect]

    if not os.path.exists(input_path):
        print("Input path `%s` doesn't exist" % input_path)

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    cnt_fail = 0
    if os.path.isfile(input_path) and input_path[-len(FILE_FILTER):].lower() == FILE_FILTER:
        cnt_fail += wrapper_convert(input_path, create_xml_path(input_path, output_path), easy_converter, rect)
    elif not args.tree:
        files = os.listdir(input_path)
        for _ in filter(lambda x: x[-len(FILE_FILTER):].lower() == FILE_FILTER, files):
            cnt_fail += wrapper_convert(os.path.join(input_path, _), create_xml_path(_, output_path), easy_converter, rect)
    else:
        tree = os.walk(input_path)
        for _ in tree:
            if len(_[1]) > 0:
                continue
            for file in filter(lambda x: x[-len(FILE_FILTER):].lower() == FILE_FILTER, _[2]):
                cnt_fail += wrapper_convert(os.path.join(_[0], file), create_xml_path(file, output_path),
                                            easy_converter, rect)
    print("Fail converting: %d" % cnt_fail)
