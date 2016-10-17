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

import atexit
import codecs
import json
import os
import sys
import tempfile
import zipfile

import botocore.loaders

from botocore.exceptions import DataNotFoundError
from collections import OrderedDict

EGG = None
try:
    egg_path = os.path.dirname(os.path.dirname(__file__))
    EGG = zipfile.ZipFile(egg_path, 'r')
    EGG_DIRS = set([os.path.split(x)[0] for x in EGG.namelist() if '/' in x])
    EGG_API_PATHS = [x for x in EGG_DIRS if 'botocore/data/' in x]
    EGG_API_PATHS.extend([x for x in EGG_DIRS if 'boto3/data/' in x])
except:
    pass


class JSONFileLoader2(object):

    """Loader JSON files.

    This class can load the default format of models, which is a JSON file.

    """
    def exists(self, file_path: str):
        """Checks if the file exists.

        :type file_path: str
        :param file_path: The full path to the file to load without
            the '.json' extension.

        :return: True if file path exists, False otherwise.

        """
        # TODO fix? seems inconsistent with .format usage pattern. Also cast as str?
        return any(x.startswith("%s" % file_path) for x in EGG.namelist())


    def load_file(self, file_path: str):
        """Attempt to load the file path.

        :type file_path: str
        :param file_path: The full path to the file to load without
            the '.json' extension.

        :return: The loaded data if it exists, otherwise None.

        """
        # everything is inside the egg now, so load from there
        full_path = file_path + '.json'
        content = EGG.read(full_path).decode('UTF-8')

        return json.loads(content, object_pairs_hook=OrderedDict)


@botocore.loaders.instance_cache
def load_data(self, name):
    """Load data given a data path.
    This is a low level method that will search through the various
    search paths until it's able to load a value.  This is typically
    only needed to load *non* model files (such as _endpoints and
    _retry).  If you need to load model files, you should prefer
    ``load_service_model``.
    :type name: str
    :param name: The data path, i.e ``ec2/2015-03-01/service-2``.
    :return: The loaded data.  If no data could be found then
        a DataNotFoundError is raised.
    """
    # this is the hardcoded location for non-python things inside an egg
    locations = ['botocore/data/', 'boto3/data/']
    for possible_path in locations:
        file_path = possible_path + name
        if self.file_loader.exists(file_path):
            return self.file_loader.load_file(file_path)

    # We didn't find anything that matched on any path.
    raise DataNotFoundError(data_path=name)


@botocore.loaders.instance_cache
def list_available_services(self, type_name: str):
    """List all known services.
    :type type_name: str
    :param type_name: The type of the service (service-2,
        paginators-1, waiters-2, etc).  This is needed because
        the list of available services depends on the service
        type.  For example, the latest API version available for
        a resource-1.json file may not be the latest API version
        available for a services-2.json file.
    :return: A list of all services.  The list of services will
        be sorted.
    """

    # search for available services, pulled from the egg
    services = set()
    for api_path in EGG_API_PATHS:
        api_version = api_path.replace('botocore/data/', '').replace('boto3/data/', '').split('/')
        if len(api_version) == 2:
            full_path = os.path.join(api_path, type_name)
            if self.file_loader.exists(full_path):
                services.add(api_version[0])

    return sorted(services)


@botocore.loaders.instance_cache
def list_api_versions(self, service_name: str, type_name: str):
    """List all API versions available for a particular service type
        :type service_name: str
        :param service_name: The name of the service
        :type type_name: str
        :param type_name: The type name for the service (i.e service-2,
            paginators-1, etc.)
        :rtype: list
        :return: A list of API version strings in sorted order.

    """
    known_api_versions = set()
    for api_path in EGG_API_PATHS:
        if service_name in api_path.split('/'):
            api_version = api_path.replace('botocore/data/', '').replace('boto3/data/', '').split('/')
            if len(api_version) == 2:
                full_path = os.path.join(api_path, type_name)
                # Only add to the known_api_versions if the directory
                # contains a service-2, paginators-1, etc. file corresponding
                # to the type_name passed in.
                if self.file_loader.exists(full_path):
                    known_api_versions.add(api_version[1])
    if not known_api_versions:
        #raise Exception('service_name: {0}, type_name: {1}'.format(service_name, type_name))
        raise DataNotFoundError(data_path=service_name)
    return sorted(known_api_versions)


def patch_ca_certs():
    """
    Boto needs an actual file path for the cacerts.pem so we extract it from
    inside the egg. If it's been overridden by Boto 3's REQUESTS_CA_BUNDLE
    setting then just skip this patch.
    """

    # set the certificate to what requests bundles unless it's already overridden
    ca_bundle = os.environ.get('REQUESTS_CA_BUNDLE')
    if ca_bundle is None:
        # extract the cacerts.pem into a temp directory
        cert_dir = tempfile.mkdtemp(prefix='cacerts')
        cert_file = os.path.join(cert_dir, 'cacerts.pem')
        with open(cert_file, 'wb') as cf:
            cf.write(EGG.read('botocore/vendored/requests/cacert.pem'))
        os.environ['REQUESTS_CA_BUNDLE'] = cert_file
        atexit.register(clean_ca_certs, cert_dir)


def clean_ca_certs(cert_dir):
    """Delete the temporary cacerts and directory"""
    cert_file = os.path.join(cert_dir, 'cacerts.pem')
    os.remove(cert_file)
    os.rmdir(cert_dir)


# monkeypatch the original loaders to handle being inside of an eggsecutable
if EGG:
    patch_ca_certs()
    botocore.loaders.Loader.FILE_LOADER_CLASS = JSONFileLoader2
    botocore.loaders.Loader.load_data = load_data
    botocore.loaders.Loader.list_available_services = list_available_services
    botocore.loaders.Loader.list_api_versions = list_api_versions