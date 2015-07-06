from pyfix.event import EventManager
from pyfix.journaler import Journaler

class FIXEngine(object):
    def __init__(self, journalfile = None):
        self.eventManager = EventManager()
        self.journaller = Journaler(journalfile)
        self.sessions = {}

        # We load all sessions from the journal and add to our list
        for session in self.journaller.sessions():
            self.sessions[session.key] = session

    def validateSession(self, targetCompId, senderCompId):
        # this make any session we receive valid
        return True

    def shouldResendMessage(self, session, msg):
        # we should resend all application messages
        return True

    def createSession(self, targetCompId, senderCompId):
        if self.findSessionByCompIds(targetCompId, senderCompId) is None:
            session = self.journaller.createSession(targetCompId, senderCompId)
            self.sessions[session.key] = session
        else:
            raise RuntimeError("Failed to add session with duplicate key")
        return session

    def getSession(self, identifier):
        try:
            return self.sessions[identifier]
        except KeyError:
            return None

    def findSessionByCompIds(self, targetCompId, senderCompId):
        sessions = [x for x in self.sessions.values() if x.targetCompId == targetCompId and x.senderCompId == senderCompId]
        if sessions is not None and len(sessions) != 0:
            return sessions[0]
        return None

    def getOrCreateSessionFromCompIds(self, targetCompId, senderCompId):
        session = self.findSessionByCompIds(targetCompId, senderCompId)
        if session is None:
            if self.validateSession(targetCompId, senderCompId):
                session = self.createSession(targetCompId, senderCompId)

        return session
