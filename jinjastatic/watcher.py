import sys
import os
import time
import threading
import logging
import fnmatch

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileDeletedEvent

__all__ = [
    'setup_watch',
]

logger = logging.getLogger('jinjastatic')


class EventHandler(FileSystemEventHandler):
    def __init__(self, base_path, callback, excludes=[]):
        self.base_path = os.path.abspath(base_path)
        self.modified_files = set()
        self.promise = None
        self.callback = callback
        self.excludes = excludes

    def on_any_event(self, event):
        if event.is_directory:
            return
        path = event.src_path
        path = path[len(self.base_path):].lstrip('/')
        for exclude in self.excludes:
            if fnmatch.fnmatch(path, exclude):
                return

        logger.debug("Caught event: {0}".format(event))

        if isinstance(event, FileDeletedEvent):
            if path in self.modified_files:
                self.modified_files.remove(path)
            return

        self.modified_files.add(path)
        if not self.promise or self.promise.cancel():
            self.promise = DelayedPromise(self.run_combined, 0.1)

    def run_combined(self):
        f = self.modified_files
        self.modified_files = set()
        logger.debug("Changed files: {0}".format(','.join(f)))
        self.callback(list(f))


def setup_watch(src_dir, callback, excludes=[]):
    observer = Observer()
    observer.schedule(EventHandler(src_dir, callback, excludes), path=src_dir, recursive=True)
    observer.start()
    logger.info("Set up watching on {0} recursively. (CTRL-C to stop)".format(src_dir))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


class DelayedPromise(threading.Thread):
    def __init__(self, callback, delay_time=0.1):
        threading.Thread.__init__(self)
        self.cancelled = False
        self.running = threading.Lock()
        self.delay_time = delay_time
        self.stopped = False
        self.callback = callback
        self.setDaemon(True)
        self.start()


    def cancel(self):
        if self.running.acquire(False) or self.stopped:
            self.cancelled = True
            self.running.release()
            return True
        return False

    def run(self):
        time.sleep(self.delay_time)
        self.running.acquire()
        if self.cancelled:
            return
        self.stopped = True
        try:
            self.callback()
        finally:
            self.running.release()
