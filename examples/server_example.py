import logging
from pyfix.connection import ConnectionState, MessageDirection
from pyfix.server_connection import FIXServer
from pyfix.event import EventManager


class Replay:
    def __init__(self):
        eventMgr = EventManager()
        self.server = FIXServer(eventMgr, "pyfix.FIX44")

        self.server.addConnectionListener(self.onConnect, ConnectionState.CONNECTED)
        self.server.addConnectionListener(self.onDisconnect, ConnectionState.DISCONNECTED)

        self.server.start('', int("9898"))
        while True:
            eventMgr.waitForEventWithTimeout(10.0)

        self.server.removeConnectionListener(self.onConnect, ConnectionState.CONNECTED)
        self.server.removeConnectionListener(self.onConnect, ConnectionState.DISCONNECTED)

    def onConnect(self, session):
        logging.info("Accepted new connection from %s" % (session.address(), ))
        session.addMessageHandler(self.onLogin, MessageDirection.OUTBOUND, self.server.protocol.msgtype.LOGON)

    def onDisconnect(self, session):
        logging.info("%s has disconnected" % (session.address(), ))
        session.removeMsgHandler(self.onLogin, MessageDirection.OUTBOUND, self.server.protocol.msgtype.LOGON)

    def onLogin(self, connectionHandler, msg):
        codec = connectionHandler.codec

        logging.info("We're logged in now")
        logging.info("[" + msg[codec.protocol.fixtags.SenderCompID] + "] <---- " + codec.protocol.msgtype.msgTypeToName(msg[codec.protocol.fixtags.MsgType]))


def main():
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)
    replay = Replay()
    logging.info("All done... shutting down")

if __name__ == '__main__':
    main()
