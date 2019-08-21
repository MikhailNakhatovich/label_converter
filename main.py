import argparse
import os

from converter import convert


FILE_FILTER = '.json'


def register_launch_arguments():
    parser = argparse.ArgumentParser(description='Serve the application')
    parser.add_argument('-i', '--input', help='input path - folder with json files or file from labelme', required=True)
    parser.add_argument('-o', '--output', help='output path - folder for xml files for labelImg', required=True)
    parser.add_argument('-e', '--easy', help='easy converter', action="store_true")
    parser.add_argument('-t', '--tree', help='iterate in tree of folders', action="store_true")

    return parser.parse_args()


def create_xml_path(path_to_json, output):
    return os.path.join(output, "%s.xml" % os.path.basename(path_to_json)[:-len(FILE_FILTER)])


if __name__ == '__main__':
    args = register_launch_arguments()

    input_path = args.input
    output_path = args.output
    easy_converter = args.easy

    if not os.path.exists(input_path):
        print("Input path `%s` doesn't exist" % input_path)

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    if os.path.isfile(input_path) and input_path[-len(FILE_FILTER):].lower() == FILE_FILTER:
        convert(input_path, create_xml_path(input_path, output_path), easy_converter)
    elif not args.tree:
        files = os.listdir(input_path)
        for _ in filter(lambda x: x[-len(FILE_FILTER):].lower() == FILE_FILTER, files):
            convert(os.path.join(input_path, _), create_xml_path(_, output_path), easy_converter)
    else:
        tree = os.walk(input_path)
        for _ in tree:
            if not _[1]:
                for file in filter(lambda x: x[-len(FILE_FILTER):].lower() == FILE_FILTER, _[2]):
                    convert(os.path.join(_[0], file), create_xml_path(file, output_path), easy_converter)
