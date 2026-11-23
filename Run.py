#!/usr/bin/python3
"""按13天阈值尝试处理Navicat本地试用相关文件。

操作来源：https://github.com/pretend-m/navicat_for_mac_reset/blob/main/reset_navicat.sh
将目标偏好文件和匹配隐藏文件移入本机备份目录，检测到应用进程时跳过。
文件处理完成不代表试用期已重置或授权激活，实际效果须在应用内确认。
"""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime

STORE = Path.home() / 'Library/Application Support/NavicatReferenceTimer'
PREF = Path.home() / 'Library/Preferences/com.navicat.NavicatPremium.plist'
DATA = Path.home() / 'Library/Application Support/PremiumSoft CyberTech/Navicat CC/Navicat Premium'
INTERVAL = 13 * 24 * 60 * 60


def log(message):
    """记录操作阶段，不读取或输出连接配置内容。"""
    print('[{}] {}'.format(datetime.now().astimezone().isoformat(timespec='seconds'), message), flush=True)


def app_running():
    """匹配安装目录或挂载安装镜像中正在运行的Navicat。"""
    result = subprocess.run(['/usr/bin/pgrep', '-f', 'Navicat Premium.app/Contents/MacOS/'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode not in (0, 1):
        raise RuntimeError('无法检查Navicat进程，停止操作')
    return result.returncode == 0


def check_path(path):
    """拒绝目标及其父目录的符号链接，防止越出固定文件范围。"""
    for item in (path, *path.parents):
        if item.is_symlink():
            raise RuntimeError('目标路径含符号链接，停止操作')


def reset_files(now):
    """备份固定目标后移走文件；任何失败均不推进下一次执行时间。"""
    for path in (PREF, DATA, STORE):
        check_path(path)
    targets = [PREF] if PREF.exists() else []
    if DATA.is_dir():
        targets += sorted(p for p in DATA.iterdir() if re.fullmatch(r'\.[0-9A-Z]{32}', p.name))
    if not targets:
        raise RuntimeError('未发现目标文件，未更新周期起点')
    for path in targets:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError('目标不是普通文件，停止操作')
    backup = STORE / 'reset-backups' / (datetime.fromtimestamp(now).strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid()))
    backup.mkdir(parents=True, mode=0o700)
    (backup / 'manifest.json').write_text(json.dumps({
        'timestamp': now, 'targets': [str(p) for p in targets],
        'source': 'https://github.com/pretend-m/navicat_for_mac_reset/blob/main/reset_navicat.sh'
    }, ensure_ascii=False, indent=2) + '\n')
    # 检查与执行前再确认一次；不强制关闭应用或中断数据库操作。
    if app_running():
        log('Navicat已启动，顺延至退出后的下一次检查')
        return False
    for path in targets:
        path.rename(backup / path.name)
    stamp = STORE / 'last-success.tmp'
    stamp.write_text(str(now) + '\n')
    stamp.replace(STORE / 'last-success')
    log('目标文件处理完成，试用效果待应用内确认；备份：{}；下次到期：{}'.format(
        backup, datetime.fromtimestamp(now + INTERVAL).astimezone().isoformat(timespec='seconds')))
    return True


def main():
    os.umask(0o077)
    with (STORE / 'run.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        last = int((STORE / 'last-success').read_text().strip())
        now = int(time.time())
        if last <= 0 or last > now:
            raise RuntimeError('上次执行时间无效，停止操作')
        due = last + INTERVAL
        if '--status' in sys.argv or '--dry-run' in sys.argv:
            print(json.dumps({'interval_days': 13, 'due': now >= due,
                              'next_due': datetime.fromtimestamp(due).astimezone().isoformat(timespec='seconds'),
                              'navicat_running': app_running(), 'mode': 'read_only'}, ensure_ascii=False))
            return 0
        if now < due:
            return 0
        if app_running():
            log('已到13天，Navicat运行中；退出后下一次检查再处理')
            return 0
        reset_files(now)
        return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        log('任务失败，未推进下次时间：{} ({})'.format(str(exc), type(exc).__name__))
        sys.exit(1)
