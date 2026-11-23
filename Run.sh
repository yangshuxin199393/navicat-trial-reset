#!/bin/bash
# 保留原LaunchAgent入口；所有周期判断、进程保护和备份由同目录脚本处理。
set -eu
umask 077
exec /usr/bin/python3 "$HOME/Library/Application Support/NavicatReferenceTimer/Run.py" "$@"
