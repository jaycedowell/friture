#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2009 Timothée Lecomte

# This file is part of Friture.
#
# Friture is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as published by
# the Free Software Foundation.
#
# Friture is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Friture.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np
from scipy.signal import sawtooth
from PyQt5 import QtWidgets

DEFAULT_SAWTOOTH_FREQUENCY = 440.


class SawtoothGenerator:

    name = "Sawtooth"

    def __init__(self, parent):
        self.f = 440.

        self.settings = SettingsWidget(parent)
        self.settings.spinBox_sawtooth_frequency.valueChanged.connect(self.setf)

        self.offset = 0
        self.lastt = 0

    def setf(self, f):
        oldf = self.f
        self.f = f

        # the offset is adapted to avoid phase break
        lastphase = 2. * np.pi * self.lastt * oldf + self.offset
        newphase = 2. * np.pi * self.lastt * self.f + self.offset
        self.offset += (lastphase - newphase)
        self.offset %= 2. * np.pi

    def settingsWidget(self):
        return self.settings

    def signal(self, t):
        self.lastt = t[-1]
        return sawtooth(2. * np.pi * t * self.f + self.offset, width=1)


class SettingsWidget(QtWidgets.QWidget):

    def __init__(self, parent):
        super().__init__(parent)

        self.spinBox_sawtooth_frequency = QtWidgets.QDoubleSpinBox(self)
        self.spinBox_sawtooth_frequency.setKeyboardTracking(False)
        self.spinBox_sawtooth_frequency.setDecimals(2)
        self.spinBox_sawtooth_frequency.setSingleStep(1)
        self.spinBox_sawtooth_frequency.setMinimum(20)
        self.spinBox_sawtooth_frequency.setMaximum(22000)
        self.spinBox_sawtooth_frequency.setProperty("value", DEFAULT_SAWTOOTH_FREQUENCY)
        self.spinBox_sawtooth_frequency.setObjectName("spinBox_sawtooth_frequency")
        self.spinBox_sawtooth_frequency.setSuffix(" Hz")

        self.formLayout = QtWidgets.QFormLayout(self)

        self.formLayout.addRow("Frequency:", self.spinBox_sawtooth_frequency)

        self.setLayout(self.formLayout)

    def saveState(self, settings):
        settings.setValue("sawtooth frequency", self.spinBox_sawtooth_frequency.value())

    def restoreState(self, settings):
        sawtooth_freq = settings.value("sawtooth frequency", DEFAULT_SAWTOOTH_FREQUENCY, type=float)
        self.spinBox_sawtooth_frequency.setValue(sawtooth_freq)
