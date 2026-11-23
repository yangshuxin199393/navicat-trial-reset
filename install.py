#!/usr/bin/env python3
"""安装或卸载当前用户的LaunchAgent；保留已有周期状态及所有本地备份。"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import time

from Run import check_path, read_interval_days, validate_interval_days

LABEL = 'com.shuxin.navicat-reference-reset'
STORE = Path.home() / 'Library/Application Support/NavicatReferenceTimer'
AGENT = Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true', help='移除定时任务，保留备份和状态')
    parser.add_argument('--interval-days', type=int, help='重置检查的间隔天数，1至365；首次安装默认13天，更新时保留现有配置')
    args = parser.parse_args()
    if os.uname().sysname != 'Darwin':
        parser.error('仅支持macOS')
    if args.uninstall and args.interval_days is not None:
        parser.error('--uninstall不能与--interval-days同时使用')
    os.umask(0o077)
    for path in (STORE, AGENT):
        check_path(path)
    source = Path(__file__).resolve().parent
    config_path = STORE / 'config.json'
    # 在停用旧任务前校验配置；显式参数允许修复已有的非法配置。
    interval_days = None
    if not args.uninstall:
        check_path(config_path)
        if args.interval_days is not None:
            try:
                interval_days = validate_interval_days(args.interval_days)
            except ValueError as exc:
                parser.error(str(exc))
        else:
            interval_days = read_interval_days(config_path if config_path.exists() else source / 'config.json')
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
    # 更新前备份旧入口与任务；不会把任何运行状态复制回源码目录。
    old = [STORE / name for name in ('Run.py', 'Run.sh', 'last-success', 'config.json')]
    old.append(AGENT)
    if any(path.exists() for path in old):
        backup_root = STORE / 'task-backups'
        check_path(backup_root)
        backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup = Path(tempfile.mkdtemp(prefix=datetime.now().strftime('%Y%m%d-%H%M%S') + '-', dir=backup_root))
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
    # 原子替换配置，保留周期起点；后续检查会按新的间隔重新计算到期时间。
    config_tmp = STORE / 'config.json.tmp'
    check_path(config_tmp)
    config_tmp.write_text(json.dumps({'interval_days': interval_days}, indent=2) + '\n', encoding='utf-8')
    config_tmp.replace(config_path)
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
    print('定时任务已加载：按每小时检查、{}天阈值尝试处理；检测到Navicat进程时跳过。此提示不代表试用重置或授权激活。'.format(interval_days))


if __name__ == '__main__':
    main()
