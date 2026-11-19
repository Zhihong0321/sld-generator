@echo off
cd /d "%~dp0app"
if not exist node_modules call npm install
npx electron .
