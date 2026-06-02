# OKX 实盘 / 模拟盘交易使用指南

本指南说明如何在 Hummingbot 中用 **OKX 现货**和 **OKX 永续合约**进行**实盘交易**和**官方模拟盘（Demo Trading）交易**。

模拟盘连接到 OKX 服务器端的真实模拟环境（真实撮合引擎、真实下单/成交回报、虚拟资金），比本地的 Paper Trade 更接近实盘，适合上真钱前做完整验证。

---

## 速查表

| 市场 | 实盘（默认） | 模拟盘（Demo） |
|------|-------------|----------------|
| 现货 | `connect okx` | `connect okx_demo` |
| 永续 | `connect okx_perpetual` | `connect okx_perpetual_demo` |

> 实盘与模拟盘是**各自独立的连接器**：实盘无需任何额外配置；模拟盘是单独的连接器，需要用 OKX 模拟盘专属的 API Key。

---

## 一、实盘交易（默认，开箱即用）

### 现货实盘
```
>>> connect okx
```
依次输入：API key、Secret key、Passphrase、注册子域名（`www`/`app`/`my`，大多数用户为 `www`）。

### 永续实盘
```
>>> connect okx_perpetual
```
依次输入：API key、Secret key、Passphrase。

---

## 二、模拟盘交易（Demo Trading）

### 步骤 1：申请 OKX 模拟盘 API Key

> ⚠️ 模拟盘必须使用**模拟盘专属的 API Key**；实盘的 Key 不能用于模拟盘，反之亦然（用错会返回 401 / Invalid OK-ACCESS-KEY）。

1. 登录 OKX 官网
2. 进入 **交易 → 模拟交易（Demo Trading）**，切换到模拟交易模式
3. 打开 **个人中心 → 模拟交易 API → 创建模拟交易 API Key**
4. 记录生成的 **API Key / Secret Key / Passphrase**

模拟盘账户自带虚拟资金，可在模拟交易界面查看或领取。

### 步骤 2A：现货模拟盘

```
>>> connect okx_demo
```
依次输入模拟盘的 **API key / Secret / Passphrase**。之后创建策略时，**连接器选 `okx_demo`**，订单会路由到 OKX 模拟盘。

### 步骤 2B：永续模拟盘

```
>>> connect okx_perpetual_demo
```
依次输入模拟盘的 **API key / Secret / Passphrase**。之后创建策略时，**连接器选 `okx_perpetual_demo`**。

### 步骤 3：验证连通

```
>>> balance
```
能看到模拟盘的虚拟余额，即说明连接成功。

---

## 三、运行策略示例

模拟盘与实盘的策略配置方式完全一致，只是连接器选择不同。例如跑一个纯做市：

```
>>> create
# 选择策略: pure_market_making
# 交易所: okx_demo（现货模拟盘）或 okx_perpetual_demo（永续模拟盘）
# 交易对: BTC-USDT
# ... 其余按提示填写
>>> start
>>> status      # 查看运行状态
```

---

## 四、技术实现细节

OKX 模拟盘与实盘共用同一套 REST 域名，区别在于请求头与 WebSocket 主机：

| 项目 | 实盘 | 模拟盘 |
|------|------|--------|
| REST 域名 | `https://www.okx.com` | `https://www.okx.com`（相同） |
| REST 请求头 | 无 | 每个请求附加 `x-simulated-trading: 1` |
| 公共 WebSocket | `wss://ws.okx.com:8443/ws/v5/public` | `wss://wspap.okx.com:8443/ws/v5/public?brokerId=9999` |
| 私有 WebSocket | `wss://ws.okx.com:8443/ws/v5/private` | `wss://wspap.okx.com:8443/ws/v5/private?brokerId=9999` |

### 实现方式

现货和永续都通过 Hummingbot 标准的 **`OTHER_DOMAINS`** 机制，把模拟盘暴露成**独立连接器**（与 `binance_perpetual_testnet` 同款模式）：

- **现货**（`hummingbot/connector/exchange/okx/`）：新增连接器 `okx_demo`。内部把模拟盘建模为第四种 `okx_registration_sub_domain` 取值 `"demo"`，由一个 REST 预处理器在每个请求注入 `x-simulated-trading: 1` 头，并将 WebSocket 切到 `wspap` 主机。
- **永续**（`hummingbot/connector/derivative/okx_perpetual/`）：新增连接器 `okx_perpetual_demo`，复用底层已有的 `DEMO_DOMAIN`（demo 的 REST/WS 地址），并在 REST 注入模拟盘请求头。

两边默认都走实盘，改动向后兼容，不影响既有实盘配置。**纯 Python 改动，无需 `./compile`，下次启动直接生效。**

---

## 五、注意事项

- **API Key 不通用**：模拟盘 Key 与实盘 Key 相互独立，不能混用。
- **行情数据**：模拟盘使用真实市场行情，但撮合在 OKX 模拟服务器进行。
- **网络延迟**：demo 的 `wspap` 节点偶尔延迟会高于生产环境，属正常现象。
- **数据库交易所名**：`okx_demo` 在数据库中仍以 `okx` 记录、`okx_perpetual_demo` 仍以 `okx_perpetual` 记录（连接器 `name` 属性沿用父连接器，与 testnet 类连接器行为一致），不影响交易功能。
- **切换实盘/模拟盘**：实盘与模拟盘是不同连接器，互不干扰 —— 现货 `okx` ↔ `okx_demo`，永续 `okx_perpetual` ↔ `okx_perpetual_demo`。

---

## 六、验证（单元测试）

相关单元测试覆盖了 live/demo 的 WebSocket 地址、模拟盘请求头注入、`OTHER_DOMAINS` 连接器变体注册与字段映射：

```bash
pytest test/hummingbot/connector/exchange/okx/test_okx_web_utils.py \
       test/hummingbot/connector/derivative/okx_perpetual/test_okx_perpetual_web_utils.py \
       test/hummingbot/connector/derivative/okx_perpetual/test_okx_perpetual_utils.py
```
