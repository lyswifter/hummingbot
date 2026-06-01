# HFT 研究笔记:基础设施与"出手"决策

> 整理自一次关于高频交易(HFT)的深入讨论,起点是"Hummingbot 算不算 HFT"。
> 结论:Hummingbot 是**秒级的自动化做市/套利框架**,不是低延迟竞速的 HFT。
> 本笔记记录真正的 HFT 是怎么做的,以及"一个行情包何时值得出手"的判断逻辑。
> 数字与案例均来自公开资料(见文末来源),代码引用对应 Hummingbot 仓库。

---

## 目录

- [第一部分:真·HFT 技术栈——把延迟从"秒"压到"纳秒"](#第一部分真hft技术栈把延迟从秒压到纳秒)
  - [0. 尺度感:tick-to-trade 延迟预算](#0-尺度感tick-to-trade-延迟预算)
  - [1. 地理与专线:和光速赛跑](#1-地理与专线和光速赛跑)
  - [2. Co-location:挤进交易所机房](#2-co-location挤进交易所机房)
  - [3. 网络:绕开操作系统内核](#3-网络绕开操作系统内核kernel-bypass)
  - [4. 硬件:FPGA / ASIC](#4-硬件fpga--asic)
  - [5. 软件与语言:C++ / Rust / OCaml](#5-软件与语言c--rust--ocaml)
  - [6. 可读代码的开源项目](#6-可读代码的开源项目)
  - [7. 现实成本与门槛](#7-现实成本与门槛)
- [第二部分:一个行情包,何时"值得出手"](#第二部分一个行情包何时值得出手)
  - [1. 行情包是什么](#1-行情包是什么)
  - [2. 黄金法则:净 edge > 安全垫](#2-黄金法则净-edge--安全垫)
  - [3. 代码实证:Hummingbot 的套利决策](#3-代码实证hummingbot-的套利决策)
  - [4. 成本侧:毛利里要扣什么](#4-成本侧毛利里要扣什么)
  - [5. 真·HFT 的出手信号目录](#5-真hft-的出手信号目录)
  - [6. 两种出手姿势:maker vs taker](#6-两种出手姿势maker-vs-taker)
  - [7. 为什么判断必须极简](#7-为什么判断必须极简)
- [TL;DR 速记](#tldr-速记)
- [延伸研究方向](#延伸研究方向)
- [来源](#来源)

---

# 第一部分:真·HFT 技术栈——把延迟从"秒"压到"纳秒"

HFT 的核心思维是 **tick-to-trade**:从网卡收到一个行情包,到把订单发出网卡,这中间花多少时间。整条链路每一层都在和物理极限较劲。

## 0. 尺度感:tick-to-trade 延迟预算

| 环节 | Hummingbot(对照) | 真·HFT |
|---|---|---|
| 策略循环 | tick 1 秒(最快 0.1s) | 事件驱动,无轮询 |
| 决策逻辑(订单簿更新) | Python/Cython,微秒~毫秒 | C++/FPGA,**单位数~数百纳秒** |
| 操作系统网络栈 | 标准内核栈,~10–100 μs | **绕过内核**,1–5 μs |
| 网卡→交易所撮合 | 公网,几十~几百 ms | **同机房**,微秒级 |
| 城市间(芝↔纽) | 走公网 | **自建微波**,~4 ms 单程 |

> 单位参照:1 秒 = 10³ 毫秒(ms)= 10⁶ 微秒(μs)= 10⁹ 纳秒(ns)。
> HFT 竞争的尺度是 μs 和 ns,Hummingbot 在 s 的尺度。

## 1. 地理与专线:和光速赛跑

经典战场:**芝加哥(CME 期货)↔ 纽约/新泽西(股票/ETF)**,约 1200 km。期货与现货之间套利,谁的信息先到谁赢。

- **光纤时代**:2010 年 Spread Networks 花 **$300M** 铺了一条 827 英里的**直线**光纤,把往返从 ~17ms 压到 **~13ms**。Michael Lewis《Flash Boys》写的就是它。
- **微波反超**:光在**空气里比在玻璃(光纤)里快约 50%**(折射率 1.0 vs ~1.47),且微波走直线。McKay Brothers 等用微波把往返做到 **~8.2–8.5ms**,比光纤快 **2.7–5ms**,每条链路成本仅约 **$8M**。
- **官方数字**:CME–Nasdaq 微波行情 Carteret↔Aurora **4.25ms 单程 / 8.5ms 往返**,而最快光纤是 6.65ms 单程。
- **更极端**:跨大西洋海缆(Hibernia Express)、毫米波、激光、中空光纤(hollow-core fiber,光在空气芯里跑)。

> 直觉:这一层买的是**物理距离和介质**,钱解决的是"光速"问题。

## 2. Co-location:挤进交易所机房

城际靠微波,机房内就要**和撮合引擎同处一室**。三大核心机房:

- **NYSE → Mahwah, NJ**;**Nasdaq → Carteret, NJ**;**CME → Aurora, IL**

公平性细节:**等长线缆(equal-length / harmonized cabling)**。交易所把每个客户机柜到撮合引擎的光纤**裁成相同长度**——哪怕你物理上更近,也绕等长的线,确保没人靠"离得近几米"占优。这写进了 colocation 技术规范(ICE/NYSE Mahwah 文档)。

## 3. 网络:绕开操作系统内核(kernel bypass)

标准 Linux 收包要经过中断、内核协议栈、上下文切换、内存拷贝——几十微秒且**抖动大**(HFT 怕慢更怕不确定)。解决办法:让数据包**直接从网卡进用户态内存**。

- **DPDK**(Data Plane Development Kit):用户态轮询驱动直接操作网卡,~1–5 μs。
- **Solarflare OpenOnload**:把 TCP/IP 协议栈搬到用户态,HFT 行业**事实标准**。
- 配套:**busy-polling**(忙等而非中断/sleep)、**CPU pinning** + `isolcpus`(核心独占)、关超线程/节能、NUMA 感知。

## 4. 硬件:FPGA / ASIC

软件再快也有 CPU 指令和总线开销。最极致是把"解析行情 → 风控 → 决策 → 发单"**直接做进网卡上的 FPGA**,数据不进 CPU:

- FPGA 的 tick-to-trade 通常 **100–500 ns**。
- 真实标杆:**Solarflare + LDA Technologies** 用 Xilinx Kintex UltraScale FPGA + "Delegated TCP send" 技巧,做到 **120 纳秒** tick-to-trade。
- 硬件:Xilinx(现 AMD)SN1000/SN1022 这类 **SmartNIC**;再极致是 ASIC。
- 连 Jane Street 这种软件文化很强的公司,最热路径也上 FPGA。

## 5. 软件与语言:C++ / Rust / OCaml

共同硬约束:**绝不能有 GC**——垃圾回收的 stop-the-world 暂停在 HFT 里是灾难。所以基本只用无 GC 的系统语言:

- **C++ —— 绝对主流**(Citadel Securities、Jump Trading 等):手动内存控制、零成本抽象、生态成熟、遗留代码多。
- **Rust —— 新兴**:同样无 GC + 零成本抽象,多了内存安全与现代工具链;但行业采用度、生态、遗留集成不如 C++,目前多见于新系统/外围。
- **OCaml —— Jane Street 的著名特例**:函数式、编译到原生。但 Jane Street 自承在超低延迟上"fight at a fundamental disadvantage",有名言:**"anyone can write fast C++, but it takes a real expert to write fast OCaml"**。

**热路径编程纪律**(无论哪种语言):
- 不分配堆内存(预分配内存池 / 对象池)
- 不加锁(lock-free,如 ring buffer)
- 不做系统调用(kernel bypass、busy-polling)
- 少用虚函数/异常(避免分支预测失败、间接跳转)
- 数据 cache 友好(局部性、避免 false sharing、NUMA 感知)
- LMAX 把这套叫 **"mechanical sympathy"**(对硬件的同理心)

## 6. 可读代码的开源项目

生产级 HFT 系统是商业机密,但**基础设施件**和**教学级实现**有大量开源:

**消息 / 并发 / 序列化框架(被真实交易系统采用):**
- **LMAX Disruptor**(Java)— LMAX 交易所开源的 lock-free ring buffer,mechanical sympathy 代表作
- **Aeron**(Real Logic / Martin Thompson)— 超低延迟消息(UDP/IPC),Premium 版用 DPDK
- **Chronicle Queue**(OpenHFT)— Java 堆外持久化队列
- **SBE**(Simple Binary Encoding)— 零拷贝序列化
- **Seastar**(C++)— shard-per-core 异步框架(ScyllaDB 同款);**DPDK** — kernel bypass

**可读的撮合引擎 / order book(GitHub,带实测延迟):**
- `PIYUSH-KUMAR1809/order-matching-engine` — C++20 限价订单簿,实测 **~7 ns/单**、~160M 单/秒
- `Naseefabu/ultra-low-latency-orderbook` — C++20,宣称**单位数纳秒**
- `aspone/OrderBook` — addOrder 中位数 **484 ns**,指标全
- `eelixir/mercury` — C++ 撮合引擎,网关→引擎→发布全链路纳秒级追踪
- `SLMolenaar/orderbook-simulator-cpp` — 微秒级,接 Binance 实时数据(适合加密练手)

> 入门路径:先读 `aspone/OrderBook` 看干净的低延迟订单簿;再读 LMAX Disruptor 设计文档理解 lock-free / mechanical sympathy;想碰网络层就上 DPDK / Onload 示例。

## 7. 现实成本与门槛

一套真·HFT 基础设施:co-location 机柜(月租数千~数万美元)+ 微波链路接入(单条建设 ~$8M)+ FPGA 工程师 + C++ 专家团队——**门槛是几百万美元级**,收益来自**纳秒级的相对优势**,是零和竞速。

Hummingbot 在另一个象限:**用公网 API、秒级循环做自动化做市/套利**,门槛极低、对延迟不敏感(挂单价差、资金费套利、网格)。两者不是同一个游戏:一个拼物理和工程极限,一个拼策略和易用性。

---

# 第二部分:一个行情包,何时"值得出手"

## 1. 行情包是什么

交易所行情流持续推送各类 **market data message**:

- **L1 / BBO**:最优买卖价(top of book)变了
- **L2**:某价位挂单量变了(深度更新)
- **L3 / MBO**(market-by-order):每一笔订单的增/删/改——信息最细,HFT 最爱
- **Trades**:有人成交了(价、量、方向)
- 形式分**快照**(snapshot)和**增量**(diff/delta)

关键认知:**行情包量极大,真正"值得出手"的极少**。HFT 系统 99.99% 的时间在"看"(更新内部订单簿状态),只在极个别包上"出手"。所以问题本质是:**这个包把市场更新到了一个该动手的状态吗?**

## 2. 黄金法则:净 edge > 安全垫

任何"出手"决策,内核都是同一个不等式:

```
E[这笔交易的净收益]  >  不确定性安全垫

其中  净收益 = 毛利 − 手续费 − 滑点 − 预期被逆向选择的损失
```

毛利转正还不够,必须**超过一个阈值(buffer)**:从你"决定"到"成交"之间,机会可能消失、价格可能滑。

## 3. 代码实证:Hummingbot 的套利决策

这套逻辑在 `arbitrage_executor.py` 写得非常干净(`control_task`,每个 tick 跑一次):

```python
# hummingbot/strategy_v2/executors/arbitrage_executor/arbitrage_executor.py:163
async def control_task(self):
    if self.status == RunnableStatus.RUNNING:
        await self.update_trade_pnl_pct()   # 1. 用当前盘口价算两腿毛利率
        await self.update_tx_cost()         # 2. 算总成本(买卖手续费 + gas)
        self._current_profitability = (
            self._trade_pnl_pct * self.order_amount - self._last_tx_cost
        ) / self.order_amount               # 3. 净利润率 = (毛利 − 成本) / 量
        if self._current_profitability > self.min_profitability:  # 4. 超过阈值才出手!
            await self.execute_arbitrage()  # 5. 同时打两腿市价单
```

逐行对应黄金法则:
- `update_trade_pnl_pct()`(:251)= `(卖价 − 买价) / 买价`,用**当前行情**算毛利
- `update_tx_cost()`(:215)= 两腿手续费 + gas,**成本侧**
- `min_profitability` 就是那个**安全垫**(如 0.3%)——低于它,哪怕毛利为正也**不出手**

V1 的 `amm_arb.py:215-228` 同理:只保留 `profit_pct >= min_profitability` 的提案,否则不动手。

> 这就是"值得出手"最朴素、最真实的代码形态:**净利润 > 阈值 → 下单,否则继续看**。每来一个行情包重算一次。

## 4. 成本侧:毛利里要扣什么

新手只看"两边差价",老手扣完这些才看是否为正:

| 成本项 | 含义 |
|---|---|
| **手续费** | maker/taker 费率(taker 吃单更贵) |
| **滑点 / 市场冲击** | 你的单不是只吃最优价,会吃穿几档(Hummingbot 有 `apply_slippage_buffers`) |
| **成交概率(fill prob)** | 挂单未必成交;期望要乘以成交概率 |
| **逆向选择(adverse selection)** | 能成交往往因为对手方掌握你不知道的信息——做市最大的隐性成本 |
| **延迟风险** | 从你决策到单子到达,机会还在吗 |

## 5. 真·HFT 的出手信号目录

什么样的包会触发动作(每个给一句直觉):

1. **跨市场 / 三角套利**:同一资产两个场所价差(或 A/B·B/C·C/A)扣费后 > 0 → 两腿同时打。**即上面那段代码做的事。**
2. **Latency arbitrage / stale quote**:交易所 A 的价已动,交易所 B 报价**还没更新**——抢在它更新前吃旧价。微波专线就是为这几微秒。
3. **Order book imbalance(盘口失衡)**:买盘量 ≫ 卖盘量,短期价格大概率上行 → 抢先买。信号:`I = (Qbid − Qask)/(Qbid + Qask)`。
4. **Micro-price(微价格)**:买卖量加权的"真实中间价"(Sasha Stoikov 提出),显著偏离普通 mid 时,预示短期漂移方向。
5. **大单 sweep / 价位被清空**:L3 包显示某档被吃穿 → 预示动量,跟上或撤掉自己暴露的挂单。

> 注:Hummingbot 也有 `imbalance` 的影子——`stat_arb.py` 用持仓 imbalance 决定建仓,`xemm_multiple_levels` 用 executor imbalance 控方向暴露,只是在**秒级**用,非纳秒级。

## 6. 两种出手姿势:maker vs taker

- **Taker(主动吃单)**:套利、latency、动量信号——看到机会**主动打市价/IOC 单**。上面的 arbitrage 就是 taker。
- **Maker(被动做市)**:大部分时间**挂单等成交**,"出手"其实是**报价和撤价**的决策:盘口一动、库存一偏、检测到 adverse selection,就**撤旧挂新**。Hummingbot 的 `avellaneda_market_making` 用 Avellaneda-Stoikov 模型算 reservation price 决定挂哪、`order_refresh_time` 决定多久重报。

## 7. 为什么判断必须极简

真·HFT 里,"值得不值得"要在**纳秒级**做完,否则机会就没了。所以热路径里**不能跑复杂模型**,只能是**预算好的查表、整数比较、加减法**(阈值、价差、imbalance 比值)。复杂的 alpha 模型在**离线**算好,压缩成几个阈值/系数,在线只做"比较"。这也是为什么决策逻辑常落到 FPGA——简单到可以固化成电路。

---

## TL;DR 速记

1. **HFT = 和物理极限赛跑**:语言(无 GC 的 C++/Rust)→ kernel bypass(DPDK/Onload,μs)→ FPGA(tick-to-trade ~120ns)→ co-location(同机房+等长线缆)→ 城际微波专线(芝↔纽 ~4ms 单程)。
2. **每一层都在砍延迟的某个来源**:计算、操作系统、机房内距离、城市间距离。
3. **"出手"的唯一内核**:`净收益(毛利 − 手续费 − 滑点 − 逆向选择)> 安全垫`。绝大多数行情包达不到,所以**克制不动手**和**算准何时动手**同样重要。
4. **真实代码**:`arbitrage_executor.control_task` —— 每 tick 重算净利润,`> min_profitability` 才下单。
5. **常见出手信号**:跨市场/三角套利、latency/stale quote、order book imbalance、micro-price、大单 sweep。
6. **Hummingbot 的定位**:秒级自动化做市/套利,不是 HFT;但"阈值出手""imbalance"这些**概念是相通的**,只是时间尺度差 6~9 个数量级。

## 延伸研究方向

- 逐行精读一个开源 C++ order book(如 `aspone/OrderBook`)的数据结构与 lock-free 技巧
- 读懂 LMAX Disruptor 的 ring buffer 为何无锁(单生产者/多消费者、序号屏障)
- Avellaneda-Stoikov 做市模型:reservation price 与最优 spread 的推导(对照 Hummingbot `avellaneda_market_making`)
- micro-price 原始论文(Stoikov, 2018)与 order book imbalance 的实证 alpha
- 动手:用 Python/Rust 写一个最小的 "order book imbalance 信号 + 阈值出手" 回测

## 来源

**专线 / co-location:**
- Spread Networks — https://en.wikipedia.org/wiki/Spread_Networks
- A short story about how to spend $300m — https://jimdcampbell.com/2016/09/01/a-short-story-about-how-to-spend-300m/
- CME–Nasdaq microwave connectivity — https://wallstreetandtech.com/infrastructure/countering-hft-exclusives-cme-nasdaq-launch-microwave-connectivity-for-market-data/d/d-id/1268095.html
- ICE/NYSE Mahwah Colocation Tech Specs — https://www.nyse.com/publicdocs/IGN_Colocation_Mahwah_Technical_Specs.pdf

**网络 / FPGA:**
- Solarflare + LDA: 120ns tick-to-trade — https://www.tradersmagazine.com/departments/brokerage/solarflare-and-lda-technologies-slash-tick-to-trade-latency-to-120-nanoseconds/
- Kernel bypass in HFT (Databento) — https://databento.com/microstructure/kernel-bypass

**语言:**
- Jane Street OCaml vs C++ (eFinancialCareers) — https://www.efinancialcareers.com/news/2023/11/ocaml-vs-c-high-frequency-trading
- Rust for HFT (markrbest) — https://markrbest.github.io/hft-and-rust/

**开源框架 / 代码库:**
- LMAX Disruptor — https://lmax-exchange.github.io/disruptor/
- Aeron on AWS (Real Logic) — https://aws.amazon.com/blogs/industries/aeron-performance-enables-capital-markets-to-move-to-the-cloud-on-aws/
- ultra-low-latency-orderbook — https://github.com/Naseefabu/ultra-low-latency-orderbook
- aspone/OrderBook — https://github.com/aspone/OrderBook
- order-matching-engine — https://github.com/PIYUSH-KUMAR1809/order-matching-engine

**Hummingbot 代码引用:**
- `hummingbot/strategy_v2/executors/arbitrage_executor/arbitrage_executor.py`(`control_task`:163,`update_tx_cost`:215,`update_trade_pnl_pct`:251)
- `hummingbot/strategy/amm_arb/amm_arb.py`(:215–229,`min_profitability` 筛选)
- `hummingbot/strategy/avellaneda_market_making/`(reservation price 做市模型)

---

*免责声明:本笔记为技术研究记录,不构成投资建议。文中延迟/成本数字来自公开报道,会随时间和厂商而变,引用前请核对原始来源。*
