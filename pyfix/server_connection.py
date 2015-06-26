import logging
import socket
from pyfix.journaler import DuplicateSeqNoError
from pyfix.session import FIXSession
from pyfix.connection import FIXEndPoint, ConnectionState, MessageDirection, FIXConnectionHandler
from pyfix.event import FileDescriptorEventRegistration, EventType

class FIXServerConnectionHandler(FIXConnectionHandler):
    def __init__(self, engine, protocol, sock=None, addr=None, observer=None):
        FIXConnectionHandler.__init__(self, engine, protocol, sock, addr, observer)

    def handleSessionMessage(self, msg):
        protocol = self.codec.protocol

        recvSeqNo = msg[protocol.fixtags.MsgSeqNum]

        msgType = msg[protocol.fixtags.MsgType]
        targetCompId = msg[protocol.fixtags.TargetCompID]
        senderCompId = msg[protocol.fixtags.SenderCompID]
        responses = []

        if msgType == protocol.msgtype.LOGON:
            if self.connectionState == ConnectionState.LOGGED_IN:
                logging.warning("Client session already logged in - ignoring login request")
            else:
                # compids are reversed here...
                self.session = self.engine.getOrCreateSessionFromCompIds(senderCompId, targetCompId)
                if self.session is not None:
                    try:
                        self.connectionState = ConnectionState.LOGGED_IN
                        self.heartbeatPeriod = float(msg[protocol.fixtags.HeartBtInt])
                        responses.append(protocol.messages.Messages.logon())
                        self.registerLoggedIn()
                    except DuplicateSeqNoError:
                        logging.error("Failed to process login request with duplicate seq no")
                        self.disconnect()
                        return
                else:
                    logging.warning("Rejected login attempt for invalid session (SenderCompId: %s, TargetCompId: %s)" % (senderCompId, targetCompId))
                    self.disconnect()
                    return # we have to return here since self.session won't be valid
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
                newSeqNo = msg[protocol.fixtags.NewSeqNo]
                self.session.setRecvSeqNo(int(newSeqNo) - 1)
                recvSeqNo = newSeqNo
        else:
            logging.warning("Can't process message, counterparty is not logged in")

        return (recvSeqNo, responses)

class FIXServer(FIXEndPoint):
    def __init__(self, engine, protocol):
     FIXEndPoint.__init__(self, engine, protocol)

    def start(self, host, port):
        self.connections = []
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.socket.listen(5)
        self.serverSocketRegistration = FileDescriptorEventRegistration(self.handle_accept, self.socket, EventType.READ)

        logging.debug("Awaiting Connections " + host + ":" + str(port))
        self.engine.eventManager.registerHandler(self.serverSocketRegistration)

    def stop(self):
        logging.info("Stopping server connections")
        for connection in self.connections:
            connection.disconnect()
        self.serverSocketRegistration.fd.close()
        self.engine.eventManager.unregisterHandler(self.serverSocketRegistration)

    def handle_accept(self, type, closure):
        pair = self.socket.accept()
        if pair is not None:
            sock, addr = pair
            logging.info("Connection from %s" % repr(addr))
            connection = FIXServerConnectionHandler(self.engine, self.protocol, sock, addr, self)
            self.connections.append(connection)
            for handler in filter(lambda x: x[1] == ConnectionState.CONNECTED, self.connectionHandlers):
                    handler[0](connection)
