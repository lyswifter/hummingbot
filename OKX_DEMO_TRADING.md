# OKX 实盘 / 模拟盘交易使用指南

本指南说明如何在 Hummingbot 中使用 **OKX 现货**和**OKX 永续合约**进行**实盘交易**和**官方模拟盘(Demo Trading)交易**。

模拟盘连接到 OKX 服务器端的真实模拟环境(真实撮合引擎、真实下单/成交回报、虚拟资金),比本地的 Paper Trade 更接近实盘,适合上真钱前做完整验证。

---

## 速查表

| 市场 | 实盘(默认) | 模拟盘(Demo) |
|------|-------------|----------------|
| 现货 | `connect okx` → demo 选项答 **No** | `connect okx` → demo 选项答 **Yes** |
| 永续 | `connect okx_perpetual` | `connect okx_perpetual_demo` |

> 实盘是默认行为,无需任何额外配置。模拟盘是可选的:现货用一个开关,永续用一个独立的连接器。

---

## 一、实盘交易(默认,开箱即用)

实盘本来就是 OKX 连接器的原生行为,直接连接即可。

### 现货实盘
```
>>> connect okx
```
依次输入:API key、Secret key、Passphrase、注册子域名(`www`/`app`/`my`,大多数用户为 `www`)。
最后会询问是否使用模拟盘 —— **答 `No`(默认)即为实盘**。

### 永续实盘
```
>>> connect okx_perpetual
```
依次输入:API key、Secret key、Passphrase。

---

## 二、模拟盘交易(Demo Trading)

### 步骤 1:申请 OKX 模拟盘 API Key

> ⚠️ 模拟盘必须使用**模拟盘专属的 API Key**;实盘的 Key 不能用于模拟盘,反之亦然。

1. 登录 OKX 官网
2. 进入 **交易 → 模拟交易(Demo Trading)**
3. 打开 **个人中心 → 模拟交易 API → 创建模拟交易 API Key**
4. 记录生成的 **API Key / Secret Key / Passphrase**

模拟盘账户自带虚拟资金,可在模拟交易界面查看或领取。

### 步骤 2A:现货模拟盘

```
>>> connect okx
```
- 输入模拟盘的 API key / Secret / Passphrase
- 子域名填 `www`
- 最后一问 **「Do you want to connect to the OKX demo (simulated) trading environment?」答 `Yes`**

之后照常创建并启动策略(连接器选 `okx`),订单会路由到 OKX 模拟盘。

### 步骤 2B:永续模拟盘

```
>>> connect okx_perpetual_demo
```
- 输入模拟盘的 API key / Secret / Passphrase

之后创建策略时,**连接器选择 `okx_perpetual_demo`**,交易对例如 `BTC-USDT`,启动即可。

---

## 三、运行策略示例

模拟盘与实盘的策略配置方式完全一致,只是连接器选择不同。例如跑一个纯做市:

```
>>> create
# 选择策略: pure_market_making
# 交易所(现货):okx 或 okx_perpetual_demo(永续模拟盘)
# 交易对:BTC-USDT
# ... 其余按提示填写
>>> start
```

---

## 四、技术实现细节

OKX 模拟盘与实盘共用同一套 API 域名,区别在于:

| 项目 | 实盘 | 模拟盘 |
|------|------|--------|
| REST 域名 | `https://www.okx.com` | `https://www.okx.com`(相同) |
| REST 请求头 | 无 | 每个请求附加 `x-simulated-trading: 1` |
| 公共 WebSocket | `wss://ws.okx.com:8443/ws/v5/public` | `wss://wspap.okx.com:8443/ws/v5/public?brokerId=9999` |
| 私有 WebSocket | `wss://ws.okx.com:8443/ws/v5/private` | `wss://wspap.okx.com:8443/ws/v5/private?brokerId=9999` |

### 实现方式
- **现货**(`hummingbot/connector/exchange/okx/`):新增配置开关 `okx_use_demo_trading`。开启时,通过一个 REST 预处理器给每个请求注入 `x-simulated-trading` 头,并将 WebSocket 切到 `wspap` 主机。
- **永续**(`hummingbot/connector/derivative/okx_perpetual/`):通过 Hummingbot 的 `OTHER_DOMAINS` 机制暴露独立连接器 `okx_perpetual_demo`(与 `bybit_perpetual_testnet` 同款模式)。该 domain 自动选用 demo 的 REST/WS 地址,并注入模拟盘请求头。

两边默认都走实盘,改动向后兼容,不影响既有实盘配置。

---

## 五、注意事项

- **API Key 不通用**:模拟盘 Key 与实盘 Key 相互独立,不能混用。
- **行情数据**:模拟盘使用真实市场行情,但撮合在 OKX 模拟服务器进行。
- **网络延迟**:demo 的 `wspap` 节点偶尔延迟会高于生产环境,属正常现象。
- **交易记录**:永续模拟盘 `okx_perpetual_demo` 在数据库中仍以 `okx_perpetual` 这个交易所名记录(与 bybit testnet 行为一致),不影响交易功能。
- **切换实盘/模拟盘**:
  - 现货:重新 `connect okx`,把 demo 一问改为相反选项即可。
  - 永续:实盘用 `okx_perpetual`,模拟盘用 `okx_perpetual_demo`,互不干扰。

---

## 六、验证(单元测试)

相关单元测试覆盖了 live/demo 的 WebSocket 地址、模拟盘请求头注入、配置开关与连接器变体:

```bash
pytest test/hummingbot/connector/exchange/okx/test_okx_web_utils.py \
       test/hummingbot/connector/exchange/okx/test_okx_utils.py \
       test/hummingbot/connector/derivative/okx_perpetual/test_okx_perpetual_web_utils.py \
       test/hummingbot/connector/derivative/okx_perpetual/test_okx_perpetual_utils.py
```
