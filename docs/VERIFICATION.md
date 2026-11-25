# 预览版验收范围

测试环境：fnOS **1.2.1102**，x86_64 / Debian 12。以下是已执行的结果，不是仅按设计推断。

## 设备上的安装验收

| 检查 | PSRP | Chiaki-NG-Web |
|---|---|---|
| 实际 FPK 构建、应用中心安装到存储空间2 | 通过 | 通过 |
| 应用中心停止 → stopped → 启动 → running | 通过 | 通过 |
| 重启应用后随机密钥/初始凭据不变 | 通过 | 通过 |
| 长期服务使用各自 package UID、不是 root | 通过 | 通过 |
| 未认证网关请求拒绝；非管理员拒绝 | 通过 | 通过 |
| 本地 Unix Socket 返回真实 HTML 与 JS/CSS，而不是 fnOS 的 `invalid token` 占位响应 | 通过 | 通过 |
| 网页资源路径保持在各自 `/app/…/` 前缀 | 通过 | 通过 |
| 实际 nginx/www-data 用户可连接安装后的 Unix Socket | 通过 | 通过 |
| 安装实例本地账户登录、认证态读取及退出 | 未新建用户测试 | 通过；Cookie 为 Secure/HttpOnly/SameSite=Lax 且限定应用路径 |
| 运行时不启动 Docker 容器 | 通过 | 通过 |
| 本地真实 WASM magic / MIME / 加载 | 不适用 | 通过 |
| COOP / COEP 响应头 | 非该实现的必要条件 | 通过 |

PSRP 的安装实例包含原生 Node 监督器、ASP.NET 后端和独立 PostgreSQL；Chiaki 安装实例为原生 Node 服务。内部 TCP 仅本地回环，不通过本工程添加公网监听或路由器映射。

## 构建目录内的组件测试

- PSRP：独立 PG 初始化/迁移、注册与登录/JWT、三个 SignalR Hub 的 negotiate、真实 WebSocket 101 与 JSON 协议握手；过期 PID、重复启动、端口冲突和停止回收等测试。测试数据与真实安装数据分离。
- Chiaki：HTML、安全头、匿名/非管理员/非HTTPS/跨源拒绝、Secure/HttpOnly/prefix Cookie、真实 WASM 和 V8 编译、WebSocket 101 与 POSIX 二进制往返等 21 项测试；生命周期与端口冲突测试。
- 公共发布检查器：5 项单元测试通过，发布索引未发现所检查的令牌格式、数据库或大型运行产物。

详细组件测试方法与限制见各应用 README。这些测试不绕过或替代主机配对。

## 尚未验证

以下项目必须保持为 **未验证**，不能因网页或 WebSocket 通过便标记成功：

- 使用已登录的真实 NAS 浏览器完成桌面入口全流程；本地 Unix 测试使用可信网关头模拟管理员上下文。
- 用户 PS5 的当前配对 PIN、PSN 身份与会话认证。
- 实际游戏视频、声音、音画同步。
- 实体/虚拟手柄、按键释放、触摸板、震动和自适应扳机。
- iPhone Safari / Mac Safari 的真实浏览器兼容性。
- 跨外网、断线重连与长时间稳定性。
- 卸载时 fnOS 自身的数据清理选项；本工程的卸载脚本不主动删除持久数据。

首次使用需要在 PS5 上开启远程游玩并获取配对码。请在准备好配对时再生成，不应将 PIN、PSN 令牌或配对密钥提交 GitHub。
