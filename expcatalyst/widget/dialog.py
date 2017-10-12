# -*- coding: utf-8 -*-


import wx
import DynaUI as UI
from .field import *

__all__ = ["Dialog", "DisableCanvas"]

SIZE_BTN = wx.Size(20, 20)
SIZE_BTN_BOLD = wx.Size(32, 20)
SF_HEAD = wx.SizerFlags().Expand().Border(wx.TOP, 2)
SF_MAIN = wx.SizerFlags().Expand()
SF_SASH = wx.SizerFlags().Expand().Border(wx.BOTTOM, 6)

DisableCanvas = lambda func: lambda self: (self.DisableCanvas(), func(self), self.EnableCanvas())


# ==================================================== DetachedHead ====================================================
class DetachedHead(UI.BaseHead):
    def __init__(self, parent):
        super().__init__(parent, buttons=False)
        self.GetSizer().Insert(1, UI.ToolNormal(self, size=UI.SETTINGS["DLG_HEAD_BTN"], pics=self.R["DIALOG_LOCA"], func=self.Frame.Main.Locate), self.SizerFlags)
        self.GetSizer().Insert(1, UI.ToolNormal(self, size=UI.SETTINGS["DLG_HEAD_BTN"], pics=self.R["DIALOG_ATCH"], func=self.Frame.Main.Attach), self.SizerFlags)

    def OnMouse(self, evt):  # TODO Multiple screen see wx.Display
        if evt.GetEventType() == wx.wxEVT_MOTION and self.lastMousePos:
            newPos = self.lastFramePos - self.lastMousePos + self.Frame.ClientToScreen(evt.GetPosition())
            size = self.Frame.GetSize()
            UI.EnsureWindowInScreen(newPos, size, 12)
            l, t = newPos
            b = t + size[1]
            r = l + size[0]
            closestH = closestV = UI.SETTINGS["DLG_HEAD"] // 2
            for frame in wx.GetTopLevelWindows():
                if isinstance(frame, UI.BaseDialog) and frame != self.Frame and frame.IsShown():
                    _l, _t = frame.GetPosition()
                    _b = _t + frame.GetSize()[1]
                    _r = _l + frame.GetSize()[0]
                    if _l <= l < _r or _l < r <= _r:
                        d = abs(t - _b)
                        if d < closestV:
                            closestV = d
                            newPos[1] = _b
                        d = abs(b - _t)
                        if d < closestV:
                            closestV = d
                            newPos[1] = _t - size[1]
                        d = abs(t - _t)
                        if d < closestV:
                            closestV = d
                            newPos[1] = _t
                        d = abs(b - _b)
                        if d < closestV:
                            closestV = d
                            newPos[1] = _b - size[1]
                    if _t <= t < _b or _t < b <= _b:
                        d = abs(l - _r)
                        if d < closestH:
                            closestH = d
                            newPos[0] = _r
                        d = abs(r - _l)
                        if d < closestH:
                            closestH = d
                            newPos[0] = _l - size[0]
                        d = abs(l - _l)
                        if d < closestH:
                            closestH = d
                            newPos[0] = _l
                        d = abs(r - _r)
                        if d < closestH:
                            closestH = d
                            newPos[0] = _r - size[0]
            self.Frame.SetPosition(newPos)
        else:
            super().OnMouse(evt)


# ==================================================== AttachedHead ====================================================
class AttachedHead(UI.Button):
    def __init__(self, parent, tag, func):
        super().__init__(parent=parent, size=(-1, 20), tag=tag, func=func, fg="B", edge="D", res="R")
        Sizer = wx.BoxSizer(wx.HORIZONTAL)
        Sizer.AddMany((
            (4, 4, 1),
            (UI.ToolNormal(self, size=SIZE_BTN, pics=self.R["DIALOG_DTCH"], edge=("", "TB"), func=func[1].Detach)),
            (UI.ToolNormal(self, size=SIZE_BTN, pics=self.R["DIALOG_LOCA"], edge=("", "TB"), func=func[1].Locate)),
            (UI.ToolNormal(self, size=SIZE_BTN, pics=self.R["AP_EXIT"], edge=("", "RTB"), func=func[1].OnClose, res="R"))
        ))
        self.SetSizer(Sizer)


# ==================================================== DialogMaker =====================================================
def MakeWidgetDialog(widget):
    Frame = UI.BaseDialog(parent=widget.Canvas.GetParent(),
                          title=widget.NAME,
                          style=wx.STAY_ON_TOP,
                          main=(widget.DIALOG, {"widget": widget}),
                          head=DetachedHead)
    Frame.SetSize(widget.dialogSize or Frame.GetEffectiveMinSize())
    Frame.SetPosition(widget.dialogPos or UI.EnsureWindowInScreen(widget.Canvas.ClientToScreen(widget.GetPosition() + wx.Point(64, 0)), Frame.GetSize()))
    Frame.Main.GetData()
    Frame.Play("FADEIN")
    return Frame.Main


