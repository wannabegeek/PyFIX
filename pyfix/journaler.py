import sqlite3
import pickle

class Journaler(object):
    def __init__(self, filename = None):
        if filename is None:
            self.conn = sqlite3.connect(":memory:")
        else:
            self.conn = sqlite3.connect(filename)

        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE msgStore("
                               "seqNo INTEGER NOT NULL,"
                               "session TEXT NOT NULL,"
                               "direction INTEGER NOT NULL,"
                               "msg TEXT,"
                               "PRIMARY KEY (seqNo, session, direction)) WITHOUT ROWID")

    def persistMsg(self, msg, session, direction):
        seqNo = msg.getField(session.codec.protocol.fixtags.MsgSeqNum)
        msgStr = pickle.dumps(msg)
        self.cursor.execute("INSERT INTO msgStore VALUES(?, ?, ?, ?)", (seqNo, session.key, direction.value, msgStr))
        pass

    def recoverMsg(self, session, direction, seqNo):
        try:
            msgs = self.recoverMsgs(session, direction, seqNo, seqNo)
            return msgs[0]
        except IndexError:
            return None

    def recoverMsgs(self, session, direction, startSeqNo, endSeqNo):
        self.cursor.execute("SELECT msg FROM msgStore WHERE session = ? AND direction = ? AND seqNo >= ? AND seqNo <= ?", (session.key, direction.value, startSeqNo, endSeqNo))
        msgs = []
        for msg in self.cursor:
            msgs.append(pickle.loads(msg[0]))
        return msgs