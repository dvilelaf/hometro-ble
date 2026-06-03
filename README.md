# HomeTro BLE

A small local web app to control a HomeTro treadmill from your browser over Bluetooth LE.

Use it to find and connect to the treadmill, set the target speed, start, pause, resume, stop, and see workout stats like speed, distance, time, and calories.

## Use

From the cloned repo, start the app and open the browser:

```bash
just start
```

Server-only mode:

```bash
just run
```

When you are done, stop it:

```bash
just stop
```

Safety note: the app sends real treadmill commands. Test with the treadmill empty, keep the safety key attached, and start at a low speed.
