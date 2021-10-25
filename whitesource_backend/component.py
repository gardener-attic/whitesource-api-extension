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


import dataclasses
import json
import logging
import os
import subprocess
import tarfile
import tempfile

import dacite
import falcon.asgi
from whitesource_common import protocol

import model
import paths
import util


logger = logging.getLogger(__name__)


class Component:

    async def on_websocket(self, req: falcon.Request, ws: falcon.asgi.WebSocket):

        try:
            await ws.accept()

            logger.info('receiving metadata...')
            try:
                metadata = dacite.from_dict(
                    data_class=protocol.WhiteSourceApiExtensionWebsocketMetadata,
                    data=json.loads(await ws.receive_text()),
                )

                logger.info('receiving whitesource config...')
                ws_config = dacite.from_dict(
                    data_class=protocol.WhiteSourceApiExtensionWebsocketWSConfig,
                    data=json.loads(await ws.receive_text()),
                )

            except (json.decoder.JSONDecodeError, dacite.exceptions.MissingValueError):
                await ws.close(
                    code=protocol.WhiteSourceApiExtensionStatusCodeReasons.CONTRACT_VIOLATION.value
                )
                return

            plogger = logging.getLogger(ws_config.projectName)

            if metadata.chunkSize > metadata.length:
                await ws.close(
                    code=protocol.WhiteSourceApiExtensionStatusCodeReasons.CHUNK_SIZE_TOO_BIG.value
                )
                return

            with tempfile.TemporaryDirectory() as tmp_dir:
                plogger.info('transfer start')
                with tempfile.NamedTemporaryFile() as tar_file:
                    received = 0
                    while received < metadata.length:
                        chunk = await ws.receive_data()
                        tar_file.write(chunk)
                        plogger.info(
                            f'{util.sizeof_fmt(received)}/{util.sizeof_fmt(metadata.length)} '
                            f'({received}/{metadata.length})'
                        )
                        received += len(chunk)
                    tar_file.seek(0)
                    plogger.info(
                        f'{util.sizeof_fmt(received)}/{util.sizeof_fmt(metadata.length)} '
                        f'({received}/{metadata.length})'
                    )
                    plogger.info('transfer done')
                    try:

                        # extract top tar
                        with tarfile.open(fileobj=tar_file, mode='r|*', bufsize=1024) as f:
                            while tar_info := f.next():
                                f.extract(tar_info, path=tmp_dir, set_attrs=False)

                        # extract each oci layer in seperate tar, rm .tar afterwards
                        for file in os.listdir(tmp_dir):
                            if file.endswith('.tar'):
                                with tarfile.open(
                                        os.path.join(tmp_dir, file),
                                        mode='r|*', bufsize=1024,
                                ) as f:
                                    try:
                                        while tar_info := f.next():
                                            f.extract(
                                                tar_info,
                                                path=os.path.join(tmp_dir, file.replace('.tar', '')),
                                                set_attrs=False,
                                            )
                                    except (tarfile.StreamError, KeyError) as e:
                                        if isinstance(e, tarfile.StreamError):
                                            # https://bugs.python.org/issue12800
                                            plogger.warn('skipping duplicate (probably symlink)')
                                        elif isinstance(e, KeyError):
                                            plogger.warn('linkname not found, skipping')
                                        else:
                                            raise e
                                os.remove(os.path.join(tmp_dir, file))

                    except (
                            tarfile.ReadError,
                            UnicodeDecodeError,
                            tarfile.InvalidHeaderError,
                    ):
                        await ws.close(
                            code=protocol.WhiteSourceApiExtensionStatusCodeReasons
                                .BINARY_CORRUPTED.value
                        )
                        return

                plogger.info('scan start')
                wss_agent_hardlink_path = util.get_wss_agent_hardlink(tmp_dir=tmp_dir)
                result = _scan_component(
                    wss_agent_dir=tmp_dir,
                    component_path=tmp_dir,
                    ws_config=ws_config,
                    plogger=plogger,
                )

                os.unlink(wss_agent_hardlink_path)

                if result.returncode == 0:
                    agent_log_str = (result.stdout.decode('utf-8') or '')
                else:
                    agent_log_str = (result.stderr.decode('utf-8') or '') + \
                    (result.stdout.decode('utf-8') or '')

                res = _build_scan_result_response(
                    successful=True if result.returncode == 0 else False,
                    message=agent_log_str,
                )

                await ws.send_text(str(result.returncode))
                await ws.send_text(json.dumps(dataclasses.asdict(res)))

        except falcon.WebSocketDisconnected:
            return


def _build_scan_result_response(
    successful: bool,
    message: str,
):
    res = {
        'successful': successful,
        'message': message
    }
    res = dacite.from_dict(
        data_class=model.ScanResult,
        data=res
    )
    return res


def generate_config(
    wss_agent_dir: str,
    java_path: str,
):
    logger.info('generating config')
    wss_agent_path = os.path.join(wss_agent_dir, paths.wss_agent_name)
    args = [
        java_path,
        '-jar', wss_agent_path,
        '-detect',
    ]

    subprocess.run(
        args,
        cwd=wss_agent_dir,
        capture_output=False,
    )


def _add_configuration(
    file,
    ws_config,
):
    for e in [
        f'requesterEmail={ws_config.requesterEmail}',
        'go.collectDependenciesAtRuntime=true',
        'failErrorLevel=ALL',
        'fileSystemScan=true',
        'resolveAllDependencies=true',
        'python.installVirtualEnv=true'
    ]:
        file.write(f'\n{e}')


def _scan_component(
    wss_agent_dir: str,
    component_path: str,
    ws_config: protocol.WhiteSourceApiExtensionWebsocketWSConfig,
    plogger: logging.Logger,
) -> subprocess.CompletedProcess:

    generate_config(
        wss_agent_dir=wss_agent_dir,
        java_path=paths.java_path,
    )

    with open(os.path.join(wss_agent_dir, 'wss-generated-file.config'), 'a') as config_file:
        _add_configuration(
            file=config_file,
            ws_config=ws_config,
        )
        if ws_config.extraWsConfig:
            for key, value in ws_config.extraWsConfig.items():
                config_file.write(f'\n{key}={value}')

        config_file.seek(0)

    plogger.info('agent start')
    result = run_whitesource_scan(
        wss_agent_dir=wss_agent_dir,
        component_path=component_path,
        config_path=os.path.join(wss_agent_dir, 'wss-generated-file.config'),
        java_path=paths.java_path,
        ws_config=ws_config,
    )
    return result


def run_whitesource_scan(
    wss_agent_dir: str,
    component_path: str,
    java_path: str,
    ws_config: protocol.WhiteSourceApiExtensionWebsocketWSConfig,
    config_path: str,
) -> subprocess.CompletedProcess:
    wss_agent_path = os.path.join(wss_agent_dir, paths.wss_agent_name)
    args = [
        java_path,
        '-Xms256m',
        '-Xmx512m',
        '-jar', wss_agent_path,
        '-c', config_path,
        '-d', component_path,
        '-apiKey', ws_config.apiKey,
        '-userKey', ws_config.userKey,
        '-wss.url', ws_config.wssUrl,
        '-productToken', ws_config.productToken,
        '-project', ws_config.projectName,
        # if project version is added each new version will create a new project in product
        # this will overload the product with projects this no project version
        # '-projectVersion', ws_config.projectVersion,
    ]

    return subprocess.run(
        args,
        cwd=wss_agent_dir,
        capture_output=True,
    )
