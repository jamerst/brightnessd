from time import sleep

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from monitorcontrol.monitorcontrol import (
    get_monitors
)

DBusGMainLoop(set_as_default=True)

class ddc(dbus.service.Object):
    ceaseFade = False
    fading = False

    def _getCurrent(self):
        brightnesses = []
        for monitor in get_monitors():
            with monitor:
                brightnesses.append(monitor.get_luminance())

        return brightnesses

    def _change(self, amount):
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

    def _changeTo(self, amount, target):
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

    @dbus.service.method('net.jtattersall.ddc', 'n', 'an')
    def ChangeBrightness(self, amount):
        self.ceaseFade = True
        return self._change(amount)

    @dbus.service.method('net.jtattersall.ddc', in_signature='in', out_signature='n', async_callbacks=('ok', 'err'),)
    def Fade(self, target, time, ok, err):
        if self.fading:
            err(dbus.exceptions.DBusException('Fade already in progress'))
            return

        try:
            monitors = [b for b in self._getCurrent() if b != target]

            if (len(monitors) == 0):
                err(dbus.exceptions.DBusException('Monitors already at target'))
                return

            maxBrightness = max(monitors)
            interval = time / abs(maxBrightness - target)
            amount = -1 if maxBrightness > target else 1

            atTarget = False
            self.fading = True
            while (not atTarget and not self.ceaseFade):
                atTarget = self._changeTo(amount, target)

                if (not atTarget):
                    sleep(interval)
        except:
            err(dbus.exceptions.DBusException('An error occurred'))
            return

        finally:
            self.fading = False

        ok(target)

    @dbus.service.method('net.jtattersall.ddc')
    def Stop(self):
        self.ceaseFade = True
        self.fading = False

bus = dbus.SessionBus()
name = dbus.service.BusName('net.jtattersall.ddc', bus)
object = ddc(bus, '/net/jtattersall/ddc')

loop = GLib.MainLoop()
loop.run()