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
from scipy.signal import square
from PyQt5 import QtWidgets

DEFAULT_SQUARE_FREQUENCY = 440.


class SquareGenerator:

    name = "Square"

    def __init__(self, parent):
        self.f = 440.

        self.settings = SettingsWidget(parent)
        self.settings.spinBox_square_frequency.valueChanged.connect(self.setf)

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
        return square(2. * np.pi * t * self.f + self.offset)


class SettingsWidget(QtWidgets.QWidget):

    def __init__(self, parent):
        super().__init__(parent)

        self.spinBox_square_frequency = QtWidgets.QDoubleSpinBox(self)
        self.spinBox_square_frequency.setKeyboardTracking(False)
        self.spinBox_square_frequency.setDecimals(2)
        self.spinBox_square_frequency.setSingleStep(1)
        self.spinBox_square_frequency.setMinimum(20)
        self.spinBox_square_frequency.setMaximum(22000)
        self.spinBox_square_frequency.setProperty("value", DEFAULT_SQUARE_FREQUENCY)
        self.spinBox_square_frequency.setObjectName("spinBox_square_frequency")
        self.spinBox_square_frequency.setSuffix(" Hz")

        self.formLayout = QtWidgets.QFormLayout(self)

        self.formLayout.addRow("Frequency:", self.spinBox_square_frequency)

        self.setLayout(self.formLayout)

    def saveState(self, settings):
        settings.setValue("square frequency", self.spinBox_square_frequency.value())

    def restoreState(self, settings):
        square_freq = settings.value("square frequency", DEFAULT_SQUARE_FREQUENCY, type=float)
        self.spinBox_square_frequency.setValue(square_freq)
