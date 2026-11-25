# Chiaki-NG Web：fnOS 原生 FPK

**运行时无需 Docker**。Node.js 22 直接运行上游 POSIX WebSocket / SQLite 认证服务，浏览器运行本地从 C 源码编译的 Emscripten WASM。

## 上游与构建

- 上游：<https://github.com/CSystem77/Chiaki-NG-Web>
- main 固定提交：`70669b47a16376768001db229e3e8c3baf3e5238`。
- `SOURCES.json` 记录源码、三个必要子模块、mbedTLS、Opus 的版本与下载 SHA-256；再次获取时校验，不使用猜测的预编译资产。
- Opus `v1.5.2` 的 peeled commit 为 `ddbe48383984d56acd9e1ab6a090c54ca6b735a6`，下载内容另以 SHA-256 固定。
- 构建镜像固定 digest：`emscripten/emsdk@sha256:460fff8f8ac87e11b16447fbd66538a686eafa0e4fb977aa0989ed19fe2079f7`（4.0.20）。容器仅用于构建，2 CPU / 4 GiB，`CMAKE_BUILD_PARALLEL_LEVEL=2`。
- 原生 Node 服务仅使用内置模块，不需要 npm 下载运行依赖。使用 fnOS `nodejs_v22` 应用（本机实际测试 Node v22.23.5，含 `node:sqlite`）。

```sh
# Linux x86_64，Python3 + requests、Docker、fnpack；系统运行时安装 nodejs_v22。
python3 fetch-sources.py
bash build.sh
python3 smoke-test.py
python3 lifecycle-test.py
# 本机需要代理时显式设置，默认不绑定任何私人网络配置：
BUILD_PROXY=http://127.0.0.1:7890 bash build.sh
```

可设置 `FNPACK=/path/to/fnpack`。`apply-patches.py` 是幂等源码变更器；`patches/` 是对干净上游的完整差异。`stage-package.py` 生成 fnOS 工程并复制**真实编译产物**。无 Docker 权限时脚本尝试 `sudo -n docker`；离线环境需预载固定镜像及构建依赖。容器中的 apt / pip / protoc 属于构建工具，不会进入 FPK。构建可复现是指相同固定源码和变更可重建，未承诺 apt 仓库变化或打包时间戳下字节级完全相同。

## 访问与安全

- `appname=chiaki-ng-web`，桌面入口 `type=url`，顶层打开，避免 iframe 对 Gamepad / Fullscreen 的限制。
- 唯一对外路径：`https://<NAS HTTPS origin>/app/chiaki-ng-web/`。
- fnOS 统一网关转发至 `${TRIM_APPDEST}/app.sock`，mode `0660`；启动时以 socket 所有者权限设置窄 ACL `u:www-data:rw-` 和 target 目录 `u:www-data:--x`，不改共享系统组或祖先目录。网关必须传递可信 `X-Trim-Userid`、`X-Trim-Isadmin`、`X-Forwarded-Proto=https` 和正确 Host。
- 应用同时要求 **NAS 管理员身份 + 独立 Chiaki 账户认证**。无网关身份 403；非 HTTPS 426；匿名 API / POSIX WS 401；跨源修改和 WS 被拒绝。
- 内部 HTTP 只绑定 `127.0.0.1:10121`。**不开放 10120、没有 LAN / WAN wildcard listener、不会改防火墙 / 路由 / VPN / DMZ。** 端口冲突直接失败，不悄悄换端口。
- 上游自助注册关闭、WAN relay 关闭；保持上游注册 / 主机归属校验、密码 scrypt 和 SQLite session；未向前端下发 PSN 配对密钥之外的管理凭据。
- Cookie 强制 `Secure; HttpOnly; SameSite=Lax; Path=/app/chiaki-ng-web/`。
- 网关响应始终提供 COOP `same-origin`、COEP `require-corp`、CORP `same-origin`；API / WS 和绝对 URL 均处于该 prefix 下。
- 首次启动在 `${TRIM_PKGVAR}/credentials.json` 写入随机强密码（0600，父目录0700），账户 email 为 `admin@localhost`。**管理员仅通过本地 SSH / 应用 var 目录读取初始密码，不在日志或公开仓库展示。** 登录后可在上游账户页改密码；重启不会重置现有 SQLite 账户。
- 运行身份声明为 package，不加入系统特权组；无开放 API Scope / 共享目录权限。生命周期和测试均未使用 root 运行网络服务。

### 真正安装后的必测项（父任务负责）

