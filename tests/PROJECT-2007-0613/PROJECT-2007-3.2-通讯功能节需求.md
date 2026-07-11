# PROJECT-2007 3.2 通讯功能（开发对齐版）

> 来源：`PROJECT-2007空中加受油控制器控制软件研制任务书-V1.01（受控）.docx`
> 用途：用于地测/RIU/KZZZ/CCDL通信链路核对。
> 口径说明：接口条款与专题正文冲突时，以任务书正文为主，协议文件作为辅证。

---

## 原始需求号列表

- `PROJECT-2007R_SDTD_0014` 通道内部通讯功能
- `PROJECT-2007R_SDTD_0015` 通道间通讯功能
- `PROJECT-2007R_SDTD_0016` 与地面测试设备的通讯功能
- `PROJECT-2007R_SDTD_0017` 与RIU的通讯功能
- `PROJECT-2007R_SDTD_0018` 与左/右吊舱控制装置的通讯功能

---

## 条款拆解（逐条）

### 0014 通道内部通讯功能
- DSP与CPLD通过EMIF/CCDL完成通道内通信。
- 通信项需与附录B总线表一致。

### 0015 通道间通讯功能
- A/B通道DSP之间通过SCIC进行CCDL数据交换。
- 波特率为`115200bit/s`。
- 周期为`100ms`。

### 0016 与地面测试设备通信
- 通过SCIA与地面测试设备全双工异步通信。
- 波特率为`115200bit/s`。
- 通信用于地面维护功能闭环。

### 0017 与RIU通信
- 通过ARINC429与RIU通信。
- 通过SPI控制429芯片。
- 波特率为`100kbit/s`。

### 0018 与左/右吊舱控制装置通信
- 通过ARINC429与左右吊舱控制装置通信。
- 通过SPI控制429芯片。
- 波特率为`100kbit/s`。

---

## 代码入口函数候选

- `CommCCDLDataBuffRead`
- `CommCCDLFrameProcess`
- `MaintRxDataProcess`
- `Comm429RIUDataProcess`
- `Comm429RIUPeriodInfoTx`
- `Comm429KZZZDataProcess`
- `SysInfoComm429PeriodSend`

---

## 已知文档冲突/疑点

- 报文字段/标签真值以已重建的`requirements/protocol_catalog*.yaml`与专题正文共同约束。
- KZZZ旧版控制装置接口与任务书正文冲突处，正文控制语义优先，旧接口仅用于协议兼容说明。

---

## 验收判据

- 通信对象、方向、速率、周期和主语义与任务书一致。
- `RIU`与`KZZZ`发送项必须能追溯到明确来源，不允许无来源业务值。
- 关键接口链路需具备“输入 -> 处理 -> 输出”闭环证据。
