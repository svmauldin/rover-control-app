[app]
title = Rover Control
package.name = rovercontrol
package.domain = org.rover
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,requests
orientation = landscape
fullscreen = 1
android.permissions = INTERNET,RECORD_AUDIO,CAMERA,WAKE_LOCK
android.api = 31
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a

[buildozer]
android.pip_install_options = --break-system-packages
log_level = 2
warn_on_root = 1

# Allow pip to install packages
p4a.bootstrap_build_dir = ./build
