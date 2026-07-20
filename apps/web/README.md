# JHAi-to-C Web

JHAi-to-C 正式前端，使用 React 19、JavaScript 和 Vite。

## 开发

```bash
npm ci
npm run dev
```

默认地址为 `http://127.0.0.1:5174`。开发服务器将 `/api` 代理到
`http://127.0.0.1:8000`，可通过 `VITE_API_PROXY_TARGET` 覆盖。

## 构建

```bash
npm run build
```

正式前端与后端 API 契约必须同步维护；不要在仓库中新增第二套平行前端。
