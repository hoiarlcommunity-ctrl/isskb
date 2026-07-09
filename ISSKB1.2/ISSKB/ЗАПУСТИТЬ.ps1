#Requires -Version 5.1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
& (Join-Path $PSScriptRoot "start.ps1")
