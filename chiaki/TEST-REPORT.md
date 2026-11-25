# 原生 FPK 实测报告

- 固定上游：`70669b47a16376768001db229e3e8c3baf3e5238`。main快照与固定提交的847个未修改文件逐一相同。
- Emscripten4.0.20：真实源码307步编译 / 链接；Node v22.23.5原生进程，非运行容器。
- FPK：`chiaki-ng-web.fpk`，456880 bytes，SHA-256 `a9681418793cb45d2b8edee97bc517bfec93a5d3539d3258c0efabe860be1e31`。已解出FPK内部app.tgz，核对真实WASM与测试文件完全相同。
- WASM：641785 bytes，SHA-256 `5767df0ee6eeb63e13ef6d6723dbb6d18b57737f851e08105c62bda2ebac8fa9`，V8验证成功，34个导出。

## 原生冒烟：21项通过

- PASS Gateway HTML + COOP/COEP
- PASS Narrow www-data socket ACL
- PASS Actual www-data connection
- PASS No gateway identity rejected
- PASS Non-HTTPS rejected
- PASS Non-admin rejected
- PASS Anonymous state rejected
- PASS Malformed cookie rejected without crash
- PASS Registration disabled
- PASS Server auth + secure scoped cookie
- PASS Authenticated persistent profile
- PASS Cross-origin mutation rejected
- PASS Real WASM served
- PASS V8 WebAssembly.compile
- PASS API + WS prefix in real app.js
- PASS Emscripten JS served
- PASS Anonymous WS denied
- PASS Cross-origin WS denied
- PASS Authenticated WS POSIX binary roundtrip
- PASS Native Node HTTP health
- PASS No public TCP listener

## 生命周期

```text
status: exit 3
bad-command: exit 1
start: exit 0
start: exit 0
status: exit 0
stop: exit 0
status: exit 3
Persistent SQLite retained after stop; socket removed
start: exit 1
status: exit 3
stop: exit 0
Port conflict refused (no random/wildcard fallback)
All lifecycle shell + native Node syntax checks passed
```

## 测试边界

- 使用自有Unix socket及模拟的可信网关Header验证HTTP和WebSocket；不是fnOS真实登录会话。www-data确实在继承的应用cwd中连接socket并收到HTTP200；未修改工作区外祖先ACL。安装路径祖先遍历和真实NASHTTPS会话需父任务安装后验证。
- Node源文件UID regex实际匹配1000；WS返回101并成功执行POSIX二进制请求id42 / result0，未发现所怀疑的双转义问题。
- COOP/COEP已验证，不等于已在真实浏览器证明crossOriginIsolated或实际串流。
- Safari / iPhone未实测，SharedArrayBuffer、WebCodecs和音频/手柄兼容性不保证。
- 未获取用户PS5LinkDevice PIN，尚未配对，未宣称串流画面/音频成功。
- 所有测试原生服务及Unix socket已回收。没有生产安装、开放端口、改共享服务/防火墙/VPN或外部发布。
