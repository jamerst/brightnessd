#!/usr/bin/python

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

    def _getCurrent(self):
        brightnesses = []
        for monitor in get_monitors():
            with monitor:
                brightnesses.append(monitor.get_luminance())

        return brightnesses

    def _change(self, amount: int):
        brightnesses = []
        for monitor in get_monitors():
            with monitor:
                current = monitor.get_luminance()
                new = current + amount

                if (new < 0):
                    new = 0
                elif (new > 100):
                    new = 100

                brightnesses.append(new)

                if (new != current):
                    monitor.set_luminance(new)

        return brightnesses

    def _changeTo(self, amount: int, target: int):
        atTarget = True
        for monitor in get_monitors():
            with monitor:
                current = monitor.get_luminance()
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

        return atTarget

    def _doFade(self, step: int, target: int, interval: int):
        print('Starting fade')
        try:
            atTarget = False
            self.fading = True
            while (not atTarget and not self.ceaseFade):
                atTarget = self._changeTo(step, target)

                if (not atTarget):
                    sleep(interval)

            print('Fade complete/stopped')
        except:
            print('Fade error')
        finally:
            self.ceaseFade = False
            self.fading = False

    def ChangeBrightness(self, amount: int) -> List[int]:
        print(f'Changing brightness by {amount}%')
        self.ceaseFade = True
        return self._change(amount)

    def Fade(self, target: int, time: int):
        if self.fading:
            raise BrightnessError('Fade already in progress')

        monitors = [b for b in self._getCurrent() if b != target]

        if (len(monitors) == 0):
            return

        maxBrightness = max(monitors)
        interval = time / abs(maxBrightness - target)
        step = -1 if maxBrightness > target else 1

        self.ceaseFade = False
        thread = threading.Thread(target=self._doFade, args=(step, target, interval))
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
    BUS.disconnect()