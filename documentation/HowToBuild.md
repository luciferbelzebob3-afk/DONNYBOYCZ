# Build DONNY BOY firmware (version 1.0.0)

This repository builds the DONNY BOY firmware. The default firmware branding is configured in `fbt_options.py`:

- `FIRMWARE_ORIGIN = "DONNY BOY"` — firmware origin shown in device version information.
- `DIST_SUFFIX = "1.0.0"` — build/distribution version identifier.
- `UPDATE_VERSION_STRING = "1.0.0"` — version embedded in the updater package.
- `scripts/version.py` identifies this fork as `https://github.com/luciferbelzebob3-afk/unleashed-firmware-CZ.git`.

## Requirements

- Git
- Python version supported by the repository's build system
- The toolchain dependencies downloaded/managed by FBT
- For Windows, use PowerShell or the terminal supplied with Git

## Clone the repository

Clone this fork with all submodules:

```sh
git clone --recursive https://github.com/luciferbelzebob3-afk/unleashed-firmware-CZ.git
cd unleashed-firmware-CZ
```

If the repository is already cloned, run:

```sh
git submodule update --init --recursive
```

## Build on Windows

Run from the repository root in PowerShell:

```powershell
git submodule update --init --recursive
.\fbt.cmd COMPACT=1 DEBUG=0 DIST_SUFFIX=1.0.0 UPDATE_VERSION_STRING=1.0.0 updater_package
```

## Build on Linux/macOS

Run from the repository root:

```sh
git submodule update --init --recursive
./fbt COMPACT=1 DEBUG=0 DIST_SUFFIX=1.0.0 UPDATE_VERSION_STRING=1.0.0 updater_package
```

## Output and verification

Check the `dist/` directory for the generated updater package. The package name includes the hardware target and version suffix. Verify that the command finishes successfully and that the output archive exists before installing it on the Flipper Zero.

For troubleshooting and other FBT targets, see [fbt.md](fbt.md).

## Build a single external app

This builds an application, not the whole firmware:

```sh
./fbt COMPACT=1 DEBUG=0 launch_app APPSRC=applications_user/yourplugin
```

On Windows, use `./fbt.cmd` instead of `./fbt`.
