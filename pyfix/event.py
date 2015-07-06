from enum import Enum
import datetime
import os
from select import select, error
import errno
import time

class EventType(Enum):
    NONE = 0
    READ = 1
    WRITE = 2
    TIMEOUT = 4
    READWRITE = READ | WRITE

class EventRegistration(object):
    def __init__(self, callback, closure=None):
        self.callback = callback
        self.closure = closure

class TimerEventRegistration(EventRegistration):
    class TimeoutState(Enum):
        NONE = 0
        START = 1
        PROGRESS = 2

    def __init__(self, callback, timeout, closure=None):
        EventRegistration.__init__(self, callback, closure)
        self.timeout = timeout
        self.timeoutState = TimerEventRegistration.TimeoutState.START
        self.timeLeft = timeout
        self.lastTime = None

    def reset(self):
        self.timeLeft = self.timeout

    def __str__(self):
        return "TimerEvent interval: %s, remaining: %s" % (self.timeout, self.timeLeft)


class FileDescriptorEventRegistration(EventRegistration):

    def __init__(self, callback, fileDescriptor, eventType, closure=None):
        EventRegistration.__init__(self, callback, closure)
        self.fd = fileDescriptor
        self.eventType = eventType

    def __str__(self):
        return "FileDescriptorEvent fd: %s, type: %s" % (self.fd, self.eventType.name)


class _Event(object):
    def __init__(self, fd, filter):
        self.fd = fd
        self.filter = filter

class EventLoop(object):
    def add(self, event):
        pass

    def remove(self, event):
        pass

    def run(self, timeout):
        pass

class SelectEventLoop(EventLoop):
    def __init__(self):
        self.readSet = []
        self.writeSet = []

    def add(self, event):
        if (event.filter.value & EventType.READ.value) == EventType.READ.value:
            self.readSet.append(event.fd)
        if (event.filter.value & EventType.WRITE.value) == EventType.WRITE.value:
            self.writeSet.append(event.fd)

    def remove(self, event):
        if event.filter.value & EventType.READ.value == EventType.READ.value:
            self.readSet.remove(event.fd)
        if event.filter.value & EventType.WRITE.value == EventType.WRITE.value:
            self.writeSet.remove(event.fd)

    def run(self, timeout):
        if len(self.readSet) == 0 and len(self.writeSet) ==0:
            time.sleep(timeout)
            return []
        else:
            while True:
                try:
                    readReady, writeReady, exceptReady = select(self.readSet, self.writeSet, [], timeout)
                    events = []
                    for r in readReady:
                        events.append(_Event(r, EventType.READ))
                    for r in writeReady:
                        events.append(_Event(r, EventType.WRITE))
                    return events
                except error as why:
                    if os.name == 'posix':
                        if why[0] != errno.EAGAIN and why[0] != errno.EINTR:
                            break
                    else:
                        if why[0] == errno.WSAEADDRINUSE:
                            break


class EventManager(object):
    def __init__(self):
        self.eventLoop = SelectEventLoop()
        self.handlers = []

    def waitForEvent(self):
        self.waitForEventWithTimeout(None)

    def waitForEventWithTimeout(self, timeout):
        if not self.handlers:
            raise RuntimeError("Failed to start event loop without any handlers")

        timeout = self._setTimeout(timeout)
        events = self.eventLoop.run(timeout)
        self._serviceEvents(events)

    def _setTimeout(self, timeout):
        nowTime = datetime.datetime.utcnow()
        duration = timeout

        for handler in self.handlers:
            if type(handler) is TimerEventRegistration:
                if handler.timeoutState == TimerEventRegistration.TimeoutState.START:
                    handler.timeoutState = TimerEventRegistration.TimeoutState.PROGRESS

                handler.lastTime = nowTime
                if duration is None or handler.timeLeft < duration:
                    duration = handler.timeLeft

        return duration

    def _serviceEvents(self, events):
        nowTime = datetime.datetime.utcnow()
        for handler in self.handlers:
            if isinstance(handler, FileDescriptorEventRegistration):
                for event in events:
                    if event.fd == handler.fd:
                        type = handler.eventType.value & event.filter.value
                        if type != EventType.NONE:
                            handler.callback(type, handler.closure)
            elif isinstance(handler, TimerEventRegistration):
                if handler.timeoutState == TimerEventRegistration.TimeoutState.PROGRESS:
                    elapsedTime = nowTime - handler.lastTime
                    handler.timeLeft -= elapsedTime.total_seconds()
                    if handler.timeLeft <= 0.0:
                        handler.timeLeft = handler.timeout
                        handler.callback(EventType.TIMEOUT, handler.closure)


    def registerHandler(self, handler):
        if isinstance(handler, TimerEventRegistration):
            pass
        elif isinstance(handler, FileDescriptorEventRegistration):
            self.eventLoop.add(_Event(handler.fd, handler.eventType))
        else:
            raise RuntimeError("Trying to register invalid handler")
        self.handlers.append(handler)

    def unregisterHandler(self, handler):
        if self.isRegistered(handler):
            self.handlers.remove(handler)
            if isinstance(handler, FileDescriptorEventRegistration):
                self.eventLoop.remove(_Event(handler.fd, handler.eventType))


    def isRegistered(self, handler):
        return handler in self.handlers
