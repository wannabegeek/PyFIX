import logging
import socket
from pyfix.journaler import DuplicateSeqNoError
from pyfix.message import FIXMessage
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
        self.session = self.engine.getOrCreateSessionFromCompIds(self.targetCompId, self.senderCompId)
        if self.session is None:
            raise RuntimeError("Failed to create client session")

        self.sendMsg(protocol.messages.Messages.logon())

    def handleSessionMessage(self, msg):
        protocol = self.codec.protocol
        responses = []

        recvSeqNo = msg[protocol.fixtags.MsgSeqNum]

        msgType = msg[protocol.fixtags.MsgType]
        targetCompId = msg[protocol.fixtags.TargetCompID]
        senderCompId = msg[protocol.fixtags.SenderCompID]

        if msgType == protocol.msgtype.LOGON:
            if self.connectionState == ConnectionState.LOGGED_IN:
                logging.warning("Client session already logged in - ignoring login request")
            else:
                try:
                    self.connectionState = ConnectionState.LOGGED_IN
                    self.heartbeatPeriod = float(msg[protocol.fixtags.HeartBtInt])
                    self.registerLoggedIn()
                except DuplicateSeqNoError:
                    logging.error("Failed to process login request with duplicate seq no")
                    self.disconnect()
                    return
        elif self.connectionState == ConnectionState.LOGGED_IN:
            # compids are reversed here
            if not self.session.validateCompIds(senderCompId, targetCompId):
                logging.error("Received message with unexpected comp ids")
                self.disconnect()
                return

            if msgType == protocol.msgtype.LOGOUT:
                self.connectionState = ConnectionState.LOGGED_OUT
                self.registerLoggedOut()
                self.handle_close()
            elif msgType == protocol.msgtype.TESTREQUEST:
                responses.append(protocol.messages.Messages.heartbeat())
            elif msgType == protocol.msgtype.RESENDREQUEST:
                responses.extend(self._handleResendRequest(msg))
            elif msgType == protocol.msgtype.SEQUENCERESET:
                # we can treat GapFill and SequenceReset in the same way
                # in both cases we will just reset the seq number to the
                # NewSeqNo received in the message
                newSeqNo = msg[protocol.fixtags.NewSeqNo]
                if msg[protocol.fixtags.GapFillFlag] == "Y":
                    logging.info("Received SequenceReset(GapFill) filling gap from %s to %s" % (recvSeqNo, newSeqNo))
                self.session.setRecvSeqNo(int(newSeqNo) - 1)
                recvSeqNo = newSeqNo
        else:
            logging.warning("Can't process message, counterparty is not logged in")

        return (recvSeqNo, responses)



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
                self.connectionRetryTimer = None
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

