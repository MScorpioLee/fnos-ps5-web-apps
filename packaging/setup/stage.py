#!/usr/bin/env python3
"""Stage only packaging setup/wizards, without building or installing the app."""
from pathlib import Path
import argparse
import json
import shutil

HERE = Path(__file__).resolve().parent


def field(name, label, default=None, password=False, optional=False, pattern=None):
    result = {'type': 'password' if password else 'text', 'field': name, 'label': label}
    if default is not None:
        result['initValue'] = default
    if not optional:
        result['rules'] = [{'required': True, 'message': '请填写此项'}]
    if pattern:
        result.setdefault('rules', []).append({'pattern': pattern, 'message': '请检查输入格式'})
    return result


def stage(package, app):
    package = Path(package)
    for sub in ['app/setup', 'cmd', 'wizard']:
        (package / sub).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE / 'settings.mjs', package / 'app/setup/settings.mjs')
    shutil.copyfile(HERE / 'standalone.mjs', package / 'app/setup/standalone.mjs')
    (package / 'app/licenses').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HERE.parent.parent / 'LICENSE', package / 'app/licenses/fnos-packaging-MIT')
    # install_init runs before target files are applied; cmd/ is already available.
    shutil.copyfile(HERE / 'settings.mjs', package / 'cmd/settings.mjs')
    for action, filename in [('validate', 'install_init'), ('install', 'install_callback')]:
        script = f'''#!/bin/sh
set -eu
umask 077
: "${{TRIM_APPDEST:?}}" "${{TRIM_PKGVAR:?}}"
# No shell tracing and no secret arguments. Same lock serializes installation callbacks.
mkdir -p "$TRIM_PKGVAR"
exec 9>"$TRIM_PKGVAR/lifecycle.lock"
/usr/bin/flock -x 9
if ! /var/apps/nodejs_v22/target/bin/node "$(dirname -- "$0")/settings.mjs" {action} {app}; then
 if [ -n "${{TRIM_TEMP_LOGFILE:-}}" ]; then
  printf '%s\n' '安装设置无效：请核对账户、16–128位混合密码及确认、可用独立HTTP端口（1024–65535）。已有数据不重置。' >"$TRIM_TEMP_LOGFILE"
 fi
 exit 1
fi
'''
        (package / 'cmd' / filename).write_text(script)
        (package / 'cmd' / filename).chmod(0o755)
    # Upgrade deliberately does not consume install fields or rewrite any settings/accounts.
    for filename in ['upgrade_init', 'upgrade_callback']:
        (package / 'cmd' / filename).write_text('#!/bin/sh\n# Preserve accounts, settings, pairing and all TRIM_PKGVAR data.\nexit 0\n')
        (package / 'cmd' / filename).chmod(0o755)
    appid = 'psrp-web' if app == 'psrp' else 'chiaki-ng-web'
    account = [
        {'type': 'tips', 'helpText': '这是应用本地登录账户，不是飞牛管理员密码或 PSN 账户/PS5 配对码。入口仍须飞牛管理员会话。密码须16–128位，含大小写字母、数字及符号；确认一致由安装脚本校验。已有账户/数据在重装或升级时保留，不重置。PSRP上游无单独管理员角色，此账户受NAS管理员网关保护。' if app == 'psrp' else '这是应用本地账户，不是飞牛管理员密码或PSN/PS5配对码。入口仍须飞牛管理员会话；邮箱可用于登录。密码须16–128位并含大小写字母、数字、符号；安装脚本校验确认一致。重装/升级保留账户，不重置。'},
        field('wizard_admin_user', '本地账户名', 'admin', pattern='^[A-Za-z0-9][A-Za-z0-9_.-]{2,49}$'),

        field('wizard_admin_password', '本地账户密码', password=True),
        field('wizard_admin_confirm', '确认密码', password=True),
    ]
    ports = [
        {'type': 'tips', 'helpText': f'默认统一fnOS网关 /app/{appid}/（Unix socket）保持不变，须NAS管理员会话及可信HTTPS。端口留空=仅网关；填写=另启仅127.0.0.1监听的HTTP网页入口，供同一NAS上的Lucky/nginx HTTPS反代。域名、证书及反代由用户自行配置，本向导不设置DDNS。独立入口不使用fnOS身份头，只使用应用自身登录；禁止注册，跨域写入/WebSocket拒绝。此端口不是UDP视频端口，不会自动开NAS防火墙、UPnP、DNS或公网路由映射。数据库保持内部，不开放。'},
        field('wizard_http_port', '可选独立HTTP端口（仅回环，供反代）', '', optional=True, pattern='^[0-9]*$'),
        {'type': 'tips', 'helpText': f'反代须保留/app/{appid}/前缀及原始Host（含非标准HTTPS端口），覆盖X-Forwarded-Proto为https，转发WebSocket；写入和WebSocket的Origin须与https://Host完全一致。不能传客户端自带的代理头链，X-Forwarded-Host若存在须等于Host。TLS在反代终止，只能使用同机反代/host网络，其他主机或隔离容器不能直连回环端口。不支持任意basePath或站点根目录。独立入口不继承fnOS身份，X-Trim-*头不能绕过应用登录。'},
        {'type': 'tips', 'helpText': '网页经DDNS反代可达不等于视频可达：PSRP WebRTC媒体仍需独立ICE/STUN/TURN/NAT连通；HTTP端口不是媒体UDP端口。本向导不设置UDP范围，也不修改已有串流配置。Chiaki按上游relay/PS5协议通信。'},
    ]
    for name, data in [('install', [{'stepTitle': 'PS网页串流 (PS remote web) — 本地账户' if app == 'psrp' else '本地账户', 'items': account}, {'stepTitle': 'HTTPS网关与端口', 'items': ports}]), ('upgrade', [{'stepTitle': '保留现有数据', 'items': [{'type': 'tips', 'helpText': '升级保留本地账户密码、端口设置、配对和数据库；不会重新创建账号或自动开公网端口。请预先备份应用数据，继续使用可信HTTPS网关。'}]}])]:
        (package / 'wizard' / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('app', choices=['psrp', 'chiaki'])
    parser.add_argument('package', type=Path)
    args = parser.parse_args()
    stage(args.package, args.app)

