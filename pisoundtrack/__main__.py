""" _main_ To be properly executed from crontab --> python -m pisoundtrack"""
from log_mgr import Logger
from .soundtrack import Soundtrack

logger = Logger('pisoundtrack', log_file_name='pisoundtrack')

soundtrack = Soundtrack()
soundtrack.microphone_listen()
