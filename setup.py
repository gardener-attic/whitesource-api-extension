# Copyright (c) 2021 SAP SE or an SAP affiliate company.
# All rights reserved.
# This file is licensed under the Apache Software License,
# v. 2 except as noted otherwise in the LICENSE file.
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import setuptools
import os

own_dir = os.path.abspath(os.path.dirname(__file__))


def requirements():
    with open(os.path.join(own_dir, 'requirements.txt')) as f:
        for line in f.readlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            yield line


def modules():
    return [
    ]


def version():
    with open(os.path.join(own_dir, 'VERSION')) as f:
        return f.read().strip()


setuptools.setup(
    name='whitesource_api_extension',
    version=version(),
    description='backend for whitesource-api-extension',
    python_requires='>=3.8.*',
    py_modules=modules(),
    packages=['whitesource_backend'],
    package_data={
        'ci':['version'],
    },
    entry_points={
    },
)
