@echo off
chcp 65001 >nul
title SENTINEL ISSKB - external PG
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_vm.ps1"
