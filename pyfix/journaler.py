import sqlite3
import pickle
from pyfix.message import MessageDirection
from pyfix.session import FIXSession


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
                               "PRIMARY KEY (seqNo, session, direction))")

        self.cursor.execute("CREATE TABLE IF NOT EXISTS session("
                               "sessionId INTEGER PRIMARY KEY AUTOINCREMENT,"
                               "targetCompId TEXT NOT NULL,"
                               "senderCompId TEXT NOT NULL,"
                               "outboundSeqNo INTEGER DEFAULT 0,"
                               "inboundSeqNo INTEGER DEFAULT 0,"
                               "UNIQUE (targetCompId, senderCompId))")

    def sessions(self):
        sessions = []
        self.cursor.execute("SELECT sessionId, targetCompId, senderCompId, outboundSeqNo, inboundSeqNo FROM session")
        for sessionInfo in self.cursor:
            session = FIXSession(sessionInfo[0], sessionInfo[1], sessionInfo[2])
            session.sndSeqNum = sessionInfo[3]
            session.nextExpectedMsgSeqNum = sessionInfo[4] + 1
            sessions.append(session)

        return sessions

    def createSession(self, targetCompId, senderCompId):
        session = None
        try:
            self.cursor.execute("INSERT INTO session(targetCompId, senderCompId) VALUES(?, ?)", (targetCompId, senderCompId))
            sessionId = self.cursor.lastrowid
            self.conn.commit()
            session = FIXSession(sessionId, targetCompId, senderCompId)
        except sqlite3.IntegrityError:
            raise RuntimeError("Session already exists for TargetCompId: %s SenderCompId: %s" % (targetCompId, senderCompId))

        return session

    def persistMsg(self, msg, session, direction):
        msgStr = pickle.dumps(msg)
        seqNo = msg["34"]
        try:
            self.cursor.execute("INSERT INTO message VALUES(?, ?, ?, ?)", (seqNo, session.key, direction.value, msgStr))
            if direction == MessageDirection.OUTBOUND:
                self.cursor.execute("UPDATE session SET outboundSeqNo=?", (seqNo,))
            elif direction == MessageDirection.INBOUND:
                self.cursor.execute("UPDATE session SET inboundSeqNo=?", (seqNo,))

            self.conn.commit()
        except sqlite3.IntegrityError as e:
            raise DuplicateSeqNoError("%s is a duplicate" % (seqNo, ))

    def recoverMsg(self, session, direction, seqNo):
        try:
            msgs = self.recoverMsgs(session, direction, seqNo, seqNo)
            return msgs[0]
        except IndexError:
            return None

    def recoverMsgs(self, session, direction, startSeqNo, endSeqNo):
        self.cursor.execute("SELECT msg FROM message WHERE session = ? AND direction = ? AND seqNo >= ? AND seqNo <= ? ORDER BY seqNo", (session.key, direction.value, startSeqNo, endSeqNo))
        msgs = []
        for msg in self.cursor:
            msgs.append(pickle.loads(msg[0]))
        return msgs

    def getAllMsgs(self, sessions = [], direction = None):
        sql = "SELECT seqNo, msg, direction, session FROM message"
        clauses = []
        args = []
        if sessions is not None and len(sessions) != 0:
            clauses.append("session in (" + ','.join('?'*len(sessions)) + ")")
            args.extend(sessions)
        if direction is not None:
            clauses.append("direction = ?")
            args.append(direction.value)

        if clauses:
            sql = sql + " WHERE " + " AND ".join(clauses)

        sql = sql + " ORDER BY rowid"

        self.cursor.execute(sql, tuple(args))
        msgs = []
        for msg in self.cursor:
            msgs.append((msg[0], pickle.loads(msg[1]), msg[2], msg[3]))

        return msgs