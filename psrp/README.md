# PSRP Web — fnOS 原生版（x86_64）

将 [o1298098/remote-play](https://github.com/o1298098/remote-play) 的 React 前端、ASP.NET **10** 后端和独立 PostgreSQL 15 集群打包为 `psrp-web.fpk`。**运行时和本次构建均未使用 Docker**。上游 MIT 许可证保留在 `package/LICENSE` 和包内 `licenses/PSRP-MIT`。

## 运行模型与安全边界

- 应用中心依赖：`nodejs_v22`；Node 原生网关/监督器没有 npm 运行时依赖。
- 桌面入口为 `type=url` 顶层网页，统一网关 `/app/psrp-web/`，Unix Socket `${TRIM_APPDEST}/app.sock`。
- **从 fnOS HTTPS 入口打开**。不提供 HTTP 串流降级，HTTP 非安全上下文显示明确提示；不修改 NAS 证书或网关设置。顶层窗口避免 iframe 的手柄/WebHID 权限限制。
- fnOS 会话校验后，应用进一步要求 `X-Trim-Userid` 和管理员标志。PSRP 仍使用自己的用户注册/登录和 JWT，不等同于单点登录。
- 网关 Socket 仅包用户和 NAS nginx 用户 `www-data` 可读写；通过系统 `setfacl` 设置单用户 ACL，不使用 0666，不给应用附加系统组。
- ASP.NET 只监听 `127.0.0.1:10111`，独立 PG 只监听 `127.0.0.1:10112` 和私有目录 Socket。**10110 默认不监听，也没有任何匿名公网 TCP 网页入口**。不配置端口转发、防火墙、VPN、路由。
- 生命周期及常驻进程默认专用包用户 `psrp-web`，监督器明确拒绝 root。`status` 运行=0、停止=3，子服务退出时关闭整组服务；`stop` 先关闭后端串流再停 PG。
- 数据、日志、临时文件、DataProtection key 和独立 PG 数据均在 `TRIM_PKGVAR`。`secrets.json` 首次启动随机生成 PG 密码和 JWT 密钥，权限 0600；整个生命周期以 umask 077 启动。不记录密码、JWT 或 PSN 令牌。
- 只管理自己的 PG15 集群，绝不连接系统数据库。卸载不主动删除数据。升级前建议停止应用并备份整个 `TRIM_PKGVAR`，不承诺 PG 跨大版本自动升级。
- fnOS 网关是外部身份边界；本机 root/同包 UID 和 nginx UID 在可信边界内。后端的 loopback 端口仍应视为 NAS 本机可信进程接口。

## 构建（约两线程）

在 Debian12/fnOS x86_64 上运行：

```sh
chmod +x build.sh package/cmd/*
./build.sh
```

要求 Python3、curl、tar、dpkg-deb、sha256sum、fnpack（`/usr/local/bin/fnpack`）、fnOS `nodejs_v22` 和本机可读取的 `/usr/lib/postgresql/15`、`/usr/share/postgresql/15`。**不执行 apt install/upgrade，不修改系统文件**。默认使用普通网络（继承已有 `http_proxy/https_proxy`）；需要代理时显式设置 `BUILD_PROXY=http://127.0.0.1:7890`，不强制依赖构建者的本地代理。

构建固定上游 commit `24138d79f9fec10165d3dce9eebe95bc18ea5fa0`，源码 archive SHA256 `af6cdb40077e3065d32e10d0962e2598ed00fe3a39d0c835b32f55363712f02a`。已核对本次共享原件与该 commit 的后端项目、Program 和前端 lockfile 一致。下载 .NET SDK 10.0.404，发布 self-contained .NET/ASP.NET 10.0.15，不需要系统 dotnet。前端 `npm ci` 使用上游 lockfile。源码修补由 `patch-source.py` 可重复应用：Vite/Router/PWA/API/三个 SignalR Hub 前缀、登录重定向、安全上下文、HLS 同源 HTTPS 路径、健康检查、删除上游示例数据库密码和默认 JWT 密钥。

`bundle-native.py` 打包本机 PG15.15 的二进制、扩展、share 和依赖库闭包，布局可迁移；FFmpeg 使用 Debian 官方 **5.1.9** `.deb`，不复制 fnOS 自带的 nonfree mediasrv FFmpeg。PG/FFmpeg 的动态库来自当前 Debian12 主机，清单和 SHA256 在包内 `licenses/BUNDLE-INVENTORY.json`。同名库优先 `/lib/x86_64-linux-gnu`，不复制专有 GPU 驱动。

### 可复现的范围与系统依赖

包装脚本、上游 revision、npm lockfile、SDK 版本固定；**不是跨任意 Linux 的完全静态包或字节级 reproducible build**。PG、FFmpeg 依赖库随构建机 Debian12 补丁版本变化，应保存 inventory；不打包 glibc/ELF loader，要求 x86_64 Debian12 兼容 glibc >=2.36、libm、基础 NSS/时区/locale/CA 和 fnOS ACL 工具。原生 .NET 的系统 ICU/OpenSSL/Kerberos 等须与 Debian12 兼容。本机真实启动已验证。其他 fnOS 版本需安装回归，不应宣称已通用兼容。

### 第三方许可证

**另外 SIPSorcery 10.0.17 的 LICENSE 含 BSD-3-Clause 之外的地域/用途限制，不能把依赖链一概宣传为纯 MIT 或 OSI 开源。其完整许可随 NuGet notices 入包，发布与使用者必须自行核对适用范围。**

PSRP 包装代码遵循 MIT，PG 使用 PostgreSQL License，.NET 及 NuGet 各自保留发布目录中的 notices/license；FFmpeg 为 Debian GPL-enabled 构建（非 nonfree）。动态库对应 Debian copyright 文件收集在 `licenses/`。FFmpeg 对应源代码：`https://deb.debian.org/debian/pool/main/f/ffmpeg/`（ffmpeg_5.1.9 orig/debian 源包）；PG 源代码：`https://www.postgresql.org/ftp/source/v15.15/`；其余 Debian 依赖的源码包名和上游地址见各 copyright。发布方必须履行这些组件的对应源码提供和许可证义务；不要仅用 PSRP 的 MIT 描述整个二进制包。

## 安装与验收（本工作不执行系统安装）

由主任务在用户授权范围内通过 fnOS 应用中心安装 Release FPK。先安装 nodejs_v22，启动后从已登录的管理员 NAS **HTTPS** 桌面入口打开。

首次 PSRP 中注册自己的本地账户，再配置 PSN 身份。PS5 需要用户在设置中启用远程游玩并生成一次性的 **8 位配对 PIN**；PIN 必须等用户提供，不扫描/猜测、不在源码保存 PSN 凭据。实际配对后依次验证视频、音频、键盘/手柄输入、重连和停止。WebRTC 会按上游逻辑创建出站/动态 UDP 会话；本包装不设置 NAT/端口映射，跨网需要单独审查。

### 本地有界冒烟

```sh
export TRIM_APPDEST="$PWD/package/app" TRIM_PKGVAR="$PWD/test-var"
package/cmd/main start
/var/apps/nodejs_v22/target/bin/node smoke.mjs
package/cmd/main status
package/cmd/main stop
# 停止后 status 应返回3；测试产生的本地账户只在 test-var 中。
```

`smoke.mjs` 直接通过本包 Socket 模拟可信网关头，只是**本机组件级测试，不是 fnOS 登录验收**；检查真实 HTML/资源前缀、匿名拒绝、数据库迁移、注册/密码登录/JWT、三个 SignalR Hub 的 negotiate + 实际 WebSocket 101 + JSON 协议握手。注意：上游错误处理中间件可能把401转成HTTP200的 `success:false,Type:401`，测试必须检查响应内容；NAS 网关未登录也可能返回HTTP200纯文本 `invalid token`，不能称页面通过。

日志：构建 `logs/*-build.log`，原生依赖 `logs/native-bundle.log`，组件测试 `logs/smoke.log`、生命周期 `logs/lifecycle.log`，服务详细输出 `test-var/service.log`（包含随机测试账户名，但不输出测试密码/令牌；不会进入 Git/FPK）。产物 `dist/psrp-web.fpk`、`dist/SHA256SUMS`。

当前测试**不代表 PS5 配对、真实视频/音频或输入通过**。需要用户 PIN 和真实浏览器/PS5 验收。

## 官方字段依据

已读取当前官方文档，关键字段 `appname/platform/install_dep_apps/desktop_applaunchname`、`run-as=package`、`gatewayPrefix/gatewaySocket` 和可信 `X-Trim-*`：
- https://developer.fnnas.com/docs/core-concepts/manifest/
- https://developer.fnnas.com/docs/core-concepts/privilege/
- https://developer.fnnas.com/docs/core-concepts/gateway-registration/

仅上传包装脚本/patch/manifest/UI，`.gitignore` 排除上游副本、SDK、构建输出、测试数据和 FPK。大型产物应放 GitHub Releases。
