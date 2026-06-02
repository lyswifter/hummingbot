# OKX Demo 速查表（Cheatsheet）

本项目当前实际在跑的 OKX **模拟盘**策略的常用命令。完整说明见 [`OKX_DEMO_TRADING.md`](./OKX_DEMO_TRADING.md)。

---

## 0. 启动环境

```bash
conda activate hummingbot          # env 在 /opt/miniconda3
bin/hummingbot.py                  # 进入 Hummingbot CLI
```

---

## 1. 连接交易所（在 CLI 内）

| 市场 | 实盘 | 模拟盘（Demo） |
|------|------|----------------|
| 现货 | `connect okx` | `connect okx_demo` |
| 永续 | `connect okx_perpetual` | `connect okx_perpetual_demo` |

```text
>>> connect okx_perpetual_demo     # 永续模拟盘
>>> connect okx_demo               # 现货模拟盘
```

依次输入**模拟盘专属**的 API key / Secret / Passphrase。
凭据已存在：`conf/connectors/okx_demo.yml`、`conf/connectors/okx_perpetual_demo.yml`。

> ⚠️ 模拟盘必须用模拟盘 Key（OKX → 交易 → 模拟交易 → 个人中心 → 模拟交易 API 创建）。
> 实盘 Key 混用会报 `401 / Invalid OK-ACCESS-KEY`。

---

## 2. 启动当前的策略

在 CLI 内用 `start --v2 <conf/scripts 下的文件>`，脚本名（`script_file_name`）从该 yml 内部读取：

| 策略 | 市场 | 启动命令 |
|------|------|----------|
| 现货 PMM | `okx_demo` | `start --v2 conf_my_okx_demo_pmm_1.yml` |
| 永续 SmartGrid | `okx_perpetual_demo` | `start --v2 smart_grid_okx_perp_demo.yml` |
| 现货 SmartGrid | `okx_demo` | `start --v2 smart_grid_okx_demo.yml` |

- 脚本配置：`conf/scripts/*.yml`（含 `script_file_name` 与参数）｜ 控制器配置：`conf/controllers/*.yml`
- SmartGrid 的脚本配置 `script_file_name: v2_with_controllers.py`，由它加载 `controllers_config` 里引用的控制器 yml。
- 非交互启动（命令行直接拉起）：`bin/hummingbot.py`，或 `bin/hummingbot_quickstart.py --config-file-name <conf>`。

---

## 3. 运行中常用命令

```text
>>> status            # 当前策略 / 连接器就绪状态
>>> history           # 成交与盈亏
>>> balance           # 余额
>>> config            # 查看/改参数
>>> stop              # 停止策略
>>> exit              # 退出（会先停策略）
```

---

## 4. 日志与数据库

```
logs/logs_<策略名>.log                 # 单策略日志
logs/logs_hummingbot.log               # 全局日志
data/<策略名>.sqlite                   # 订单 / 成交 / 持仓 / Executors
```

快速排查（在仓库根目录）：

```bash
# 错误概览
grep -ciE 'ERROR|Traceback' logs/logs_smart_grid_okx_perp_demo.log

# 订单状态分布
sqlite3 -header -column data/smart_grid_okx_perp_demo.sqlite \
  "SELECT last_status, COUNT(*) n FROM 'Order' GROUP BY last_status ORDER BY n DESC;"

# 是否有残留持仓 / 在跑的 Executor（status: 1=未启动 2=运行 3=收尾 4=终止）
sqlite3 data/smart_grid_okx_perp_demo.sqlite "SELECT COUNT(*) FROM Position;"
sqlite3 -header -column data/smart_grid_okx_perp_demo.sqlite \
  "SELECT status, COUNT(*) FROM Executors GROUP BY status;"
```

---

## 5. 注意事项（坑）

- **数据库里的交易所名是父名**：`okx_demo` 在 DB 中记为 `okx`，`okx_perpetual_demo` 记为 `okx_perpetual`
  （连接器 `name` 属性沿用父连接器，与 testnet 类连接器一致）。余额/盈亏对账按这个父名查找。
- **实盘 ↔ 模拟盘是独立连接器**，互不干扰；创建策略时连接器要选 demo 名，订单才路由到模拟盘。
- **底层差异**：demo 给每个 REST 请求注入 `x-simulated-trading: 1` 头，WebSocket 走 `wspap` 节点（偶有延迟，正常）。
- **改了连接器代码后需重启 bot** 才生效（运行中的进程用的是启动时加载的代码）。

---

## 6. 跑连接器单测

```bash
conda activate hummingbot
python -m pytest \
  test/hummingbot/connector/derivative/okx_perpetual/test_okx_perpetual_derivative.py \
  test/hummingbot/connector/exchange/okx/test_okx_exchange.py -q
```
