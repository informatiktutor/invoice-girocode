import os
import signal
import sys
import time
from datetime import datetime
from queue import Queue
from threading import Thread, Timer

from dotenv import load_dotenv
from watchdog.events import RegexMatchingEventHandler
from watchdog.observers import Observer

from girocode.insert import insert_girocode
from girocode.util import ENV, fail


"""
Documentation:
https://thepythoncorner.com/posts/2019-01-13-how-to-create-a-watchdog-in-python-to-look-for-filesystem-changes/
https://camcairns.github.io/python/2017/09/06/python_watchdog_jobs_queue.html
"""

# NOTE Make sure to restart the service on new year,
# when watching changes in folders where the year is part of the path.


load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))


WATCH_WRITE_TIMEOUT_MILLIS = 200
PROGRAM_LOOP_DELAY_MILLIS = 1000
QUEUE_LOOP_DELAY_MILLIS = 100

PDF_EXT = '.pdf'
XML_EXT = '.xml'


class AfterWriteWatchdog(RegexMatchingEventHandler):
    def __init__(self, queue, regexes):
        RegexMatchingEventHandler.__init__(
            self,
            regexes=regexes,
            ignore_directories=True,
            case_sensitive=True
        )
        self.queue = queue
        self._queue_item = None
        self._timer = Timer(0, lambda: None)

    def on_created(self, event):
        self._timer.cancel()

    def on_modified(self, event):
        self._timer.cancel()
        self._queue_item = event.src_path
        self._timer = Timer(WATCH_WRITE_TIMEOUT_MILLIS / 1000, self._fire)
        self._timer.start()
    
    def _fire(self):
        self.queue.put(self._queue_item)


class OnMovedWatchdog(RegexMatchingEventHandler):
    def __init__(self, queue, regexes):
        RegexMatchingEventHandler.__init__(
            self,
            regexes=regexes,
            ignore_directories=True,
            case_sensitive=True
        )
        self.queue = queue

    def on_moved(self, event):
        self.queue.put(event.dest_path)


def process_watch_queue(queue):
    xml, pdf = None, None
    while True:
        if queue.empty():
            time.sleep(QUEUE_LOOP_DELAY_MILLIS / 1000)
            continue
        path = queue.get()
        _, extension = os.path.splitext(path)
        if extension == PDF_EXT:
            if pdf is not None:
                fail('PDF already present')
            pdf = path
        elif extension == XML_EXT:
            if xml is not None:
                fail('XML already present')
            xml = path
        else:
            fail('Invalid file extension')
        if pdf is not None and xml is not None:
            process_xml_pdf(xml, pdf)
            xml = pdf = None


def process_xml_pdf(xml_path, pdf_path):
    filename = os.path.basename(pdf_path)
    result_path = os.path.join(ENV('RESULT_PDF_DIRECTORY'), filename)
    print(f'GIROCODE: {pdf_path} -> {result_path}')
    insert_girocode(
        input_pdf=pdf_path,
        input_xml=xml_path,
        output_pdf_dest=result_path
    )
    sys.stdout.flush()


def main():
    os.makedirs(ENV('RESULT_PDF_DIRECTORY'), exist_ok=True)
    os.makedirs(os.path.dirname(ENV('ERROR_LOG_PATH')), exist_ok=True)

    watchdog_queue = Queue()

    worker = Thread(target=process_watch_queue, args=(watchdog_queue,))
    worker.daemon = True
    worker.start()

    xml_event_handler = AfterWriteWatchdog(
        queue=watchdog_queue,
        regexes=[ENV('WATCH_XML_REGEX')]
    )
    pdf_event_handler = OnMovedWatchdog(
        queue=watchdog_queue,
        regexes=[ENV('WATCH_PDF_REGEX')]
    )

    date = datetime.now()
    xml_directory = ENV('WATCH_XML_DIRECTORY')
    pdf_directory = ENV('WATCH_PDF_DIRECTORY').format(date=date)

    observer = Observer()
    observer.schedule(xml_event_handler, xml_directory, recursive=False)
    observer.schedule(pdf_event_handler, pdf_directory, recursive=False)
    observer.start()

    print(f'OBSERVING PDF {pdf_directory}')
    print(f'OBSERVING XML {xml_directory}')

    try:
        while True:
            time.sleep(PROGRAM_LOOP_DELAY_MILLIS / 1000)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()

    """insert_girocode(
        input_pdf='../data/example-invoice.pdf',
        input_xml='../data/example-zugferd.xml',
        output_pdf_dest='../build/output.pdf'
    )"""


if __name__ == '__main__':
    main()
