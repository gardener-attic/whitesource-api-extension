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


from copy import copy
import datetime
import logging
import os
import shutil
import sys
import tempfile
import threading

import requests

import paths


logger = logging.getLogger(__name__)
# noqa disables flake8 linting for error E501 = line too long
ws_agent_url = 'https://github.com/whitesource/unified-agent-distribution/releases/latest/download/wss-unified-agent.jar'  # noqa: E501


def update_or_download_agent():
    if os.path.isfile(path=paths.wss_agent_path):
        modification_date = datetime.datetime.fromtimestamp(os.stat(paths.wss_agent_path).st_mtime)
        if modification_date < datetime.datetime.now() - datetime.timedelta(hours=24):
            logger.info('ws agent is older than 24 hours. Agent will be updated...')

            # updating ws agent in new thread
            threading.Thread(
                target=pull_latest_wss_agent,
                args=[paths.wss_agent_path],
                daemon=True,
            ).start()
        else:
            logger.info(
                f'wss agent is up to date and present on file system {paths.wss_agent_path=}.'
                ' Using this one...',
            )
    else:
        try:
            # download wss agent and block thread
            logger.info('wss agent not found on file system. Pulling it now...')
            pull_latest_wss_agent(paths.wss_agent_path)
        except requests.exceptions.HTTPError as e:
            logger.error(f'could not download ws agent {e.request=}. Keeping the current one...')


def get_wss_agent_hardlink(tmp_dir: str) -> str:
    update_or_download_agent()

    # at this point the wss_agent is present on the machine
    # creating a hard link so the current agent will not be garbage collected
    wss_agent_hardlink_path = os.path.join(tmp_dir, paths.wss_agent_name)
    os.link(src=paths.wss_agent_path, dst=wss_agent_hardlink_path)

    return wss_agent_hardlink_path


def pull_latest_wss_agent(wss_agent_path: str):
    # write res stream in tmp file because of multi threading
    tmp_file = None
    try:
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        with requests.get(url=ws_agent_url, stream=True) as res:

            res.raise_for_status()

            for chunk in res.iter_content(chunk_size=8192):
                tmp_file.write(chunk)

            logger.info('agent downloaded. Moving it to tmp dir...')

            shutil.move(src=tmp_file.name, dst=wss_agent_path)
        tmp_file.close()

        logger.info('ws agent pulled successfully.')

    except Exception:
        logger.error('an error occured while pulling ws agent')
        os.unlink(tmp_file.name)
        raise RuntimeError('error pulling wss agent')


def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


class CCFormatter(logging.Formatter):
    level_colors = {
        logging.DEBUG: lambda level_name:
        f'{Bcolors.BOLD}{Bcolors.BLUE}{level_name}{Bcolors.RESET_ALL}',
        logging.INFO: lambda level_name:
        f'{Bcolors.BOLD}{Bcolors.GREEN}{level_name}{Bcolors.RESET_ALL}',
        logging.WARNING: lambda level_name:
        f'{Bcolors.BOLD}{Bcolors.YELLOW}{level_name}{Bcolors.RESET_ALL}',
        logging.ERROR: lambda level_name:
        f'{Bcolors.BOLD}{Bcolors.RED}{level_name}{Bcolors.RESET_ALL}',
    }

    def color_level_name(self, level_name, level_number):
        def default(level_name):
            return str(level_name)

        func = self.level_colors.get(level_number, default)
        return func(level_name)

    def formatMessage(self, record):
        record_copy = copy(record)
        levelname = record_copy.levelname
        if sys.stdout.isatty():
            levelname = self.color_level_name(levelname, record_copy.levelno)
            if "color_message" in record_copy.__dict__:
                record_copy.msg = record_copy.__dict__["color_message"]
                record_copy.__dict__["message"] = record_copy.getMessage()
        record_copy.__dict__["levelprefix"] = levelname
        return super().formatMessage(record_copy)


class Bcolors:
    RESET_ALL = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'


def configure_default_logging(
    stdout_level=None,
    force=True,
    tid=True,
):
    if not stdout_level:
        stdout_level = logging.INFO

    # make sure to have a clean root logger (in case setup is called multiple times)
    if force:
        for h in logging.root.handlers:
            logging.root.removeHandler(h)
            h.close()

    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setLevel(stdout_level)
    sh.setFormatter(CCFormatter(fmt=get_default_fmt_string(tid=tid)))
    logging.root.addHandler(hdlr=sh)
    logging.root.setLevel(level=stdout_level)


def get_default_fmt_string(tid: bool):
    return f'%(asctime)s [%(levelprefix)s] {"TID:%(thread)d " if tid else ""}%(name)s: %(message)s'
