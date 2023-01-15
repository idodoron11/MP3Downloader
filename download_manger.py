import logging
import os.path
import time
import traceback
from collections import deque

import requests

from singleton import Singleton

logger = logging.getLogger("mp3downloader")

class DownloadRecord:
    def __init__(self, request=None, save_location=None, on_download_success=None, on_download_failure=None):
        self.request = request
        self.on_download_success = on_download_success
        self.on_download_failure = on_download_failure
        self.save_location = save_location

    def download(self):
        DownloadManager().enqueue_download(self)

class Request:
    def __init__(self, method=None, url=None, headers=None, body=None):
        self.method = method
        self.url = url
        self.headers = headers
        self.body = body

    def __str__(self):
        return str(self.__dict__)

class DownloadManager(metaclass=Singleton):
    def __init__(self):
        self._queue = deque()
        self._active = False

    def enqueue_download(self, download_record):
        logger.debug(f"Adding {download_record} to download manager queue")
        self._queue.append(download_record)

    def _download(self, download_record):
        logger.debug(f"Start downloading {download_record}")
        request = download_record.request
        with requests.request(request.method, headers=request.headers, url=request.url, data=request.body) as r:
            parent_dir = os.path.dirname(download_record.save_location)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir)
            try:
                r.raise_for_status()
                with open(download_record.save_location, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            except requests.exceptions.HTTPError as e:
                logger.error("Download failure")
                logger.debug(traceback.format_exc())
        logger.debug(f"Finished downloading {download_record}")

    def _process_queue(self):
        logger.debug("Processing download queue")
        while self._queue:
            self._download(self._queue.popleft())
    def run(self):
        self._active = True
        while self._active:
            if self._queue:
                self._process_queue()
            time.sleep(1)

    def stop(self):
        self._active = False

