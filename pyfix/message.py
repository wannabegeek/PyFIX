from collections import OrderedDict
from enum import Enum

class MessageDirection(Enum):
    INBOUND = 0
    OUTBOUND = 1

class _FIXRepeatingGroupContainer:
    def __init__(self):
        self.groups = []

    def addGroup(self, group, index):
        if index == -1:
            self.groups.append(group)
        else:
            self.groups.insert(index, group)

    def removeGroup(self, index):
        del self.groups[index]

    def getGroup(self, index):
        return self.groups[index]

    def __str__(self):
        return str(len(self.groups)) + "=>" + str(self.groups)

    __repr__ = __str__

class FIXContext(object):
    def __init__(self):
        self.tags = OrderedDict()

    def setField(self, tag, value):
        self.tags[tag] = value

    def removeField(self, tag):
        try:
            del self.tags[tag]
        except KeyError:
            pass

    def getField(self, tag):
        return self.tags[tag]

    def addRepeatingGroup(self, tag, group, index=-1):
        if tag in self.tags:
            groupContainer = self.tags[tag]
            groupContainer.addGroup(group, index)
        else:
            groupContainer = _FIXRepeatingGroupContainer()
            groupContainer.addGroup(group, index)
            self.tags[tag] = groupContainer

    def removeRepeatingGroupByIndex(self, tag, index=-1):
        if self.isRepeatingGroup(tag):
            try:
                if index == -1:
                    del self.tags[tag]
                    pass
                else:
                    groups = self.tags[tag]
                    groups.removeGroup(index)
            except KeyError:
                pass

    def getRepeatingGroup(self, tag):
        if self.isRepeatingGroup(tag):
            return (len(self.tags[tag].groups), self.tags[tag].groups)
        return None

    def getRepeatingGroupByTag(self, tag, identifierTag, identifierValue):
        if self.isRepeatingGroup(tag):
            for group in self.tags[tag].groups:
                if identifierTag in group.tags:
                    if group.getField(identifierTag) == identifierValue:
                        return group
        return None

    def getRepeatingGroupByIndex(self, tag, index):
        if self.isRepeatingGroup(tag):
            return self.tags[tag].groups[index]
        return None

    def __getitem__(self, tag):
        return self.getField(tag)

    def __setitem__(self, tag, value):
        self.setField(tag, value)

    def isRepeatingGroup(self, tag):
        return type(self.tags[tag]) is _FIXRepeatingGroupContainer

    def __contains__(self, item):
        return item in self.tags

    def __str__(self):
        r= ""
        allTags = []
        for tag in self.tags:
            allTags.append("%s=%s" % (tag, self.tags[tag]))
        r += "|".join(allTags)
        return r

    def __eq__(self, other):
        # if our string representation looks the same, the objects are equivalent
        return self.__str__() == other.__str__()

    __repr__ = __str__

class FIXMessage(FIXContext):
    def __init__(self, msgType):
        self.msgType = msgType
        FIXContext.__init__(self)

    def setMsgType(self, msgType):
        self.msgType = msgType