1. 在应用中心安装 FPK（本子任务没有安装）。检查 package 用户能创建 target 下 app.sock，NAS 网关可连接0660 socket。
2. 使用 **已登录的 fnOS 管理员浏览器** 打开 HTTPS URL；检查 HTML 内容、COOP / COEP 与 WS。fnOS 未登录可能返回 **HTTP200 + `invalid token`**，这不是应用成功响应，不能只看状态码。
3. 如果返回426，不要绕过校验或公网开放端口；确认系统网关是否确实转发 HTTPS scheme。如果是403，确认可信网关 UID / admin header 和应用权限。
4. 在浏览器控制台验证 `isSecureContext === true`、`crossOriginIsolated === true`、`typeof SharedArrayBuffer === 'function'`，并等待真实 WASM 初始化。
5. 从 PS5 设置中的 Remote Play / Link Device 获取**当前用户 PIN**，再完成配对。本工程没有硬编码主机地址、账户 ID 或密钥。没有用户 PIN，因此尚未宣称实际画面 / 音频 / 手柄串流成功。

## Safari / iPhone

COOP / COEP 只是 SharedArrayBuffer 的必要部署条件，并非 Safari 兼容承诺。还取决于 Safari / iOS 版本、跨源隔离、WebAssembly pthread / shared memory、WebCodecs 支持的 codec、AudioWorklet、Gamepad 与全屏策略。上游只明确 Chrome / Edge / Firefox，Safari 未实测；本任务没有真实 Safari / iPhone 设备验证。**不能保证 iPhone Safari 可串流。** 首选桌面 Chrome / Edge，建议先用 H.264 验证。若 Safari 缺 SharedArrayBuffer / WebCodecs，FPK 或 HTTPS 本身不能补齐浏览器能力。

## 数据与生命周期

- SQLite、配对资料、初始凭据、PID、日志都放 `TRIM_PKGVAR`；不把运行秘密写入 target 或 FPK。
- `start` 幂等；`status` 停止返回3；`stop` 精确核对PID对应本应用，SIGTERM后有界回收；清理 PID/socket。
- 安装 / 升级回调幂等。卸载脚本**不删除持久目录**，卸载向导提示先备份、不要选择系统额外数据清理；应用中心自身的数据清理行为仍需在真实安装中验证。
- 复现测试使用本子目录内的临时数据，并在退出时回收自有服务。它不能代替真实 fnOS 网关会话验证。

## 验证产物

- `logs/wasm-build.log`：真实构建 / 复构建输出；`logs/ninja-compile.log` 保留首次完整 C / mbedTLS / Opus / nanopb / Chiaki 编译和链接目标记录（307步构建，日志共311个目标记录）。
- `logs/smoke-test.log` / `logs/smoke-results.json`：真实 HTML、安全拒绝、Cookie、WASM MIME/magic/hash、V8编译、WS101 + POSIX二进制请求响应、内部HTTP、loopback监听。
- `logs/lifecycle-test.log`：start/stop/status/重复start/非法动作/端口冲突。
- `TEST-REPORT.md`：可提交仓库的脱敏结果摘要。

## 发布与许可证

上游 LICENSE 为 AGPL-3.0，原有 COPYING 和各依赖许可证均随 FPK 保留在 `licenses/`。新增集成代码同样采用 AGPL-3.0；网页有可见 Source 链接。发布 FPK 时应一同提供 `chiaki-ng-web-corresponding-source.tar.gz`（固定源码、依赖、完整变更及重建脚本）；不要仅发二进制而省略对应源码。

`.gitignore` 排除上游副本、编译缓存、运行数据、大 WASM 与 FPK。仓库保留构建脚本、patch、版本/hash、许可证和文档；二进制与对应源码归档只作为 Release 附件。没有在此子目录初始化 Git、提交或发布。

## 核对的 fnOS 官方文档

实际读取并核对了以下关键字段：
- <https://developer.fnnas.com/docs/core-concepts/manifest/>：platform、install_dep_apps、checkport、desktop_applaunchname。
- <https://developer.fnnas.com/docs/core-concepts/gateway-registration/>：gatewayPrefix、gatewaySocket（仅文件名）、target/app.sock、HTTP / WebSocket prefix。
- <https://developer.fnnas.com/docs/core-concepts/dependency/>：运行依赖声明。
- <https://developer.fnnas.com/docs/core-concepts/wizard/>：tips 使用 `helpText`，不是猜测的 `content`。

`fnpack build` 已实际校验打包。该本机版本不支持 `--output`；且验证失败可能退出码0，因此脚本还会核对生成的真实 FPK。
