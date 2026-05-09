import sys
import os

from Core.MayaWidget import MayaWidget
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QSpinBox
import maya.cmds as mc

import importlib
import Core.MayaUtilities
importlib.reload(Core.MayaUtilities)


class AutoOverlapper:
    def __init__(self):
        self.baseController = ""
        self.delay = 2
        self.customChain = []

    def SetBaseController(self, name):
        self.baseController = name
        print("Base controller is now: " + name)

    def SetDelay(self, amount):
        self.delay = amount

    def SetCustomChain(self, chain):
        self.customChain = chain
        print("Chain set: " + str(chain))

    def IsController(self, obj):
        shapes = mc.listRelatives(obj, shapes=True) or []
        for shape in shapes:
            if mc.nodeType(shape) == "nurbsCurve":
                return True
        return False

    def GetControllerChain(self):
        if self.customChain:
            return self.customChain

        chain = [self.baseController]
        current = self.baseController

        while True:
            children = mc.listRelatives(current, children=True, type="transform") or []

            if not children:
                break

            controllerChildren = [c for c in children if self.IsController(c)]

            if not controllerChildren:
                break

            if len(controllerChildren) == 1:
                current = controllerChildren[0]

            else:
                bestChild = controllerChildren[0]
                mostChildren = 0

                for child in controllerChildren:
                    childCount = len(mc.listRelatives(child, children=True, type="transform") or [])
                    if childCount > mostChildren:
                        mostChildren = childCount
                        bestChild = child

                current = bestChild

            chain.append(current)

        return chain

    def GetKeyframeTimes(self, controller):
        attrs = mc.listAttr(controller, keyable=True) or []

        allTimes = set()

        for attr in attrs:
            try:
                keys = mc.keyframe(controller + "." + attr, query=True, timeChange=True) or []
                allTimes.update(keys)
            except:
                pass

        return sorted(allTimes)

    def GetRotationAtTime(self, controller, time):
        rx = mc.getAttr(controller + ".rotateX", time=time)
        ry = mc.getAttr(controller + ".rotateY", time=time)
        rz = mc.getAttr(controller + ".rotateZ", time=time)
        return (rx, ry, rz)

    def ApplyOverlap(self):
        print("Starting overlap!")

        chain = self.GetControllerChain()

        if len(chain) < 2:
            mc.warning("Need at least 2 controllers in the chain.")
            return

        print("Found " + str(len(chain)) + " controllers: " + str(chain))

        baseCtrl = chain[0]
        keyframeTimes = self.GetKeyframeTimes(baseCtrl)

        if not keyframeTimes:
            mc.warning("No rotation keyframes found on: " + baseCtrl)
            return

        for i in range(1, len(chain)):
            childCtrl = chain[i]
            totalDelay = self.delay * i

            activeAxes = []
            for axis in ["rotateX", "rotateY", "rotateZ"]:
                keys = mc.keyframe(baseCtrl + "." + axis, query=True, timeChange=True) or []
                if len(keys) > 1:
                    activeAxes.append(axis)

            for axis in activeAxes:
                existingKeys = mc.keyframe(childCtrl + "." + axis, query=True, timeChange=True) or []
                if existingKeys:
                    mc.cutKey(childCtrl + "." + axis, clear=True)
                mc.setAttr(childCtrl + "." + axis, 0)

            for t in keyframeTimes:
                rx, ry, rz = self.GetRotationAtTime(baseCtrl, t)
                newTime = t + totalDelay
                if "rotateX" in activeAxes:
                    mc.setKeyframe(childCtrl, attribute="rotateX", time=newTime, value=rx)
                if "rotateY" in activeAxes:
                    mc.setKeyframe(childCtrl, attribute="rotateY", time=newTime, value=ry)
                if "rotateZ" in activeAxes:
                    mc.setKeyframe(childCtrl, attribute="rotateZ", time=newTime, value=rz)

            print("Added " + str(totalDelay) + " frame delay to: " + childCtrl)

        print("Overlap done!")

    def ClearOverlap(self):
        chain = self.GetControllerChain()

        for ctrl in chain[1:]:
            for axis in ["rotateX", "rotateY", "rotateZ"]:
                existingKeys = mc.keyframe(ctrl + "." + axis, query=True, timeChange=True) or []
                if existingKeys:
                    mc.cutKey(ctrl + "." + axis, clear=True)
                mc.setAttr(ctrl + "." + axis, 0)

        print("Overlap keys cleared.")


