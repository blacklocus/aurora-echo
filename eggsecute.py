#!/usr/bin/python

## Copyright 2016 Ray Holder
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
## http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.

import os
import sys
import zipfile


def collect_single_module_file(module_name):
    """Return a list of tuples of (absolute_file_path, zip_target_path) for a single module file, like six"""
    loaded_module = __import__(module_name, globals(), locals(), [], 0)
    module_file = loaded_module.__file__
    file_path = os.path.basename(module_file)

    return [(module_file, file_path)]


def collect_module_files(module_name, relative_path_in_module):
    """Return a list of tuples of (absolute_file_path, zip_target_path)"""
    loaded_module = __import__(module_name, globals(), locals(), [], 0)
    module_path = os.path.dirname(loaded_module.__file__)
    if len(relative_path_in_module) == 0:
        # walk the whole module
        data_path = module_path
    else:
        # only walk the relative path in the module
        data_path = module_path + '/' + relative_path_in_module

    file_data = []
    for dirpath, dirnames, filenames in os.walk(data_path):
        for filename in filenames:
            file_path = dirpath + '/' + filename
            target_path = module_name + dirpath.replace(module_path, '') + '/' + filename
            file_data.append((file_path, target_path))
    return file_data

def main(script_path, output_path):
    if os.path.exists(output_path):
        sys.stderr.write("output path '%s' exists; refusing to overwrite\n" % output_path)
        return 1

    # tack Python header onto a file, zip file parsers ignore everything up until PK magic string
    outfile = open(output_path, 'w+b')
    outfile.write(b"#!/usr/bin/env python3\n")

    # make sure we flush, since we'll be writing zip data right after this
    outfile.flush()

    # create the zip file stream
    outzip = zipfile.ZipFile(outfile, 'a', zipfile.ZIP_DEFLATED)

    # this is the first thing that Python finds to run, __main__ is special
    outzip.write(script_path, "__main__.py")

    # hack to explicitly add everything
    module_files = []
    module_files.extend(collect_module_files('aurora_echo', ''))
    module_files.extend(collect_module_files('boto3', ''))
    module_files.extend(collect_module_files('botocore', ''))
    module_files.extend(collect_module_files('dateutil', ''))
    module_files.extend(collect_module_files('jmespath', ''))
    module_files.extend(collect_module_files('click', ''))
    module_files.extend(collect_single_module_file('six'))

    # filter out everything but .py's
    filtered_files = [x for x in module_files if x[1].endswith(".py") or x[1].endswith(".json") or x[1].endswith(".pem")]

    for source_path, relative_destination_path in set(filtered_files):
        outzip.write(source_path, relative_destination_path)
    outzip.close()
    outfile.close()

    os.chmod(output_path, 0o755)

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write("eggsecute <main_function_file> <output_package_file>\n")
        sys.exit(1)
    script_path = sys.argv[1]
    output_path = sys.argv[2]

    sys.exit(main(script_path, output_path))
