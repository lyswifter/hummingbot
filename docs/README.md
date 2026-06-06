# 项目文档索引

本目录收录本仓库在 Hummingbot 之上的**自定义文档**(OKX 接入、网格策略、研究笔记、开发环境等)。
上游 Hummingbot 的通用文档见官网 <https://hummingbot.org/docs/>。

> 仓库根目录只保留 `README.md` / `CONTRIBUTING.md` / `CODE_OF_CONDUCT.md` 三个标准文件,其余文档统一归到这里。

---

## 📁 目录结构

```
docs/
├── README.md              ← 本索引
├── okx/                   OKX 交易所接入与使用
│   ├── trading-guide.md   实盘 / 模拟盘交易完整指南
│   └── cheatsheet.md      日常操作速查表
├── strategies/            策略说明
│   └── smart-grid.md      SmartGrid 网格策略运行逻辑图解
├── research/              研究笔记
│   └── hft-notes.md       HFT 基础设施与"出手"决策
└── dev/                   开发环境
    └── editor-setup.md    VS Code / Cursor 配置指南
```

---

## 🔗 文档导航

### OKX 交易所
| 文档 | 内容 |
|---|---|
| [okx/trading-guide.md](./okx/trading-guide.md) | OKX **实盘 / 模拟盘**交易使用指南:连接器配置、demo 切换、技术细节、注意事项 |
| [okx/cheatsheet.md](./okx/cheatsheet.md) | 日常操作**速查表**:启动环境、连接、起策略、查日志/数据库、常见坑 |

### 策略
| 文档 | 内容 |
|---|---|
| [strategies/smart-grid.md](./strategies/smart-grid.md) | **SmartGrid** 运行逻辑图解:整体流程图、网格价格带示意、Mermaid 流程图、参数速查 |

> 相关源码:`controllers/generic/smart_grid.py` · 执行引擎 `hummingbot/strategy_v2/executors/grid_executor/`
> 其他网格控制器:`grid_strike.py` / `multi_grid_strike.py` / `quantum_grid_allocator.py` · `directional_trading/bollingrid.py`

### 研究 & 开发
| 文档 | 内容 |
|---|---|
| [research/hft-notes.md](./research/hft-notes.md) | **HFT 研究笔记**:真·HFT 技术栈(延迟预算/co-location/FPGA…)与"何时出手"决策 |
| [dev/editor-setup.md](./dev/editor-setup.md) | **VS Code / Cursor** 配置:settings、调试、测试发现 |

---

## 🚀 新手路径建议

1. 先按 [dev/editor-setup.md](./dev/editor-setup.md) 配好开发环境
2. 按 [okx/trading-guide.md](./okx/trading-guide.md) 接入 OKX(先用 `okx_demo` 模拟盘)
3. 用 [okx/cheatsheet.md](./okx/cheatsheet.md) 速查日常命令
4. 想跑网格策略 → 读 [strategies/smart-grid.md](./strategies/smart-grid.md) 理解逻辑后再起策略
