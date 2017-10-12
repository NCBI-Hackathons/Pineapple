# -*- coding: utf-8 -*-


import wx
import math
import json
import threading
import wx.lib.newevent
from DynaUI import GetTextExtent
from .dialog import MakeWidgetDialog, Dialog
from .base import Base, IdPool
from .field import BaseField
from . import anchor as An

__all__ = ["Widget", "Interrupted"]

WidgetEvent, EVT_WIDGET = wx.lib.newevent.NewEvent()

EVT_WIDGET_START = 1
EVT_WIDGET_CHANGE = 2
EVT_WIDGET_DONE = 3
EVT_WIDGET_FAIL = 4

WIDGET_STATE_IDLE = 1 << 0
WIDGET_STATE_FAIL = 1 << 1
WIDGET_STATE_WAIT = 1 << 2
WIDGET_STATE_WORK = 1 << 3
WIDGET_STATE_DONE = 1 << 4
WIDGET_STATE = 0b11111

STATE_HANDLER = {WIDGET_STATE_IDLE: "HandlerIdle",
                 WIDGET_STATE_FAIL: "HandlerFail",
                 WIDGET_STATE_WAIT: "HandlerWait",
                 WIDGET_STATE_WORK: "HandlerWork",
                 WIDGET_STATE_DONE: "HandlerDone"}


# ======================================================= Thread =======================================================
class Interrupted(Exception):
    """Raise to interrupt running thread"""


class Thread(threading.Thread):
    def __init__(self, Widget):
        super().__init__()
        self.setDaemon(True)
        self.Widget = Widget
        self.stop = False

    def Stop(self):
        self.stop = True

    def Stopped(self):
        return self.stop

    def run(self):
        try:
            out = self.Widget.Function()
            with self.Widget.Lock:
                if self.Widget.state == WIDGET_STATE_WORK and self.Widget.Thread == self:
                    self.Widget["OUT"] = out
                    self.Widget.OnFail() if out is None else self.Widget.OnDone()
        except Interrupted:
            pass
        except Exception:
            with self.Widget.Lock:
                if self.Widget.state == WIDGET_STATE_WORK and self.Widget.Thread == self:
                    self.Widget.OnFail()


