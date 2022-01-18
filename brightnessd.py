#!/usr/bin/python

import sys
import threading
from time import sleep

from dasbus.connection import SessionMessageBus
from dasbus.error import DBusError, ErrorMapper, get_error_decorator
from dasbus.identifier import DBusServiceIdentifier
from dasbus.loop import EventLoop
from dasbus.server.interface import dbus_interface
from dasbus.server.template import InterfaceTemplate
from dasbus.typing import List

from monitorcontrol.monitorcontrol import get_monitors

killed = False

ERROR_MAPPER = ErrorMapper()
BUS = SessionMessageBus(error_mapper=ERROR_MAPPER)
NAMESPACE = ('net', 'jtattersall', 'brightness')
BRIGHTNESS = DBusServiceIdentifier(
    namespace=NAMESPACE,
    message_bus=BUS
)

dbus_error = get_error_decorator(ERROR_MAPPER)

@dbus_error('BrightnessError', namespace=NAMESPACE)
class BrightnessError(DBusError):
    pass

@dbus_interface(BRIGHTNESS.interface_name)
class BrightnessInterface(InterfaceTemplate):
    def ChangeBrightness(self, amount: int) -> List[int]:
        return self.implementation.ChangeBrightness(amount)

    def Fade(self, target: int, time: int):
        self.implementation.Fade(target, time)

    def Stop(self):
        self.implementation.Stop()

class Brightness():
    ceaseFade = False
    fading = False

    def _change(self, amount: int):
        currentBrightnesses = []
        newBrightnesses = []

        try:
            monitors = get_monitors()

            for i, monitor in enumerate(monitors):
                monitor.__enter__()

                current = monitor.get_luminance()
                new = current + amount

                if (new < 0):
                    new = 0
                elif (new > 100):
                    new = 100

                currentBrightnesses.append(current)
                newBrightnesses.append(new)

            # set brightnesses separately to minimise the delay between monitors
            # DDC has a mandatory wait time, so this causes delay for each monitor when there are two DDC calls in the same loop
            for i, monitor in enumerate(monitors):
                if (newBrightnesses[i] != currentBrightnesses[i]):
                    monitor.set_luminance(newBrightnesses[i])

            return newBrightnesses

        finally:
            for monitor in monitors:
                monitor.__exit__(None, None, None)

    def _changeTo(self, amount: int, target: int, monitors: List, currentBrightnesses: List[int]):
        atTarget = True
        for i, monitor in enumerate(monitors):
            current = currentBrightnesses[i]
            if (current == target):
                atTarget = atTarget and True
                continue
            else:
                atTarget = False

            new = current + amount

            if (amount < 0 and new < target):
                new = target
            elif (amount > 0 and new >= target):
                new = target

            monitor.set_luminance(new)
            currentBrightnesses[i] = new

        return (atTarget, currentBrightnesses)

    def _doFade(self, target: int, time: int):
        print('Starting fade')
        monitors = get_monitors()

        try:
            current = []
            for monitor in monitors:
                monitor.__enter__()
                current.append(monitor.get_luminance())

            toChange = [b for b in current if b != target]
            if len(toChange) == 0:
                return

            maxBrightness = max(current)
            interval = time / abs(maxBrightness - target)
            step = -1 if maxBrightness > target else 1

            atTarget = False
            self.fading = True
            while (not atTarget and not self.ceaseFade and not killed):
                atTarget, current = self._changeTo(step, target, monitors, current)

                if (not atTarget):
                    sleep(interval)

            print('Fade complete/stopped')

        finally:
            self.ceaseFade = False
            self.fading = False

            for monitor in monitors:
                monitor.__exit__(None, None, None)

    def ChangeBrightness(self, amount: int) -> List[int]:
        self.ceaseFade = True
        return self._change(amount)

    def Fade(self, target: int, time: int):
        if self.fading:
            raise BrightnessError('Fade already in progress')

        self.ceaseFade = False
        thread = threading.Thread(target=self._doFade, args=(target, time))
        thread.daemon = True
        thread.start()

    def Stop(self):
        print('Received stop')
        self.ceaseFade = True

try:
    brightness = Brightness()

    BUS.publish_object(
        BRIGHTNESS.object_path,
        BrightnessInterface(brightness)
    )

    BUS.register_service(BRIGHTNESS.service_name)

    loop = EventLoop()
    loop.run()

finally:
    killed = True
    BUS.disconnect()