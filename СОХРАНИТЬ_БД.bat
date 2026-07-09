@echo off
title SENTINEL ISSKB - backup DB
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dpn0.ps1"
