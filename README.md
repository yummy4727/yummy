# paotuan — AI互动叙事平台 · 客户端

「剧本跑团」软件本体（游戏引擎）。加载创作者发布的「剧本项目文件（.zip）」，通过 LLM 驱动叙事，在安全沙箱中执行剧本附带脚本。

架构与需求详见项目根目录：
- `项目需求文档.txt` — 产品需求 V1.0
- `ARCHITECTURE.md` — 架构设计 V1.3

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
python -m paotuan --script examples/demo_story.zip
```

首次使用在「设置」中完成 LLM 接入：**选服务商 → 选模型 → 粘贴 API Key → 测试连接**。
内置 OpenCode Zen / OpenCode Go（月卡） / DeepSeek / OpenAI / Kimi / 智谱 GLM / 通义千问 / SiliconFlow / OpenRouter / Anthropic Claude / Google Gemini 等主流服务商预设
（预填接口地址与模型列表，支持任意 OpenAI 兼容接口的自定义服务商），旧配置会自动迁移。

每次保存的「API 配置」会以名称归档，**同一服务商可保存多条（多 Key / 多账号）**；
工具栏可一键在已保存的配置之间切换，切换后自动重建 AI 会话。

## 示例剧本

`examples/build_demo.py` 可将 `examples/demo_story/` 源码打包为 `examples/demo_story.zip`，
其中 `scripts/` 下的 `*.py` 是沙箱内执行的剧本脚本（白名单只允许 `run(state, **kwargs)` 定义与状态读写）。

## 开发

```bash
python examples/build_demo.py     # 重新生成示例剧本 zip
pytest                            # 运行测试（含沙箱逃逸 / zip 防护用例）
python -m paotuan                 # 启动客户端
```

## 模块（对应 ARCHITECTURE.md §3）

- `loader/` 剧本 zip 安全加载（zip slip / zip bomb / 元数据校验）
- `state/` game_state 状态管理器与存档
- `sandbox/` RestrictedPython 白名单 + 子进程隔离沙箱（超时 kill）
- `workflow/` Agent 工作流：M1 规则触发 或 M2 两段式意图路由（LLM JSON 拆解 + 脚本白名单校验 + 修复重试）
- `context/` 历史与状态摘要注入、记忆压缩（历史过长时 LLM 摘要）
- `censor/` 本地敏感词拦截 + 可选 OpenAI Moderation 兼容远程审查
- `llm/` OpenAI 兼容客户端（DeepSeek 默认）
- `generator/` 游玩记录 → 衍生剧本 zip 导出（游戏菜单「导出旅程…」）
- `ui/` PySide6 界面（QThread 后台推理）

M2 增强（意图路由 / 记忆压缩 / 远程审查）可在「设置」中开关；默认意图路由关（沿用 M1 规则触发）、记忆压缩开、远程审查关。

## 社区网站（M3）

`../web/` 为 FastAPI + SQLite + Jinja2 轻量前端，提供用户系统、剧本上传（含 zip 防护）/列表/详情/下载、版本历史与旧版下载：

```bash
cd web
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000   # 打开 http://127.0.0.1:8000
pytest                                    # 27 个用例
```