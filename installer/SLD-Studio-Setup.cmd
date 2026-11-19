@echo off
title SLD Studio setup
echo Installing SLD Studio (Solar ATAP SLD generator) ...
echo This downloads the latest version from GitHub. It takes a few minutes the first time.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Zhihong0321/sld-generator/main/install.ps1 | iex"
echo.
pause
