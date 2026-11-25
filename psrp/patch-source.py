#!/usr/bin/env python3
"""Idempotent fnOS integration patch; run against a private upstream copy."""
from pathlib import Path
import json,sys
p=Path(sys.argv[1] if len(sys.argv)>1 else 'source')
f=p/'RemotePlay.Web/vite.config.ts'; s=f.read_text(); s=s.replace("export default defineConfig({", "export default defineConfig({\n  base: '/app/psrp-web/',") if "base: '/app/psrp-web/'" not in s else s
s=s.replace("start_url: '/'", "start_url: '/app/psrp-web/'").replace("scope: '/'", "scope: '/app/psrp-web/'").replace("[/^\\/api/, /^\\/hubs/, /^\\/swagger/]", "[/\\/api(?:\\/|$)/, /\\/hubs(?:\\/|$)/, /\\/swagger(?:\\/|$)/]")
f.write_text(s)
f=p/'RemotePlay.Web/src/App.tsx';s=f.read_text().replace('<BrowserRouter>', '<BrowserRouter basename="/app/psrp-web">');f.write_text(s)
(p/'RemotePlay.Web/.env').write_text('VITE_API_BASE_URL=/app/psrp-web/api\n')
for f in p.rglob('appsettings*.json'):
 d=json.loads(f.read_text()); d.pop('Database',None); d.pop('ConnectionStrings',None)
 if 'JWT' in d:d['JWT'].pop('Secret',None)
 f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
f=p/'RemotePlay/Program.cs';s=f.read_text().replace('builder.Logging.SetMinimumLevel(LogLevel.Debug);','builder.Logging.SetMinimumLevel(LogLevel.Information);')
s=s.replace('var app = builder.Build();','var app = builder.Build();\napp.MapGet("/healthz", () => Results.Ok(new { status = "ok" }));') if 'app.MapGet("/healthz"' not in s else s
f.write_text(s)
# Root redirects and HLS URLs must remain inside the HTTPS gateway prefix.
f=p/'RemotePlay.Web/src/utils/auth-invalidation.ts';s=f.read_text().replace("window.location.replace('/login')", "window.location.replace('/app/psrp-web/login')");f.write_text(s)
f=p/'RemotePlay/Controllers/PlayStationController.cs';s=f.read_text().replace('var publicUrl = $"/hls/', 'var publicUrl = $"/app/psrp-web/hls/');f.write_text(s)
f=p/'RemotePlay/Middleware/HlsPathFixMiddleware.cs';s=f.read_text().replace('var baseUrl = $"{context.Request.Scheme}://{context.Request.Host}{dirPath}";', 'var baseUrl = $"/app/psrp-web{dirPath}";');f.write_text(s)
f=p/'RemotePlay.Web/src/main.tsx';s=f.read_text()
if 'window.isSecureContext ?' not in s:s=s.replace('<App />','{window.isSecureContext ? <App /> : <main><h1>PSRP requires HTTPS</h1><p>请从 fnOS 的 HTTPS 统一网关打开；WebCodecs、音频和手柄需要安全上下文。</p></main>}')
f.write_text(s)
# Block unsafe HTTP browser use with an explicit secure-context notice.
f=p/'RemotePlay.Web/index.html'; s=f.read_text()
notice='<script>if(!window.isSecureContext){document.addEventListener("DOMContentLoaded",()=>{document.getElementById("root").innerHTML="<h2>PSRP requires HTTPS</h2><p>Please open the fnOS HTTPS gateway. WebCodecs, audio and gamepad APIs require a secure context.</p>";});}</script>'
if 'PSRP requires HTTPS' not in s:s=s.replace('</head>',notice+'\n</head>')
f.write_text(s)
