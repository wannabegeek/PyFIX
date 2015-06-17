import logging
import socket
from pyfix.session import FIXSession
from pyfix.connection import FIXEndPoint, ConnectionState, MessageDirection, FIXConnectionHandler
from pyfix.event import FileDescriptorEventRegistration, EventType

connectedSessions = {}

class FIXServerConnectionHandler(FIXConnectionHandler):
    def __init__(self, eventMgr, protocol, sock=None, addr=None, observer=None):
        FIXConnectionHandler.__init__(self, eventMgr, protocol, sock, addr, observer)

    def processMessage(self, decodedMsg):
        protocol = self.codec.protocol
        # Find out session if it exists
        if self.session is None:
            if decodedMsg[protocol.fixtags.SenderCompID] not in connectedSessions:
                self.session = FIXSession(decodedMsg[protocol.fixtags.TargetCompID], decodedMsg[protocol.fixtags.SenderCompID])
                connectedSessions[decodedMsg[protocol.fixtags.SenderCompID]] = self.session
            else:
                self.session = connectedSessions[decodedMsg[protocol.fixtags.SenderCompID]]

        # validate the seq number
        recvSeqNo = decodedMsg[protocol.fixtags.MsgSeqNum]
        (seqNoState, lastKnownSeqNo) = self.session.validateRecvSeqNo(recvSeqNo)

        for handler in filter(lambda x: (x[1] is None or x[1] == MessageDirection.INBOUND) and
            (x[2] is None or x[2] == decodedMsg[protocol.fixtags.MsgType]), self.msgHandlers):
            handler[0](self, decodedMsg)

        if decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.LOGON:
            self.connectionState = ConnectionState.LOGGED_IN
            self.heartbeatPeriod = float(decodedMsg[protocol.fixtags.HeartBtInt])
            msg = self.codec.pack(protocol.messages.Messages.logon(), self.session)
            self.sendMsg(msg)
            self.registerLoggedIn()
        elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.LOGOUT:
            self.connectionState = ConnectionState.LOGGED_OUT
            self.registerLoggedOut()
            self.handle_close()
        elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.TESTREQUEST:
            msg = self.codec.pack(protocol.messages.Messages.heartbeat(), self.session)
            self.sendMsg(msg)
        elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.RESENDREQUEST:
            msg = self.codec.pack(protocol.messages.Messages.sequence_reset(decodedMsg, True), self.session)
            self.sendMsg(msg)
        elif decodedMsg[protocol.fixtags.MsgType] == protocol.msgtype.SEQUENCERESET:
            newSeqNo = decodedMsg[protocol.fixtags.NewSeqNo]
            recvSeqNo = newSeqNo

        if seqNoState is False:
            # We should send a resend request
            msg = self.codec.pack(protocol.messages.Messages.resend_request(lastKnownSeqNo, recvSeqNo), self.session)
            self.sendMsg(msg)
        else:
            self.session.setRecvSeqNo(recvSeqNo)

class FIXServer(FIXEndPoint):
    def __init__(self, eventMgr, protocol):
     FIXEndPoint.__init__(self, eventMgr, protocol)

    def start(self, host, port):
        self.shouldShutdown = False
        self.connections = []
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.socket.listen(5)
        self.serverSocketRegistration = FileDescriptorEventRegistration(self.handle_accept, self.socket, EventType.READ)

        logging.debug("Awaiting Connections " + host + ":" + str(port))
        self.eventMgr.registerHandler(self.serverSocketRegistration)

    def stop(self):
        logging.info("Stopping server connections")
        for connection in self.connections:
            connection.disconnect()
        self.serverSocketRegistration.fd.close()
        self.eventMgr.unregisterHandler(self.serverSocketRegistration)

    def handle_accept(self, type, closure):
        pair = self.socket.accept()
        if pair is not None:
            sock, addr = pair
            logging.info("Connection from %s" % repr(addr))
            connection = FIXServerConnectionHandler(self.eventMgr, self.protocol, sock, addr, self)
            self.connections.append(connection)
            for handler in filter(lambda x: x[1] == ConnectionState.CONNECTED, self.connectionHandlers):
                    handler[0](connection)