# ================================================== How to Subclass ===================================================
# Rules:
#   Widget subclasses should have the following class properties:
#       KEY       -  Class Identifier. By default KEY is id(WidgetClass). Normally user does not need to specify KEY.
#       NAME      -  Default name of the widget, for display purpose.
#       DIALOG    -  Associated Dialog class for interacting with the widget. Not always required.
#       THREAD    -  Whether the task should be done in a separate thread.
#       INTERNAL  -  KEY for data that are input from the associated dialog.
#       INCOMING  -  Incoming anchor definitions: (AnchorType, KEY:str, IsMultiple:bool, Position:int, Name:str("")) [, (more anchors...)]
#       OUTGOING  -  AnchorType of the data sending out.
#   The following methods should be re-implemented:
#       GetName   -  How canvas display the name of this widget. Default is cls.NAME
#       Function  -  to do
#   Destroy must be called when deleting the widget to (i)clear links; (ii)close dialog; (iii)stop thread; (iv)release id
# ======================================================= Widget =======================================================
class Widget(wx.EvtHandler, Base):
    KEY = None
    NAME = ""
    DIALOG = None
    THREAD = False
    INTERNAL = None
    INCOMING = None
    OUTGOING = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "__INITIALIZED__"):
            cls.__INITIALIZED__ = True
            cls.NAME = args[0].L.Get(cls.NAME, "WIDGET_NAME_")
            if cls.DIALOG in ("H", "V"):
                cls.DIALOG = type("_AutoDialog" + cls.__name__, (Dialog,), {"ORIENTATION": cls.DIALOG})
            elif isinstance(cls.DIALOG, dict):
                cls.DIALOG = type("_AutoDialog" + cls.__name__, (Dialog,), cls.DIALOG)
            if cls.INTERNAL is None:
                cls.INTERNAL = ()
            elif not isinstance(cls.INTERNAL, (tuple, list)):
                cls.INTERNAL = (cls.INTERNAL,)
            if cls.INCOMING is None:
                cls.INCOMING = ()
            elif not isinstance(cls.INCOMING[0], (tuple, list)):
                cls.INCOMING = (cls.INCOMING,)
            if cls.OUTGOING is None:
                pass
            elif not isinstance(cls.OUTGOING, (tuple, list)):
                cls.OUTGOING = (cls.OUTGOING, "", None)
        return super().__new__(cls)

    def __init__(self, canvas):
        wx.EvtHandler.__init__(self)
        Base.__init__(self, w=56, h=56)
        self.Canvas = canvas
        self.name = self.NAME
        self.namePos = (0, 0)
        self.rectSelect = wx.Rect(0, 0, 68, 68)
        self.state = WIDGET_STATE_IDLE
        self.stateHandler = self.HandlerIdle
        self.Bind(EVT_WIDGET, lambda evt: self.stateHandler(evt))
        self.dialogSize = None
        self.dialogPos = None
        self.Dialog = None
        self.Thread = None
        self.Lock = threading.Lock()
        self.Data = {}
        self.Anchors = []
        self.Incoming = []
        self.Outgoing = []
        if self.INTERNAL:
            for field in self.INTERNAL:
                self.Data[field.key if isinstance(field, BaseField) else field] = None
        if self.INCOMING:
            for args in self.INCOMING:
                self.AddAnchor(False, *args)
        if self.OUTGOING:
            self.AddAnchor(True, self.OUTGOING[0], "OUT", True, "R" if self.INCOMING else "-R", self.OUTGOING[1], self.OUTGOING[2])

    def __setitem__(self, key, value):
        self.Data[key] = value

    def __getitem__(self, item):
        return self.Data[item]

    def AddAnchor(self, send, aType, key, multiple, pos, name="", anchor=None):
        a = (anchor or An.Anchor)(self, aType, key, multiple, send, pos, self.Canvas.L.Get(name, "ANCHOR_NAME_"))
        (self.Outgoing if send else self.Incoming).append(a)
        self.Anchors.append(a)
        self[a.key] = None

    def Destroy(self):
        self.Stop()
        if self.Dialog:
            self.Dialog.OnClose()
        self.Unbind(EVT_WIDGET)
        self.SetState(WIDGET_STATE_IDLE)
        for a in reversed(self.Anchors):
            a.EmptyTarget()
            IdPool.Release(a.Id)
        IdPool.Release(self.Id)

    def NewNamePosition(self):
        self.namePos = self.x + 28 - GetTextExtent(self.Canvas, self.name)[0] // 2, self.y - 20 if len(self.Anchors) == 1 and self.Anchors[0].pos == "B" else self.y + 64

    def NewPosition(self, x, y):
        if self.Canvas.S["TOGGLE_SNAP"]:
            x = x >> 5 << 5
            y = y >> 5 << 5
        self.x = x
        self.y = y
        self.rect.SetPosition((x, y))
        self.rectSelect.SetPosition((x - 6, y - 6))
        self.NewNamePosition()
        for a in self.Anchors:
            if a.posAuto and a.connected:
                x = sum(i.x for i in a.connected) / len(a.connected) - self.x - 25
                y = sum(i.y for i in a.connected) / len(a.connected) - self.y - 25
                theta = math.atan2(y, x) * 4
                if -4.0 * math.pi <= theta < -math.pi:
                    a.pos = "T"
                elif -math.pi <= theta < math.pi:
                    a.pos = "R"
                elif math.pi <= theta < 4 * math.pi:
                    a.pos = "B"
            if a.pos == "L":
                ax = -6
            elif a.pos == "R":
                ax = 56
            else:
                ax = 25
            if a.pos == "T":
                ay = -6
            elif a.pos == "B":
                ay = 56
            else:
                ay = 25
            a.SetPosition(self.x + ax, self.y + ay)

    def Draw(self, dc):
        key = "WIDGET_CANVAS"
        if self.state == WIDGET_STATE_DONE:
            key = "WIDGET_CANVAS_DONE"
        elif self.state == WIDGET_STATE_WAIT:
            key = "WIDGET_CANVAS_WAIT"
        elif self.state == WIDGET_STATE_FAIL:
            key = "WIDGET_CANVAS_FAIL"
        elif self.state == WIDGET_STATE_WORK:
            if self.Canvas.colorLastBlink:
                key = "WIDGET_CANVAS_DONE"
        dc.DrawBitmap(self.Canvas.R[key][self.KEY], self.x, self.y)
        if self.Dialog:
            if self.Dialog.detached:
                dc.DrawBitmap(self.Canvas.R["DIALOG_DTCH"][3], self.x + 36, self.y)
            else:
                dc.DrawBitmap(self.Canvas.R["DIALOG_ATCH"][3], self.x + 36, self.y)
        if self.Canvas.S["TOGGLE_NAME"]:
            dc.nameTexts.append(self.name)
            dc.namePoints.append(self.namePos)
        if self.Canvas.S["TOGGLE_ANCR"]:
            for a in self.Anchors:
                a.Draw(dc)

    # ----------------------------------------------
    def GetLinkedWidget(self):
        for a in self.Anchors:
            for dest in a.connected:
                yield dest.Widget

    def GetOutgoingWidget(self):
        for a in self.Outgoing:
            for dest in a.connected:
                yield dest.Widget

    def GetIncomingWidget(self):
        for a in self.Incoming:
            for dest in a.connected:
                yield dest.Widget

    def PostToOutgoingWidget(self, evtType, state=WIDGET_STATE):
        for w in self.GetOutgoingWidget():
            if w.state & state:
                wx.PostEvent(w, WidgetEvent(evtType=evtType))

    def PostToIncomingWidget(self, evtType, state=WIDGET_STATE):
        for w in self.GetIncomingWidget():
            if w.state & state:
                wx.PostEvent(w, WidgetEvent(evtType=evtType))

    def IsOutgoingAvailable(self):
        for a in self.Outgoing:
            if not a.connected:
                return False
        return True

    def IsIncomingAvailable(self):
        for a in self.Incoming:
            if not a.connected:
                return False
        return True

    def IsInternalAvailable(self):
        for field in self.INTERNAL:
            if self.Data[field.key if isinstance(field, BaseField) else field] is None:
                return False
        return True

    def InitData(self):
        for a in self.Incoming:
            if a.multiple:
                self[a.key] = [dest.Widget[dest.key] for dest in a.connected] if a.connected else None
            else:
                self[a.key] = a.connected[0].Widget[a.connected[0].key] if a.connected else None
        for a in self.Outgoing:
            self[a.key] = None

    # ----------------------- User Event -----------------------
    def OnActivation(self):
        if self.Dialog:
            if self.Dialog.detached:
                if self.Dialog.Frame.minimized:
                    self.Dialog.Frame.OnMinimize()
            else:
                self.Dialog.Head.Play("ENTER_THEN_LEAVE")
            self.Dialog.SetFocus()
        elif self.DIALOG:
            self.Dialog = MakeWidgetDialog(self)

    def OnSetIncoming(self):
        wx.PostEvent(self, WidgetEvent(evtType=EVT_WIDGET_CHANGE))

    def OnSetInternal(self):
        wx.PostEvent(self, WidgetEvent(evtType=EVT_WIDGET_CHANGE))

    def OnStart(self):
        wx.PostEvent(self, WidgetEvent(evtType=EVT_WIDGET_START))

    def OnFail(self):
        wx.PostEvent(self, WidgetEvent(evtType=EVT_WIDGET_FAIL))

    def OnDone(self):
        wx.PostEvent(self, WidgetEvent(evtType=EVT_WIDGET_DONE))

    def Stop(self):
        if self.Thread and self.Thread.isAlive():
            self.Thread.Stop()
            self.Thread = None

    def Run(self):
        self.SetState(WIDGET_STATE_WORK)
        self.InitData()
        if self.THREAD:
            self.Thread = Thread(self)
            self.Thread.start()
        else:
            try:
                self["OUT"] = self.Function()
                self.OnFail() if self["OUT"] is None else self.OnDone()
            except Exception:
                self.OnFail()

    def IsDone(self):
        return self.state == WIDGET_STATE_DONE

    def IsWorking(self):
        return self.state == WIDGET_STATE_WORK

    def IsWaiting(self):
        return self.state == WIDGET_STATE_WAIT

    def IsRunning(self):
        return self.state in (WIDGET_STATE_WORK, WIDGET_STATE_WAIT)

    # ----------------------- Self Event -----------------------
    def SetState(self, state):
        with self.Lock:
            if self.state == WIDGET_STATE_WORK:
                self.Canvas.WidgetRunning(0)
            if state == WIDGET_STATE_WORK:
                self.Canvas.WidgetRunning(1)
            if self.THREAD and self.INCOMING and self.Dialog:
                if state in (WIDGET_STATE_WORK, WIDGET_STATE_WAIT):
                    self.Dialog[3].Hide()
                    self.Dialog[4].Show()
                else:
                    self.Dialog[4].Hide()
                    self.Dialog[3].Show()
                self.Dialog.Layout()
            self.state = state
            self.stateHandler = getattr(self, STATE_HANDLER[state])
            name = self.GetName()
            self.name = name if name is not None else self.NAME
            self.NewNamePosition()
            self.Canvas.ReDraw()

    def SaveData(self):
        return self.Save()

    def LoadData(self, f):
        self.Data = self.Load(f)
        name = self.GetName()
        self.name = name if name is not None else self.NAME
        self.NewNamePosition()

    def SaveState(self):
        return (self.state & 0b10011) or 1

    def LoadState(self, state):
        self.state = state
        self.stateHandler = getattr(self, STATE_HANDLER[state])

    def HandlerIdle(self, evt):
        if evt.evtType == EVT_WIDGET_CHANGE:
            self.InitData()
            if self.Dialog:
                wx.CallAfter(self.Dialog.GetData)
            self.PostToOutgoingWidget(EVT_WIDGET_CHANGE, WIDGET_STATE_IDLE)
        elif evt.evtType == EVT_WIDGET_START:
            if not self.IsIncomingAvailable() or not self.IsInternalAvailable():
                self.SetState(WIDGET_STATE_FAIL)
                self.PostToOutgoingWidget(EVT_WIDGET_FAIL)
                return
            fail = False
            wait = False
            for w in self.GetIncomingWidget():
                if w.state == WIDGET_STATE_FAIL:
                    fail = True
                elif w.state == WIDGET_STATE_WORK:
                    wait = True
                elif w.state == WIDGET_STATE_WAIT:
                    wait = True
                elif w.state == WIDGET_STATE_IDLE:
                    wait = True
            if fail:
                self.SetState(WIDGET_STATE_FAIL)
                self.PostToOutgoingWidget(EVT_WIDGET_FAIL)
            elif wait:
                self.SetState(WIDGET_STATE_WAIT)
                self.PostToIncomingWidget(EVT_WIDGET_START, WIDGET_STATE_IDLE)
            else:
                self.Run()

    def HandlerWait(self, evt):
        if evt.evtType == EVT_WIDGET_CHANGE:
            self.SetState(WIDGET_STATE_IDLE)
            self.InitData()
            self.PostToOutgoingWidget(EVT_WIDGET_CHANGE, WIDGET_STATE_WAIT | WIDGET_STATE_FAIL | WIDGET_STATE_IDLE)
        elif evt.evtType == EVT_WIDGET_FAIL:
            self.SetState(WIDGET_STATE_FAIL)
            self.PostToOutgoingWidget(EVT_WIDGET_FAIL, WIDGET_STATE_WAIT)
        elif evt.evtType == EVT_WIDGET_START:
            wait = False
            for w in self.GetIncomingWidget():
                if w.state == WIDGET_STATE_WORK:
                    wait = True
                elif w.state == WIDGET_STATE_WAIT:
                    wait = True
                elif w.state == WIDGET_STATE_IDLE:
                    wait = True
                elif w.state == WIDGET_STATE_FAIL:
                    wait = True
            if not wait:
                self.Run()

    def HandlerWork(self, evt):
        if evt.evtType == EVT_WIDGET_CHANGE:
            self.SetState(WIDGET_STATE_IDLE)
            self.InitData()
            self.PostToOutgoingWidget(EVT_WIDGET_CHANGE, WIDGET_STATE_WAIT | WIDGET_STATE_FAIL)
            self.Stop()
        elif evt.evtType == EVT_WIDGET_DONE:
            self.SetState(WIDGET_STATE_DONE)
            self.PostToOutgoingWidget(EVT_WIDGET_START, WIDGET_STATE_WAIT)
        elif evt.evtType == EVT_WIDGET_FAIL:
            self.SetState(WIDGET_STATE_FAIL)
            self.PostToOutgoingWidget(EVT_WIDGET_FAIL, WIDGET_STATE_WAIT)
        if self.Dialog:
            if not self.Dialog.detached:
                wx.CallAfter(self.Dialog.Head.Play, "ENTER_THEN_LEAVE")
            wx.CallAfter(self.Dialog.GetData)

    def HandlerFail(self, evt):
        if evt.evtType == EVT_WIDGET_CHANGE:
            self.SetState(WIDGET_STATE_IDLE)
            self.InitData()
            if self.Dialog:
                wx.CallAfter(self.Dialog.GetData)
            self.PostToOutgoingWidget(EVT_WIDGET_CHANGE, WIDGET_STATE_FAIL | WIDGET_STATE_IDLE)

    def HandlerDone(self, evt):
        if evt.evtType == EVT_WIDGET_CHANGE:
            self.SetState(WIDGET_STATE_IDLE)
            self.InitData()
            if self.Dialog:
                wx.CallAfter(self.Dialog.GetData)
            self.PostToOutgoingWidget(EVT_WIDGET_CHANGE, WIDGET_STATE)
        elif evt.evtType == EVT_WIDGET_START:
            self.PostToOutgoingWidget(EVT_WIDGET_CHANGE)
            self.Run()

    # ------------------------ Override ------------------------
    def GetName(self):
        return self.NAME

    def Function(self):
        return False

    def Save(self):
        return json.dumps(self.Data)

    def Load(self, f):
        return json.load(f)