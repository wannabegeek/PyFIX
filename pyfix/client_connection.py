import logging
import socket
from pyfix.session import FIXSession
from pyfix.connection import FIXEndPoint, ConnectionState, MessageDirection, FIXConnectionHandler
from pyfix.event import TimerEventRegistration

class FIXClientConnectionHandler(FIXConnectionHandler):
    def __init__(self, engine, protocol, targetCompId, senderCompId, sock=None, addr=None, observer=None, targetSubId = None, senderSubId = None, heartbeatTimeout = 30):
        FIXConnectionHandler.__init__(self, engine, protocol, sock, addr, observer)

        self.targetCompId = targetCompId
        self.senderCompId = senderCompId
        self.targetSubId = targetSubId
        self.senderSubId = senderSubId
        self.heartbeatPeriod = float(heartbeatTimeout)

        # we need to send a login request.
        self.session = FIXSession(self.sessionKeyFromCompIds(self.targetCompId, self.senderCompId), self.senderCompId, self.targetCompId)
        self.sendMsg(protocol.messages.Messages.logon())

    def processMessage(self, decodedMsg):
        protocol = self.codec.protocol

        # validate the seq number
        recvSeqNo = decodedMsg[protocol.fixtags.MsgSeqNum]
        (seqNoState, lastKnownSeqNo) = self.session.validateRecvSeqNo(recvSeqNo)

        self._notifyMessageObservers(decodedMsg, MessageDirection.INBOUND)

        if decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.LOGON:
            self.connectionState = ConnectionState.LOGGED_IN
            self.registerLoggedIn()
        elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.LOGOUT:
            self.connectionState = ConnectionState.LOGGED_OUT
            self.registerLoggedOut()
            self.handle_close()
        elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.TESTREQUEST:
            self.sendMsg(protocol.messages.Messages.heartbeat())
        elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.RESENDREQUEST:
            self.sendMsg(protocol.messages.Messages.sequence_reset(decodedMsg, True))
        elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.SEQUENCERESET:
            newSeqNo = decodedMsg[protocol.fixtags.NewSeqNo]
            recvSeqNo = newSeqNo

        if seqNoState is False:
            # We should send a resend request
            self.sendMsg(protocol.messages.Messages.resend_request(lastKnownSeqNo, recvSeqNo))
        else:
            self.session.setRecvSeqNo(recvSeqNo)



class FIXClient(FIXEndPoint):
    def __init__(self, engine, protocol, targetCompId, senderCompId, targetSubId = None, senderSubId = None, heartbeatTimeout = 30):
        self.targetCompId = targetCompId
        self.senderCompId = senderCompId
        self.targetSubId = targetSubId
        self.senderSubId = senderSubId
        self.heartbeatTimeout = heartbeatTimeout

        FIXEndPoint.__init__(self, engine, protocol)

    def tryConnecting(self, type, closure):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            logging.debug("Attempting Connection to " + self.host + ":" + str(self.port))
            self.socket.connect((self.host, self.port))
            if self.connectionRetryTimer is not None:
                self.engine.eventManager.unregisterHandler(self.connectionRetryTimer)
            self.connected()
        except socket.error as why:
            logging.error("Connection failed, trying again in 5s")
            if self.connectionRetryTimer is None:
                self.connectionRetryTimer = TimerEventRegistration(self.tryConnecting, 5.0)
                self.engine.eventManager.registerHandler(self.connectionRetryTimer)

    def start(self, host, port):
        self.host = host
        self.port = port
        self.connections = []
        self.connectionRetryTimer = None

        self.tryConnecting(None, None)

    def connected(self):
        self.addr = (self.host, self.port)
        logging.info("Connected to %s" % repr(self.addr))
        connection = FIXClientConnectionHandler(self.engine, self.protocol, self.targetCompId, self.senderCompId, self.socket, self.addr, self, self.targetSubId, self.senderSubId, self.heartbeatTimeout)
        self.connections.append(connection)
        for handler in filter(lambda x: x[1] == ConnectionState.CONNECTED, self.connectionHandlers):
                handler[0](connection)

    def notifyDisconnect(self, connection):
        FIXEndPoint.notifyDisconnect(self, connection)
        self.tryConnecting(None, None)

    def stop(self):
        logging.info("Stopping client connections")
        for connection in self.connections:
            connection.disconnect()
        self.socket.close()

