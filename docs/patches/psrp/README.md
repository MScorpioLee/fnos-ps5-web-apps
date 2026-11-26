# PSRP：固定上游与可重放修补

这是 **PS remote web / PS网页串流** 的 PSRP 对应源码入口，不是仅含包装脚本的发布。Chiaki 仍使用 `chiaki/SOURCES.json`、`chiaki/patches/` 与其现有 AGPL 对应源码流程；本目录没有替换或重新许可 Chiaki。

## 来源与顺序

- 上游：<https://github.com/o1298098/remote-play>
- 精确 commit：`24138d79f9fec10165d3dce9eebe95bc18ea5fa0`
- GitHub codeload 归档 SHA256：`af6cdb40077e3065d32e10d0962e2598ed00fe3a39d0c835b32f55363712f02a`
- `manifest.json` 固定归档 URL、三个 patch 的 SHA256、每层修改路径及最终 **446 个源码文件**的 SHA256。不是安装包、SDK、node_modules 或运行数据清单。

按序应用，不要把第 2 份历史累计 patch 当成相对干净上游的完整 diff：

1. `0001-fnos-network-codec-baseline.patch`：上游 → 历史 lifecycle 工作开始前的基线，保留 fnOS 路径、安全上下文、配置清理、STUN/DNS、H264/Safari/媒体就绪等既有修补和回归测试。
2. `0002-cumulative-lifecycle.patch`：该基线 → 历史累计 `source.patch` 的完整重放结果，包含租约、会话接管/回收、权限、输入授权、取消与媒体原子切换等累计后端及前端修复。导出时实际先重放旧 `source.patch`，按旧 source-changes 的全部 48 项 SHA256 核对；不是只取某轮 review-fix。
3. `0003-latest-browser-controls.patch`：累计结果 → 当前前端；包含全屏按钮、统计诊断、键盘/实体手柄、触屏布局/多点触控、混合输入及测试，共 24 个变动文件。

三层各为 31 / 48 / 24 个变动文件（存在跨层重叠，不是相加后的唯一文件数）。全部生产源码均与导出时被忽略的 `psrp/source` **字节一致**；没有修改工作副本的 streaming 源码。

### 仅测试工具的公开化处理

`manifest.json.test_path_normalizations` 列出 15 个测试文件：去掉构建主机的绝对路径；Chromium 改用 `CHROMIUM_PATH`（不设置时使用 Playwright 默认浏览器）；测试服务使用相对路径；截图目录可用 `PSRP_TEST_EVIDENCE` 指定。网络单测地址使用文档地址；可选真实 STUN 集成必须由运行者显式设置自己的 `PSRP_WEBRTC_BIND_ADDRESS` / `PSRP_WEBRTC_DNS_SERVER`，不会内置部署设备地址。这些是导出副本的测试修整，不是生产源码改动。原始工作副本 hashes 仅留在仓库外的本地审计材料中。

Patch 第 1 层的删除行中可见**固定上游归档自带**的示例数据库地址/密码、示例 JWT 与 Vite 地址，均逐项核对来源，不是部署凭据；补丁移除这些默认配置。测试中的 `alice`、`lease-B`、`candidate` 与最小 `v=0` 无效 SDP 是隔离 fixture，不含真实会话、设备身份、SDP 协商记录或配对数据。

## 一键恢复与 hash 验证

在仓库根目录运行（目标必须不存在；验证脚本拒绝覆盖）：

```sh
python3 docs/patches/psrp/verify-replay.py /tmp/psrp-restored
# 有已下载归档时，可完全离线重放：
python3 docs/patches/psrp/verify-replay.py /tmp/psrp-restored-offline \
  --archive /path/to/upstream.tar.gz
```

脚本验证归档 SHA256、检查提取路径、逐层 `git apply --check` / `git apply`，再校验完整文件集合及每个 SHA256、上游 LICENSE。失败不生成目标副本。不会启动服务、触碰生产数据、连接 PS5、创建 Git commit 或上传文件。

**干净 checkout 构建必须先恢复这些修补。** 现有 `psrp/build.sh` 只自动运行早期 `patch-source.py`，不会自动应用本目录三层 patch，不能声称直接运行旧 build.sh 就包含当前全部功能。确认 `psrp/source` 不存在后，可将上述恢复目标设为 `psrp/source`，再按 `psrp/README.md` 的环境/许可要求构建；不要在已有源码副本上重复应用这些 patch。包装/setup 正在独立审查，本目录没有更改该构建流程。

可先在恢复的独立副本执行：

```sh
# 已安装 .NET 10 SDK，且已按项目依赖恢复；默认回归不连接 PS5：
dotnet run --project /tmp/psrp-restored/RemotePlay.RegressionTests
cd /tmp/psrp-restored/RemotePlay.Web
npm ci --no-audit --no-fund
node node_modules/typescript/bin/tsc --noEmit
node --test tests/streaming-diagnostics.test.mjs
node tests/touch-controller-service.cjs
```

其他隔离浏览器/真实 loopback WebRTC 测试见恢复后的 `RemotePlay.Web/tests/README-lifecycle.md`。测试需自己的 Playwright/Chromium 环境，和虚拟测试端口；不应运行生产 Program 或复用生产数据库。源码重放、TypeScript、fixture 测试都不等于 PS5 实机串流或 iOS 兼容性验收，也不证明字节级可复现二进制。

## 许可证与发布边界

固定上游 `LICENSE`（2025 PSRP contributors，MIT）逐字保留，并由 manifest 校验；补丁旁同时提供逐字副本 [`UPSTREAM-LICENSE.txt`](UPSTREAM-LICENSE.txt)。PSRP 修改代码继续按该上游 MIT 提供，不以仓库根部原创包装/文档的 MIT 署名替换上游版权。Chiaki、.NET、NuGet、npm、PG、FFmpeg 与其他组件仍遵循各自许可证。特别是 SIPSorcery 附加地域/用途条件，不应将依赖链宣传为纯 MIT 或全部 OSI 开源。

**PSRP 二进制 FPK 继续 HOLD**：本源码修补交付不解决所有打包依赖的对应源码、notices 与发布许可缺口。见 [许可证审查](../../PSRP-LICENSE-REVIEW.md)。本目录不包含 FPK、编译产物、SDK、生产 var、凭据、私人日志、抓包或 SDP 记录。
