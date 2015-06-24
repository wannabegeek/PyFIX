from pyfix.event import EventManager


class FIXEngine(object):
    def __init__(self):
        self.eventManager = EventManager()
        self.journaller = None


    def validateSession(self, session):
        return True