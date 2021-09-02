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


import argparse
import logging
import threading

import falcon.asgi
import uvicorn

import component
import util


util.configure_default_logging(tid=False)
logger = logging.getLogger(__name__)


def _logging_config(stdout_level=logging.INFO):
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'loggers': {
            'uvicorn': {'level': stdout_level},
            'uvicorn.error': {'level': stdout_level},
            'uvicorn.access': {'level': stdout_level},
        },
    }


def create():
    logger.info('initializing falcon')
    app = falcon.asgi.App()
    app.add_route('/component', component.Component())

    threading.Thread(
        target=util.update_or_download_agent,
        daemon=True,
    ).start()

    return app


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', action='store', dest='port', type=int)
    parser.add_argument('--worker', action='store', dest='worker', type=int, default=4)
    args = parser.parse_args()
    uvicorn.run(
        'app:create',
        host="0.0.0.0",
        port=args.port,
        log_level='info',
        log_config=_logging_config(),
        workers=args.worker,
    )


if __name__ == '__main__':
    run()
