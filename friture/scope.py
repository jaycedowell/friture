#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2009 Timoth?Lecomte

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

import logging

from PyQt5 import QtWidgets
from PyQt5.QtQuickWidgets import QQuickWidget

from numpy import log10, where, sign, arange, zeros

from friture.store import GetStore
from friture.audiobackend import SAMPLING_RATE
from friture.scope_data import Scope_Data
from friture.curve import Curve
from friture.qml_tools import qml_url, raise_if_error

SMOOTH_DISPLAY_TIMER_PERIOD_MS = 25
DEFAULT_TIMERANGE = 2 * SMOOTH_DISPLAY_TIMER_PERIOD_MS
DEFAULT_SCALE = 1.0
DEFAULT_AUTOSCALE = False

#
# These three variables control how the auto-scaling is implemented
#

# Sets how fast the auto-scaling responds to changes in the input intensity.
# Valid values are [0,1] with 0 representing do not actually auto scale and
# 1 always use the most recent auto-scale amplitude.  Values in between
# represent a weighted average between the current amplitude and the previous
# amplitude.
AUTOSCALE_ALPHA = 0.995

# Minimum amplitude scale to set.  This is useful for making sure the amplitude
# does not actually hit zero.
AUTOSCALE_MIN_SCALE = 0.015

# The jump factor controls how the auto-scale amplitude responds to a sudden
# increase in the intensity.  If the current amplitude is greater than
# AUTOSCALE_JUMP_FACTOR times the previous amplitude, then the current amplitude
# is used instead of the weighted average.
AUTOSCALE_JUMP_FACTOR = 3

