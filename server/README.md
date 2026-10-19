# platform2 server

FastAPI 后端。默认连接本机 PostgreSQL `platform2`（`postgresql+psycopg://platform2@127.0.0.1:5432/platform2`），启动时建表、补注册表列并造数。AI SSE 默认转发到 `http://127.0.0.1:3080`（真 `dsh` 或 harness-bridge）。官方 Dify 在 `http://127.0.0.1:5001`；管理员于 `/admin/dify` 登记关键字与 API Key 后，由 `scripts/dify-mcp` 供 `dsh` 按关键字调用。`PLATFORM2_USE_MOCK_AI=true` 可改回进程内 mock。

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

默认账号：
- operator / operator
- admin / admin
