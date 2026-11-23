#!/usr/bin/env python3
"""安装或卸载当前用户的LaunchAgent；保留已有周期状态及所有本地备份。"""
import argparse
from datetime import datetime
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import time

from Run import check_path

LABEL = 'com.shuxin.navicat-reference-reset'
STORE = Path.home() / 'Library/Application Support/NavicatReferenceTimer'
AGENT = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true', help='移除定时任务，保留备份和状态')
    args = parser.parse_args()
    if os.uname().sysname != 'Darwin':
        parser.error('仅支持macOS')
    os.umask(0o077)
    for path in (STORE, AGENT):
        check_path(path)
    target = 'gui/{}/{}'.format(os.getuid(), LABEL)
    loaded = subprocess.run(['/bin/launchctl', 'print', target],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if loaded:
        subprocess.run(['/bin/launchctl', 'bootout', target], check=True)
    if args.uninstall:
        if AGENT.exists():
            AGENT.unlink()
        print('已卸载定时任务；本地配置、状态及备份保留在：' + str(STORE))
        return
    STORE.mkdir(parents=True, exist_ok=True, mode=0o700)
    AGENT.parent.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parent
    # 更新前备份旧入口与任务；不会把任何运行状态复制回源码目录。
    old = [STORE / name for name in ('Run.py', 'Run.sh', 'last-success')]
    old.append(AGENT)
    if any(path.exists() for path in old):
        backup = STORE / 'task-backups' / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid()))
        backup.mkdir(parents=True, mode=0o700)
        for path in old:
            check_path(path)
            if path.exists():
                shutil.copy2(path, backup / path.name)
    for name in ('Run.py', 'Run.sh'):
        dest = STORE / name
        check_path(dest)
        shutil.copyfile(source / name, dest)
        dest.chmod(0o700)
    stamp = STORE / 'last-success'
    check_path(stamp)
    if not stamp.exists():
        # 首次安装从此刻计时，安装本身不会立即重置。
        stamp.write_text(str(int(time.time())) + '\n')
    plist = {
        'Label': LABEL,
        'ProgramArguments': ['/bin/bash', str(STORE / 'Run.sh')],
        'RunAtLoad': True,
        'StartInterval': 3600,
        'StandardOutPath': str(STORE / 'run.log'),
        'StandardErrorPath': str(STORE / 'error.log'),
    }
    AGENT.write_bytes(plistlib.dumps(plist))
    AGENT.chmod(0o600)
    subprocess.run(['/bin/launchctl', 'bootstrap', 'gui/' + str(os.getuid()), str(AGENT)], check=True)
    subprocess.run(['/usr/bin/python3', str(STORE / 'Run.py'), '--status'], check=True)
    print('定时任务已加载：按每小时检查、13天阈值尝试处理；检测到Navicat进程时跳过。此提示不代表试用重置或授权激活。')


if __name__ == '__main__':
    main()
