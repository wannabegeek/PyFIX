# PyFIX [![Build Status](https://travis-ci.org/wannabegeek/PyFIX.svg?branch=master)](https://travis-ci.org/wannabegeek/PyFIX)
Open Source implementation of a FIX (Financial Information eXchange) Engine implemented in Python

See here [http://fixprotocol.org/] for more information on what FIX is.

## Installation

This package requires Python 3 to run.

Install in the normal python way
```
python setup.py install
```    
and it should install with no errors

## Usage
Using the module should be simple. There is an examples directory, which is the probably best place to start.

### Session Setup
Create an `EventManager` object instance, this handles all the timers and socket data required by the FIX engine, however, you can add to events to the manager if required.

Either you can create a `FIXClient` or a `FIXServer`. The Client initiates the connection and also initaiates the Logon sequence, a Server would sit there waiting for inbound connections, and expect a Logon message to be sent.
```python
self.eventMgr = EventManager()
self.client = FIXClient(self.eventMgr, "pyfix.FIX44", "TARGET", "SENDER")

# tell the client to start the connection sequence
self.client.start('localhost', int("9898"))

# enter the event loop waiting for something to happen
while True:
    self.eventMgr.waitForEvent()

```

The argument "pyfix.FIX44" specified the module which is used as the protocol, this is dynamically loaded, to you can create and specify your own if required.

If you want to do something useful, other than just watching the session level bits work, you'll probably want to register for connection status changes (you'll need to do this be fore starting the event loop);

```python
self.client.addConnectionListener(self.onConnect, ConnectionState.CONNECTED)
self.client.addConnectionListener(self.onDisconnect, ConnectionState.DISCONNECTED)
```

The implementatino of thouse methods would be something like this;
```python
def onConnect(self, session):
    logging.info("Established connection to %s" % (session.address(), ))
    session.addMessageHandler(self.onLogin, MessageDirection.INBOUND, self.client.protocol.msgtype.LOGON)

def onDisconnect(self, session):
    logging.info("%s has disconnected" % (session.address(), ))
    session.removeMsgHandler(self.onLogin, MessageDirection.INBOUND, self.client.protocol.msgtype.LOGON)
```
in the code above, we are registering to be called back whenever we receive (`MessageDirection.INBOUND`) a logon request `MsgType[35]=A` on that session.

That is pretty much it for the session setup.

### Message construction and sending

Constructing a message is simple, and is just a matter of adding the fields you require.
The session level tags will be added when the message is encoded by the codec. Setting any of the following session tags will result in the tag being duplicated in the message 
- BeginString
- BodyLength
- MsgType
- MsgSeqNo
- SendingTime
- SenderCompID
- TargetCompID
- CheckSum

Example of building a simple message

```python
def sendOrder(self, connectionHandler):
    self.clOrdID = self.clOrdID + 1
    # get the codec we are currently using for this session
    codec = connectionHandler.codec

    # create a new message
    msg = FIXMessage(codec.protocol.msgtype.NEWORDERSINGLE)
    
    # ...and add some data to it
    msg.setField(codec.protocol.fixtags.Price, random.random() * 1000)
    msg.setField(codec.protocol.fixtags.OrderQty, int(random.random() * 10000))
    msg.setField(codec.protocol.fixtags.Symbol, "VOD.L")
    msg.setField(codec.protocol.fixtags.SecurityID, "GB00BH4HKS39")
    msg.setField(codec.protocol.fixtags.SecurityIDSource, "4")
    msg.setField(codec.protocol.fixtags.Symbol, "VOD.L")
    msg.setField(codec.protocol.fixtags.Account, "TEST")
    msg.setField(codec.protocol.fixtags.HandlInst, "1")
    msg.setField(codec.protocol.fixtags.ExDestination, "XLON")
    msg.setField(codec.protocol.fixtags.Side, int(random.random() * 2))
    msg.setField(codec.protocol.fixtags.ClOrdID, str(self.clOrdID))
    msg.setField(codec.protocol.fixtags.Currency, "GBP")

    # send the message on the session
    connectionHandler.sendMsg(codec.pack(msg, connectionHandler.session))
```

A message (which is a subclass of `FIXContext`) can also hold instances of `FIXContext`, these will be treated as repeating groups. For example

```
msg = FIXMessage(codec.protocol.msgtype.NEWORDERSINGLE)
msg.setField(codec.protocol.fixtags.Symbol, "VOD.L")
msg.setField(codec.protocol.fixtags.SecurityID, "GB00BH4HKS39")
msg.setField(codec.protocol.fixtags.SecurityIDSource, "4")

rptgrp1 = FIXContext()
rptgrp1.setField(codec.protocol.fixtags.PartyID, "It's Me")
rptgrp1.setField(codec.protocol.fixtags.PartyIDSource, "1")
rptgrp1.setField(codec.protocol.fixtags.PartyRole, "2")

msg.addRepeatingGroup(codec.protocol.fixtags.NoPartyIDs, rptgrp1)

rptgrp2 = FIXContext()
rptgrp2.setField(codec.protocol.fixtags.PartyID, "Someone Else")
rptgrp2.setField(codec.protocol.fixtags.PartyIDSource, "2")
rptgrp2.setField(codec.protocol.fixtags.PartyRole, "8")
msg.addRepeatingGroup(codec.protocol.fixtags.NoPartyIDs, rptgrp2)

```
This will result in a message like the following
```
8=FIX.4.4|9=144|35=D|49=sender|56=target|34=1|52=20150619-11:08:54.000|55=VOD.L|48=GB00BH4HKS39|22=4|453=2|448=It's Me|447=1|452=2|448=Someone Else|447=2|452=8|10=073|
```

To send the message you need a handle on the session you want to use, this is provided to you in the callback methods. e.g. in the code above we registered for Logon callbacks using
```
session.addMessageHandler(self.onLogin, MessageDirection.INBOUND, self.client.protocol.msgtype.LOGON)
```

the signature for the callback is something like;
```
def onLogin(self, connectionHandler, msg):
    logging.info("Logged in")
```
