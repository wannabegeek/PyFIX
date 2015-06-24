import logging
from pyfix.event import EventManager
from pyfix.journaler import Journaler
from pyfix.session import FIXSession


class FIXEngine(object):
    def __init__(self, journalfile = None):
        self.eventManager = EventManager()
        self.journaller = Journaler(journalfile)
        self.sessions = {}

        # TODO: we should load all sessions from the journal and add to our list

    def validateSession(self, targetCompId, senderCompId):
        # this make any session we receive valid
        return True

    def addSession(self, session):
        if session.key not in self.sessions:
            self.sessions[session.key] = session
        else:
            raise RuntimeError("Failed to add session with duplicate key")

    def getSession(self, identifier):
        try:
            return self.sessions[identifier]
        except KeyError:
            return None

    def findSessionByCompIds(self, targetCompId, senderCompId):
        sessionKey = FIXSession.generateKeysFromCompIds(targetCompId, senderCompId)
        try:
            return self.sessions[sessionKey]
        except KeyError:
            return None

    def getOrCreateSessionFromCompIds(self, targetCompId, senderCompId):
        session = self.findSessionByCompIds(targetCompId, senderCompId)
        if session is None:
            if self.validateSession(targetCompId, senderCompId):
                session = FIXSession(targetCompId, senderCompId)
                self.addSession(session)

        return session
