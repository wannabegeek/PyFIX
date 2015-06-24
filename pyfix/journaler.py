import logging
import sqlite3
import pickle
from pyfix.connection import MessageDirection

class DuplicateSeqNoError(Exception):
    pass

class Journaler(object):
    def __init__(self, filename = None):
        if filename is None:
            self.conn = sqlite3.connect(":memory:")
        else:
            self.conn = sqlite3.connect(filename)

        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS message("
                               "seqNo INTEGER NOT NULL,"
                               "session TEXT NOT NULL,"
                               "direction INTEGER NOT NULL,"
                               "msg TEXT,"
                               "PRIMARY KEY (seqNo, session, direction)) WITHOUT ROWID")

        self.cursor.execute("CREATE TABLE IF NOT EXISTS session("
                               "targetCompId TEXT NOT NULL,"
                               "senderCompId TEXT NOT NULL,"
                               "outboundSeqNo INTEGER DEFAULT 0,"
                               "inboundSeqNo INTEGER DEFAULT 0,"
                               "PRIMARY KEY (targetCompId, senderCompId))")

    def createSession(self, targetCompId, senderCompId):
        pass

    def persistMsg(self, msg, session, direction):
        msgStr = pickle.dumps(msg)
        seqNo = session.sndSeqNum if direction == MessageDirection.OUTBOUND else session.rcvSeqNum
        try:
            self.cursor.execute("INSERT INTO message VALUES(?, ?, ?, ?)", (seqNo, session.key, direction.value, msgStr))
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise DuplicateSeqNoError("%s is a duplicate" % (seqNo, ))

    def recoverMsg(self, session, direction, seqNo):
        try:
            msgs = self.recoverMsgs(session, direction, seqNo, seqNo)
            return msgs[0]
        except IndexError:
            return None

    def recoverMsgs(self, session, direction, startSeqNo, endSeqNo):
        self.cursor.execute("SELECT msg FROM message WHERE session = ? AND direction = ? AND seqNo >= ? AND seqNo <= ?", (session.key, direction.value, startSeqNo, endSeqNo))
        msgs = []
        for msg in self.cursor:
            msgs.append(pickle.loads(msg[0]))
        return msgs