class AutoOverlapperWidget(MayaWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Auto-Overlapper")

        self.overlapper = AutoOverlapper()

        self.mainLayout = QVBoxLayout()
        self.setLayout(self.mainLayout)

        self.mainLayout.addWidget(QLabel("HOW TO USE:"))
        self.mainLayout.addWidget(QLabel("1. Animate your base controller first."))
        self.mainLayout.addWidget(QLabel("   - Select it, go to a frame, rotate it, press S."))
        self.mainLayout.addWidget(QLabel("   - Go to a different frame, rotate to a new position, press S."))
        self.mainLayout.addWidget(QLabel("2. Select all controllers in order (base to tip)."))
        self.mainLayout.addWidget(QLabel("   - Hold Shift to select multiple."))
        self.mainLayout.addWidget(QLabel("3. Click Pick Chain below."))
        self.mainLayout.addWidget(QLabel("4. Set your delay amount in frames."))
        self.mainLayout.addWidget(QLabel("5. Click Apply Overlap."))
        self.mainLayout.addWidget(QLabel("6. Press Play to see the result."))

        self.mainLayout.addWidget(QLabel(""))

        self.controllerRow = QHBoxLayout()
        self.mainLayout.addLayout(self.controllerRow)
        self.controllerRow.addWidget(QLabel("Base Controller:"))

        self.controllerNameBox = QLineEdit()
        self.controllerRow.addWidget(self.controllerNameBox)

        self.pickBtn = QPushButton("Pick Selected")
        self.pickBtn.clicked.connect(self.PickBtnClicked)
        self.controllerRow.addWidget(self.pickBtn)

        self.chainRow = QHBoxLayout()
        self.mainLayout.addLayout(self.chainRow)
        self.chainRow.addWidget(QLabel("Influenced Chain:"))

        self.chainNameBox = QLineEdit()
        self.chainNameBox.setReadOnly(True)
        self.chainNameBox.setPlaceholderText("Select controllers in order then click Pick Chain...")
        self.chainRow.addWidget(self.chainNameBox)

        self.pickChainBtn = QPushButton("Pick Chain")
        self.pickChainBtn.clicked.connect(self.PickChainBtnClicked)
        self.chainRow.addWidget(self.pickChainBtn)

        self.delayRow = QHBoxLayout()
        self.mainLayout.addLayout(self.delayRow)
        self.delayRow.addWidget(QLabel("Delay Per Controller (frames):"))

        self.delayBox = QSpinBox()
        self.delayBox.setMinimum(1)
        self.delayBox.setMaximum(10)
        self.delayBox.setValue(2)
        self.delayBox.valueChanged.connect(self.DelayChanged)
        self.delayRow.addWidget(self.delayBox)

        self.applyBtn = QPushButton("Apply Overlap")
        self.applyBtn.clicked.connect(self.ApplyBtnClicked)
        self.mainLayout.addWidget(self.applyBtn)

        self.clearBtn = QPushButton("Clear Overlap")
        self.clearBtn.clicked.connect(self.ClearBtnClicked)
        self.mainLayout.addWidget(self.clearBtn)

    def PickBtnClicked(self):
        selected = mc.ls(selection=True, type="transform")

        if selected:
            self.controllerNameBox.setText(selected[0])
            self.overlapper.SetBaseController(selected[0])
        else:
            mc.warning("Please select a controller first.")

    def PickChainBtnClicked(self):
        selected = mc.ls(selection=True, type="transform")

        if len(selected) < 2:
            mc.warning("Please select at least 2 controllers in order.")
            return

        self.overlapper.SetCustomChain(selected)
        self.chainNameBox.setText(", ".join(selected))

        self.controllerNameBox.setText(selected[0])
        self.overlapper.SetBaseController(selected[0])

    def DelayChanged(self):
        self.overlapper.SetDelay(self.delayBox.value())

    def ApplyBtnClicked(self):
        self.overlapper.SetBaseController(self.controllerNameBox.text())
        self.overlapper.SetDelay(self.delayBox.value())

        mc.undoInfo(openChunk=True)
        self.overlapper.ApplyOverlap()
        mc.undoInfo(closeChunk=True)

    def ClearBtnClicked(self):
        self.overlapper.SetBaseController(self.controllerNameBox.text())

        mc.undoInfo(openChunk=True)
        self.overlapper.ClearOverlap()
        mc.undoInfo(closeChunk=True)

    def GetWidgetHash(self):
        return "a3f82cd1047b3e95a12f7d84c590be371fa26c8d09e4b175263ac84f1d0e7c92"


def Run():
    window = AutoOverlapperWidget()
    window.show()

Run()