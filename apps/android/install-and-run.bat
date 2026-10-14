@echo off
echo Building Chmaba POS Android App...
cd /d "%~dp0"

set ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk
set JAVA_HOME=C:\Program Files\Android\Android Studio\jbr
set PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;%PATH%

echo Checking emulator...
adb devices

echo.
echo Installing app to emulator...
adb install -r app\build\outputs\apk\debug\app-debug.apk

echo.
echo Launching app...
adb shell am start -n com.chmaba.pos/.MainActivity

echo.
echo Done! Check your emulator.
pause