# ======================================================= Dialog =======================================================
# Rules: #TODO
#   The following functions must be re-implemented:
#       GetData:
#           Supposed to be called only in __init__ or Reload
#           All modifiable things go here, __init__ only contain non-modifiable data
#           Use only after GetReady is called; call Canvas.Refresh after GetReady
#           Should always set all data area (If else)
#       SetData:
#           Supposed to be called only when OnApply or OnOK  by standard button
#           Don't call SetData When reload is needed
# ======================================================= Dialog =======================================================
class Dialog(UI.BaseMain):
    AUTO = True
    SIZE = None
    ORIENTATION = wx.VERTICAL
    MARGIN = 2
    LABEL_WIDTH = 80
    LINE_HEIGHT = 20

    def __init__(self, parent, widget):
        super().__init__(parent, size=self.SIZE or wx.DefaultSize)  # MainFrame - MiniFrame - Dialog
        self.Widget = widget
        self.Frame.OnClose = self.OnClose
        self.Harbor = self.GetGrandParent().Harbor
        self.Head = None
        self.Sash = None
        self.detached = True
        self.Auto = {}
        Sizer = wx.BoxSizer({"H": wx.HORIZONTAL, "V": wx.VERTICAL}[self.ORIENTATION] if self.ORIENTATION in ("V", "H") else self.ORIENTATION)
        self.Initialize(Sizer)
        if self.AUTO and self.Widget.INTERNAL:
            for field in self.Widget.INTERNAL:
                if isinstance(field, str):
                    continue
                key = field.key
                label = self.L.Get(field.label, "WIDGET_DLG_")
                if isinstance(field, BooleanField):
                    tags = self.L.Get(field.tag1), self.L.Get(field.tag2)
                    self.Auto[key] = self.AddButtonToggle(sizer=Sizer, label=label, tags=tags, toggle=self.GetDefaultData(key, 0)).IsToggled
                elif isinstance(field, IntegerField):
                    self.Auto[key] = self.AddLineCtrl(sizer=Sizer, label=label, value=str(self.GetDefaultData(key, "")), width=104).GetValue
                elif isinstance(field, FloatField):
                    self.Auto[key] = self.AddLineCtrl(sizer=Sizer, label=label, value=str(self.GetDefaultData(key, "")), width=104).GetValue
                elif isinstance(field, LineField):
                    self.Auto[key] = self.AddLineCtrl(sizer=Sizer, label=label, value=self.GetDefaultData(key, ""), hint=self.L.Get(field.hint, "WIDGET_DLG_")).GetValue
                elif isinstance(field, TextField):
                    self.Auto[key] = self.AddTextCtrl(sizer=Sizer, label=label, value=self.GetDefaultData(key, ""), ).GetValue
                elif isinstance(field, ChoiceField):
                    choices = tuple(self.L.Get(i) if isinstance(i, str) else str(i) for i in field.choices)
                    selected = field.choices.index(self.Widget[key]) if self.Widget[key] is not None else -1
                    if field.useListBox:
                        self.Auto[key] = self.AddListBox(sizer=Sizer, label=label, choices=choices, selected=selected, width=field.w, height=field.h).GetSelection
                    else:
                        self.Auto[key] = self.AddButtonBundle(sizer=Sizer, label=label, tags=choices, toggled=selected, group="_" + key, width=field.w).GetToggled
        self.Finalize(Sizer)
        self.SetSizer(Sizer)

    # --------------------------------------
    def EnableCanvas(self):
        self.GetGrandParent().Enable()

    def DisableCanvas(self):
        self.GetGrandParent().Disable()

    # --------------------------------------
    def Attach(self):
        if self.detached:
            self.detached = False
            self.Frame.Hide()
            self.Frame.Main = None
            self.Frame.GetSizer().Detach(self)
            self[0].Hide()
            self.Layout()
            if 1 in self:
                self[1].Func = self.OnBegin
            if not self.IsShown():
                self.Show()
            self.Reparent(self.Harbor.Inner)
            self.Head = AttachedHead(self.Harbor.Inner, tag=(" ■ " + self.Widget.NAME, "L"), func=(self.Harbor.OnChild, self))
            self.Sash = UI.Sash(self.Harbor.Inner, target=self, direction="T", vRange=(2, 600), func=((self.Harbor.SetActualSize,), self.Harbor.Inner.Layout, self.Harbor.ReDraw), res="D")
            self.Harbor.Inner.GetSizer().AddMany((
                (self.Head, SF_HEAD),
                (self, SF_MAIN),
                (self.Sash, SF_SASH)
            ))
            self.Harbor.SetActualSize()
            self.Harbor.ReDraw()
            if not self.Harbor.IsShown():
                self.Harbor.GetParent().HiderR.Click()
            self.Widget.Canvas.ReDraw()

    def Detach(self):
        if not self.detached:
            self.detached = True
            self._RemoveFromHarbor()
            self[0].Show()
            self.Layout()
            if 1 in self:
                self[1].Func = self.OnReady
            if not self.IsShown():
                self.Show()
            self.Reparent(self.Frame)
            self.Frame.Main = self
            self.Frame.GetSizer().Insert(1, self, 1, wx.EXPAND | wx.ALL ^ wx.BOTTOM, 4)
            self.Frame.Layout()
            # self.Frame.Refresh()
            self.Frame.Show()
            self.Frame.SetFocus()
            if not self.Harbor.Inner.GetChildren():
                self.Harbor.GetParent().HiderR.Click()
            self.Widget.Canvas.ReDraw()

    def _RemoveFromHarbor(self):
        self.Harbor.Inner.GetSizer().Detach(self.Head)
        self.Harbor.Inner.GetSizer().Detach(self)
        self.Harbor.Inner.GetSizer().Detach(self.Sash)
        self.Harbor.SetActualSize()
        self.Harbor.ReDraw()
        self.Head.Destroy()
        self.Sash.Destroy()

    def Locate(self):
        self.Widget.Canvas.Play("LOCATE", [self.Widget for _ in range(10)])

    # --------------------------------------
    def OnClose(self):  # Key = 0
        self.Widget.dialogSize = self.Frame.GetSize()
        self.Widget.dialogPos = self.Frame.GetPosition()
        if self.Frame.minimized:
            self.Widget.dialogSize[1] = self.Frame.minimized
        self.Widget.Dialog = None
        self.Widget.Canvas.ReDraw()
        if self.detached:
            self.Frame.Play("FADEOUT")
        else:
            self._RemoveFromHarbor()
            self.Frame.Destroy()
            self.Destroy()

    def OnReady(self):  # Key = 1
        if self.OnBegin():
            self.OnClose()

    def OnApply(self):  # Key = 2
        if self.AUTO:
            self.AutoSetData()
        self.SetData()
        self.Widget.OnSetInternal()
        self.Widget.Canvas.ReDraw()

    def OnBegin(self):  # Key = 3
        if self.AUTO:
            ok = self.AutoSetData()
        else:
            ok = True
        self.SetData()
        self.Widget.OnSetInternal()
        self.Widget.OnStart()
        self.Widget.Canvas.ReDraw()
        return ok

    def OnAbort(self):  # Key = 4
        self.Widget.OnSetInternal()

    # --------------------------------------
    def AutoSetData(self):
        ok = True
        for field in self.Widget.INTERNAL:
            if isinstance(field, BaseField):
                v = field.Validate(UI.Do(self.Auto[field.key]))
                if v is None:
                    ok = False
                    self.Widget[field.key] = None
                else:
                    self.Widget[field.key] = v
        return ok

    def GetDefaultData(self, key, null):
        if self.Widget[key] is not None:
            return self.Widget[key]
        return null

    # --------------------------------------
    def AddStdButton(self, sizer):
        self[0] = UI.ToolNormal(self, size=SIZE_BTN_BOLD, pics=self.R["AP_CROSS"], edge="D", func=self.OnClose)
        if self.Widget.INCOMING:
            self[3] = UI.ToolNormal(self, size=SIZE_BTN_BOLD, pics=self.R["AP_BEGIN"], edge="D", func=self.OnBegin)
            self[4] = UI.ToolNormal(self, size=SIZE_BTN_BOLD, pics=self.R["AP_PAUSE"], edge="D", func=self.OnAbort)
            if self.Widget.IsRunning():
                self[3].Hide()
                self[4].Show()
            else:
                self[4].Hide()
                self[3].Show()
        else:
            self[1] = UI.ToolNormal(self, size=SIZE_BTN_BOLD, pics=self.R["AP_CHECK"], edge="D", func=self.OnReady)
        if self.Widget.INTERNAL:
            self[2] = UI.ToolNormal(self, size=SIZE_BTN_BOLD, pics=self.R["AP_APPLY"], edge="D", func=self.OnApply)
        subSizer = sizer if sizer.GetOrientation() == wx.HORIZONTAL else wx.BoxSizer(wx.HORIZONTAL)
        for i in (3, 4, 1, 0, 2):
            if i in self:
                subSizer.Add(self[i], 0, wx.ALL, self.MARGIN)
        if subSizer is not sizer:
            sizer.Add(subSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 0)

    # --------------------------------------
    def Initialize(self, Sizer):
        pass

    def Finalize(self, Sizer):
        self.AddStdButton(Sizer)

    def GetData(self):
        pass

    def SetData(self):
        pass