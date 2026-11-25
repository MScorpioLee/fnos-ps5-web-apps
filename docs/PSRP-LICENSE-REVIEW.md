# PSRP FPK 有界发布前审查

补充：下文针对初始预览包，不是最新源码的放行报告。后续已将版权告知收集改为失败即退出，并实际触发了测试机缺少 `libstdc++6` copyright 的阻断；没有跳过该检查公开二进制。Release 的 PSRP 源码附件包含后续包装脚本修正，文件项数及 SHA256 以 Release 的 `SHA256SUMS` 为准。

结论：**建议暂缓公开当前 PSRP 二进制 FPK；可以先公开已清理的 PSRP 源码/包装工程。** 已取得 FFmpeg 精确 Debian 对应源码，但尚未覆盖整个二进制依赖闭包的源码提供和许可告知义务。本报告不是法律意见，也不声明完全合规。

## 已验证与产物

- 检查目标 `psrp/dist/psrp-web.fpk`，SHA256 `8dabb2fe6f6355d8df3faf3f3ec9be8e70d3d1508b3e8fe63ca80998776ee905`。直接流式查看 FPK 的 app.tgz（4325 项），没有改变原包。
- 实际运行随包 `ffmpeg -version`，确认 5.1.9-0+deb12u1、`--enable-gpl`、未见 `--enable-nonfree`。不能将其称为纯 LGPL 或整个包纯 MIT。
- `ffmpeg-5.1.9-debian-corresponding-source.tar.gz`：实际下载 Debian `ffmpeg_5.1.9.orig.tar.xz`、签名、`ffmpeg_5.1.9-0+deb12u1.debian.tar.xz`、`.dsc`，原始/补丁档均按 dsc SHA256 检验；未独立验证 Debian/OpenPGP 签名。
- `psrp-modified-source-fnos.tar.gz`：414 项，约 5MB，包括已修补上游源码、MIT LICENSE、npm lockfile、构建说明、patch/bundle/finalize/notices 脚本、包装配置及网关源码。不含 node_modules/bin/obj/dist/.git、SDK/NuGet 二进制、test-var/日志或部署 secrets；检查 appsettings，没有数据库密码/JWT 密钥。并非完整通用秘密扫描。
- `psrp-native-source-index-and-notices.tar.gz`：系统 Debian notices、精确二进制/源码版本映射、已取得的 dsc 和对应源码 URL/校验值清单。**不是完整依赖源码归档。**
- `SHA256SUMS` 为三个附件的 SHA256。各文件均在本目录；未上传 GitHub。

## 明显缺口 / 发布门槛

1. **当前 FPK 缺少动态库版权告知。** 包中仅存在 `licenses/ffmpeg-copyright`、`licenses/postgresql-15-copyright`，没有 `licenses/debian-*-copyright`。`bundle-native.py` 无权限运行 dpkg-query 时静默跳过；本次普通用户确实遇到 `/var/lib/dpkg/info/format: Permission denied`。独立审查通过只读 sudo 查询补齐了本目录 notices，但这不会修复已打包 FPK。应在父工程明确收集失败即退出、重打包，再检查最终 FPK；至少提供完整随包/伴随材料，不能继续声称原 FPK 已保留这些动态库 notices。
2. **仅给 Debian pool 首页、上游 URL 和包装脚本，不足以证明完成 GPL/LGPL 对应源码提供。** 已映射 201 个二进制包；对 copyright 中出现 GPL/LGPL 字样者保守选择 103 个精确源码包（含部分仅构建工具/文档带 GPL 字样的宽松许可包，不等同 103 个实际 GPL 链接义务）。102 个精确源码包已得到文件清单，99 个从 Debian dsc 取得 SHA256，3 个通过 snapshot API 取得文件 URL/SHA1；仅 FFmpeg 全量下载。其余 pool 清单声明的源码文件合计约 680MB，5分钟内没有下载/重建整个闭包。若发布二进制，建议将对应源码同 Release 持久托管并明确定位，或采用经过核对、满足各许可证的其他有效源码提供方式；不要把第三方 URL 等同于发布方已完成义务。
3. **Mesa 精确源码尚未解决。** 随包 `libgbm.so.1` 对应本机 `libgbm1 26.1.6-1~bpo12+1`，主 Debian、安全仓库与 snapshot 精确版本查询未找到源包。该包被保守命中 GPL 文本，不代表已判定 libgbm 自身 GPL；仍需确认其实际来源/适用许可与需要保留的告知。不要虚构为官方可下载源码。
4. `libpulsecommon-16.1.so` 初始自动映射未命中（文件位于 pulseaudio 子目录）；追加只读查询确认属于 `libpulse0:amd64`，其 source `pulseaudio` 已在源码清单。其余被映射库均与对应本机 `/lib/x86_64-linux-gnu` 文件 SHA256 一致；未对所有 PG 扩展/bitcode、.NET 原生库做穷尽归属分析。
5. .NET10、NuGet、npm notices 虽已存在，但未穷尽核对其每个运行时/原生组件、所有许可证 URL 是否有完整正文、是否存在下载时失效或重链接条件。本次不以 PSRP MIT 覆盖它们。PG15.15 的 snapshot 精确源码列表已补到 manifest；PG 本身为 PostgreSQL License，不能因此免除 PG 闭包内其他组件义务。
6. 已直接读取 `SIPSorcery 10.0.17 LICENSE.md`：其附加限制针对以色列/占领区及相关用途，**不是中国禁用**；区域外条款允许商业使用及无强制衍生许可。应保留全文，明确这不是无条件 OSI 许可依赖；全球发布仍需审查地域分发边界。不在本审查中武断认定 MIT PSRP 与独立进程 FFmpeg 组成同一 GPL 衍生作品。

## 可执行发布选择

- **现在可做：** 公开 PSRP 已修改源码附件、包装工程和本审查材料；暂不发布现 FPK。源码附件只适用于 PSRP/包装源码，不是所有 bundled third-party 的完整 Corresponding Source。
- **二进制放行前：** 修复/验证动态库 notices；冻结精确依赖版本与来源；补齐实际需要提供的 GPL/LGPL 源码（含 Debian patches/build files）、构建/安装控制脚本及适用重链接/替换条件；核对 .NET/NuGet/native 组件告知；解决 Mesa 来源。随后重新打包、生成新 SHA256，并在 Release 关联同版本源码和许可材料。
- FFmpeg 源码重建入口：解开本附件，在包含 orig/debian 的目录运行 `dpkg-source -x ffmpeg_5.1.9-0+deb12u1.dsc`；在隔离 Debian12 构建环境按 `debian/control` 安装 Build-Depends 后执行 `dpkg-buildpackage -us -uc`（本次没有安装依赖/执行重建）。包装脚本现从本机复制 PG/依赖，并非所有依赖的可复现构建脚本；保留的 Debian 源包提供各自构建规则。

范围：只写 release-compliance/；未修改 psrp/chiaki 成品、服务或系统；未处理 Chiaki 已有的 AGPL 源码附件。

