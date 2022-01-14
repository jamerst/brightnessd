# brightnessd
A simple Python daemon for controlling display brightness via DDC/CI with DBus messages.

## Installation
### Dependencies
brightnessd requires the following packages to be installed:
- `monitorcontrol`
- `dasbus`

Both of these packages can be installed from PyPI with `pip`.

### Service
brightnessd is designed to be run as a user service with systemd. To set it up perform the following steps:

1. Copy `brightnessd.py` to a location in your home directory, I would recommend `~/.local/bin/`.
1. Modify the `ExecStart` line of `brightnessd.service` to point to the location of `brightnessd.py`. Note that this must be an absolute path, it cannot be relative or use variables such as `$HOME`.
1. Copy `brightnessd.service` to `~/.local/share/systemd/user/`
1. Run `systemctl --user enable brightnessd` `systemctl --user start brightnessd` to enable and start the daemon

## Usage
brightnessd supports both manual brightness changing and automatic fading. Interaction is through the `net.jtattersall.brightness` DBus Service.

### ChangeBrightness
The `net.jtattersall.brightness.ChangeBrightness(amount: int)` method allows you to change the brightness of all connected monitors by a given percentage.

**Note that calling `ChangeBrightness` will stop a fade if one is currently in progress.**

Example:
```
dbus-send --print-reply --dest=net.jtattersall.brightness /net/jtattersall/brightness net.jtattersall.brightness.ChangeBrightness int32:-5
```

This command will decrease the brightness of all monitors by 5%.

The method returns an array of integers, which is the new brightness of each monitor.

### Fade
The `net.jtattersall.brightness.Fade(target: int, time: int)` method automatically fades the brightness of all monitors to `target` over `time` seconds in steps of +-1%. This method is asynchronous, it returns early but continues to fade on a background thread.

**Note that only one fade can be in progress at once.** If `Fade` could be called again before `time` has elapsed, be sure to call `Stop` before calling `Fade`.

Example:
```
dbus-send --print-reply --dest=net.jtattersall.brightness /net/jtattersall/brightness net.jtattersall.brightness.Fade int32:20 int32:60
```

This command will change the brightness of all monitors to 20%, taking 60 seconds.

### Stop
The `net.jtattersall.brightness.Stop` method stops any fades which are currently in progress. You should make sure to call this before `Fade` if it is possible for `Fade` to be called again before the time has elapsed.

## Troubleshooting
DDC/CI can be a troublesome protocol. Some monitors just don't support it very well. Before using the daemon I would recommend using a tool like [ddcutil](https://www.ddcutil.com/) to check that your monitor supports DDC/CI and to get your environment set up correctly.

To be able to use DDC/CI without root you may have to follow [this guide](https://www.ddcutil.com/i2c_permissions/).