class Scope_Widget(QtWidgets.QWidget):

    def __init__(self, parent, engine):
        super().__init__(parent)

        self.logger = logging.getLogger(__name__)

        self.audiobuffer = None

        store = GetStore()
        self._scope_data = Scope_Data(store)
        store._dock_states.append(self._scope_data)
        state_id = len(store._dock_states) - 1

        self._curve = Curve()
        self._curve.name = "Ch1"
        self._scope_data.add_plot_item(self._curve)

        self._curve_2 = Curve()
        self._curve_2.name = "Ch2"

        self._scope_data.vertical_axis.name = "Signal"
        self._scope_data.vertical_axis.setTrackerFormatter(lambda x: "%#.3g" % (x))
        self._scope_data.horizontal_axis.name = "Time (ms)"
        self._scope_data.horizontal_axis.setTrackerFormatter(lambda x: "%#.3g ms" % (x))

        self.setObjectName("Scope_Widget")
        self.gridLayout = QtWidgets.QGridLayout(self)
        self.gridLayout.setObjectName("gridLayout")
        self.gridLayout.setContentsMargins(2, 2, 2, 2)

        self.quickWidget = QQuickWidget(engine, self)
        self.quickWidget.statusChanged.connect(self.on_status_changed)
        self.quickWidget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.quickWidget.setSource(qml_url("Scope.qml"))
        
        raise_if_error(self.quickWidget)

        self.quickWidget.rootObject().setProperty("stateId", state_id)

        self.gridLayout.addWidget(self.quickWidget)

        self.settings_dialog = Scope_Settings_Dialog(self)

        self.set_timerange(DEFAULT_TIMERANGE)
        self.set_scale(DEFAULT_SCALE)
        self.set_autoscale(DEFAULT_AUTOSCALE)
        self.ascale = DEFAULT_SCALE
        self.autoscale_count = 0

        self.time = zeros(10)
        self.y = zeros(10)
        self.y2 = zeros(10)

    def on_status_changed(self, status):
        if status == QQuickWidget.Error:
            for error in self.quickWidget.errors():
                self.logger.error("QML error: " + error.toString())

    # method
    def set_buffer(self, buffer):
        self.audiobuffer = buffer

    def handle_new_data(self, floatdata):
        time = self.timerange * 1e-3
        width = int(time * SAMPLING_RATE)
        # basic trigger capability on leading edge
        floatdata = self.audiobuffer.data(2 * width)

        twoChannels = False
        if floatdata.shape[0] > 1:
            twoChannels = True

        if twoChannels and len(self._scope_data.plot_items) == 1:
            self._scope_data.add_plot_item(self._curve_2)
        elif not twoChannels and len(self._scope_data.plot_items) == 2:
            self._scope_data.remove_plot_item(self._curve_2)

        # trigger on the first channel only
        triggerdata = floatdata[0, :]
        # trigger on half of the waveform
        trig_search_start = width // 2
        trig_search_stop = -width // 2
        triggerdata = triggerdata[trig_search_start: trig_search_stop]

        trigger_level = floatdata.max() * 2. / 3.
        trigger_pos = where((triggerdata[:-1] < trigger_level) * (triggerdata[1:] >= trigger_level))[0]

        if len(trigger_pos) == 0:
            return

        if len(trigger_pos) > 0:
            shift = trigger_pos[0]
        else:
            shift = 0
        shift += trig_search_start
        datarange = width
        floatdata = floatdata[:, shift - datarange // 2: shift + datarange // 2]

        self.y = floatdata[0, :]
        if twoChannels:
            self.y2 = floatdata[1, :]
        else:
            self.y2 = None

        dBscope = False
        if dBscope:
            dBmin = -50.
            self.y = sign(self.y) * (20 * log10(abs(self.y))).clip(dBmin, 0.) / (-dBmin) + sign(self.y) * 1.
            if twoChannels:
                self.y2 = sign(self.y2) * (20 * log10(abs(self.y2))).clip(dBmin, 0.) / (-dBmin) + sign(self.y2) * 1.
            else:
                self.y2 = None

        self.time = (arange(len(self.y)) - datarange // 2) / float(SAMPLING_RATE)

        scaled_t = (self.time * 1e3 + self.timerange/2.) / self.timerange
        if self.autoscale:
            vmin = self.y.min()
            vmax = self.y.max()
            if self.y2 is not None:
                vmin = min([vmin, self.y2.min()])
                vmax = min([vmax, self.y2.max()])
            if -vmin > vmax:
                vmax = -vmin
            ascale = vmax - vmin
            self.ascale = AUTOSCALE_ALPHA*self.ascale + (1-AUTOSCALE_ALPHA)*ascale
            self.ascale = max([self.ascale, AUTOSCALE_MIN_SCALE])
            if ascale > AUTOSCALE_JUMP_FACTOR*self.ascale:
                self.ascale = ascale
                
            if self.autoscale_count == 0:
                self._scope_data.vertical_axis.setRange(-self.ascale/2., self.ascale/2.)
            self.autoscale_count += 1
            if self.autoscale_count > 49:
                self.autoscale_count = 0
                
            scaled_y = (self.ascale - (self.y + self.ascale) / 2.) / self.ascale
            if self.y2 is not None:
                scaled_y2 = (self.ascale - (self.y2 + self.ascale) / 2.) / self.ascale
        else:
            scaled_y = (self.scale - (self.y + self.scale) / 2.) / self.scale
            if self.y2 is not None:
                scaled_y2 = (self.scale - (self.y2 + self.scale) / 2.) / self.scale
                
        self._curve.setData(scaled_t, scaled_y)
        if self.y2 is not None:
            self._curve_2.setData(scaled_t, scaled_y2)

    # method
    def canvasUpdate(self):
        return

    def pause(self):
        return

    def restart(self):
        return

    # slot
    def set_timerange(self, timerange):
        self.timerange = timerange
        self._scope_data.horizontal_axis.setRange(-self.timerange/2., self.timerange/2.)

    # slot
    def set_scale(self, scale):
        self.scale = scale
        self.ascale = scale
        self._scope_data.vertical_axis.setRange(-self.scale/2., self.scale/2.)

    #slot
    def set_autoscale(self, autoscale):
        self.autoscale = autoscale
        self.autoscale_count = 0
        if not self.autoscale:
            self.set_scale(self.scale)

    # slot
    def settings_called(self, checked):
        self.settings_dialog.show()

    # method
    def saveState(self, settings):
        self.settings_dialog.saveState(settings)

    # method
    def restoreState(self, settings):
        self.settings_dialog.restoreState(settings)


class Scope_Settings_Dialog(QtWidgets.QDialog):

    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle("Scope settings")

        self.formLayout = QtWidgets.QFormLayout(self)

        self.doubleSpinBox_timerange = QtWidgets.QDoubleSpinBox(self)
        self.doubleSpinBox_timerange.setDecimals(1)
        self.doubleSpinBox_timerange.setMinimum(0.1)
        self.doubleSpinBox_timerange.setMaximum(1000.0)
        self.doubleSpinBox_timerange.setProperty("value", DEFAULT_TIMERANGE)
        self.doubleSpinBox_timerange.setObjectName("doubleSpinBox_timerange")
        self.doubleSpinBox_timerange.setSuffix(" ms")

        self.formLayout.addRow("Time range:", self.doubleSpinBox_timerange)
        
        self.doubleSpinBox_scale = QtWidgets.QDoubleSpinBox(self)
        self.doubleSpinBox_scale.setDecimals(1)
        self.doubleSpinBox_scale.setSingleStep(0.1)
        self.doubleSpinBox_scale.setMinimum(0.1)
        self.doubleSpinBox_scale.setMaximum(10.0)
        self.doubleSpinBox_scale.setProperty("value", DEFAULT_SCALE)
        self.doubleSpinBox_scale.setObjectName("doubleSpinBox_scale")
        self.doubleSpinBox_scale.setSuffix(" ")

        self.formLayout.addRow("Amplitude Scale:", self.doubleSpinBox_scale)
        
        self.radioButton_autoscale = QtWidgets.QRadioButton(self)
        
        self.formLayout.addRow("Auto-Scale:", self.radioButton_autoscale)

        self.setLayout(self.formLayout)

        self.doubleSpinBox_timerange.valueChanged.connect(self.parent().set_timerange)
        self.doubleSpinBox_scale.valueChanged.connect(self.parent().set_scale)
        self.radioButton_autoscale.toggled.connect(self.parent().set_autoscale)
        self.radioButton_autoscale.toggled.connect(self.toggle_scale)

    # slot
    def toggle_scale(self, autoscale):
        self.doubleSpinBox_scale.setEnabled(not autoscale)
        
    # method
    def saveState(self, settings):
        settings.setValue("timeRange", self.doubleSpinBox_timerange.value())
        settings.setValue("scale", self.doubleSpinBox_scale.value())
        settings.setValue("autoscale", self.radioButton_autoscale.isChecked())

    # method
    def restoreState(self, settings):
        timeRange = settings.value("timeRange", DEFAULT_TIMERANGE, type=float)
        self.doubleSpinBox_timerange.setValue(timeRange)
        scale = settings.value("scale", DEFAULT_SCALE, type=float)
        self.doubleSpinBox_scale.setValue(scale)
        autoscale = settings.value("autoscale", DEFAULT_AUTOSCALE, type=bool)
        self.radioButton_autoscale.setChecked(autoscale)
