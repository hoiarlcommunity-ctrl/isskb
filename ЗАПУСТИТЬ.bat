@echo off
chcp 65001 >nul
title SENTINEL ISSKB
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
