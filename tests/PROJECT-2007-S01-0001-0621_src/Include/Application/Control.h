/**********************************************************************************
 *
 *             ***     **      **   **     ******
 *             ***     **     **    **   ***   ***
 *            ****     **     **   **   **      **
 *           ** **     **    **    **  **       **
 *          *** **     **   **     **  **
 *          **  **     **   **    **  **
 *         **   **     **  **     **  **
 *        ***   **     ** **      **  **
 *        ********     ** **     **   **      **
 *       **     **     ****      **   **     **
 *      **      **     ***       **   ***   **
 *      **      **     ***      **     ******
 *
 **********************************************************************************
 *
 * 文件名称:    Control.h
 *
 * 文件日期：       REDACTED
 *
 *
 * 程序版本:   V2.00
 *
 **********************************************************************************
 *
 * 功能说明:   系统控制模块公共接口定义
 *
 * 1. 定义系统状态、工作模式、控制输出及余度管理相关类型和宏。
 * 2. 对外暴露系统控制、故障评估、余度数据获取和周期发送接口。
 * 3. 控制模块内部实现已拆分到多个 Control_*.c 文件，本头文件仅保留公共接口。
 *
 *********************************************************************************/
#ifndef CONTROL_H_
#define CONTROL_H_

/* 模块说明：
 * 1. 定义系统状态、工作模式、控制功能及阈值常量。
 * 2. 定义控制输入输出、通信打包所需结构体。
 * 3. 声明控制主流程、模式处理、通信发送相关接口。
 */

/* ***************************************************************** */
/* 余度管理相关宏定义 */
/* ***************************************************************** */
#define REDUN_RIU_NUM                  (29U)    /* RIU数据余度管理数量  */
#define REDUN_KZZZ_SIDE_NUM            (25U)    /* 单侧吊舱KZZZ数据余度管理数量 */
#define REDUN_KZZZ_NUM                 (REDUN_KZZZ_SIDE_NUM * 2U)    /* 左右吊舱KZZZ数据余度管理总数量 */
#define REDUN_CCDL_NUM                 (7U)     /* CCDL数据余度管理数量 */
#define REDUN_DATA_NUM                 (REDUN_RIU_NUM + REDUN_KZZZ_NUM + REDUN_CCDL_NUM)    /* 余度管理数据总数 */

#define REDUN_INDEX_RIU_HEART          (0U)     /* 设备心跳 */
#define REDUN_INDEX_RIU_REFUEL_CMD     (1U)     /* 加油指令 */
#define REDUN_INDEX_RIU_RCV            (2U)     /* 压力加油控制活门状态 */
#define REDUN_INDEX_RIU_VALVE1         (3U)     /* 阀状态信号1 */
#define REDUN_INDEX_RIU_VALVE2         (4U)     /* 阀状态信号2 */
#define REDUN_INDEX_RIU_FUELPUMP       (5U)     /* 加油泵状态信号 */
#define REDUN_INDEX_RIU_HL_SENSOR      (6U)     /* 高油面信号器信号 */
#define REDUN_INDEX_RIU_FAULTINFO      (7U)     /* 故障信息 */
#define REDUN_INDEX_RIU_PRV            (8U)     /* 预设受油量值 */
#define REDUN_INDEX_RIU_FQ_TANK0       (9U)     /* 0号油箱油量值 */
#define REDUN_INDEX_RIU_FQ_TANK1       (10U)    /* 1号油箱油量值 */
#define REDUN_INDEX_RIU_FQ_TANK2       (11U)    /* 2号油箱油量值 */
#define REDUN_INDEX_RIU_FQ_TANK3       (12U)    /* 3号油箱油量值 */
#define REDUN_INDEX_RIU_FQ_TANK4       (13U)    /* 4号油箱油量值 */
#define REDUN_INDEX_RIU_TOTAL_FUEL     (14U)    /* 全机总油量 */
#define REDUN_INDEX_RIU_AIR_SPEED      (15U)    /* 指示空速 */
#define REDUN_INDEX_RIU_OIL_MD         (16U)    /* 燃油密度 */
#define REDUN_INDEX_RIU_LP_PFV         (17U)    /* 左吊舱预选油量值 */
#define REDUN_INDEX_RIU_RP_PFV         (18U)    /* 右吊舱预选油量值 */
#define REDUN_INDEX_RIU_MAINT_CMD      (19U)    /* 维护指令 */
#define REDUN_INDEX_RIU_WHEEL_LOAD     (20U)    /* 轮载状态 */
#define REDUN_INDEX_RIU_MBIT_EXEC      (21U)    /* 执行维护BIT */
#define REDUN_INDEX_RIU_SOFTV_REQ      (22U)    /* 软件版本请求信息 */
#define REDUN_INDEX_RIU_OIL_RESET      (23U)    /* 油量重置 */
#define REDUN_INDEX_RIU_LIFE_INFO      (24U)    /* 发送寿命信息原始值 */
#define REDUN_INDEX_RIU_CTRL_CMD       (25U)    /* 控制指令原始值 */
#define REDUN_INDEX_RIU_LP_BRIGHT      (26U)    /* 左吊舱通道灯亮度调节 */
#define REDUN_INDEX_RIU_RP_BRIGHT      (27U)    /* 右吊舱通道灯亮度调节 */
#define REDUN_INDEX_RIU_SC_CONFIG      (28U)    /* 软件部署兼容位 */

#define REDUN_INDEX_KZZZ_L_CURR_TIME_REQ (29U)    /* 左吊舱请求当前时间 */
#define REDUN_INDEX_KZZZ_L_MBIT_FB       (30U)    /* 左吊舱维护BIT执行反馈 */
#define REDUN_INDEX_KZZZ_L_MBIT_INFO1    (31U)    /* 左吊舱维护BIT结果1 */
#define REDUN_INDEX_KZZZ_L_SOFTV_APP     (32U)    /* 左吊舱控制装置应用软件版本 */
#define REDUN_INDEX_KZZZ_L_SOFTV_MC      (33U)    /* 左吊舱电驱动控制器软件版本 */
#define REDUN_INDEX_KZZZ_L_SOFTV_SIGBOX  (34U)    /* 左吊舱油量测量信号盒软件版本 */
#define REDUN_INDEX_KZZZ_L_SOFTV_BRAKE   (35U)    /* 左吊舱电液刹车驱动控制器软件版本 */
#define REDUN_INDEX_KZZZ_L_SOFTV_BITAPP  (36U)    /* 左吊舱自检测装置应用软件版本 */
#define REDUN_INDEX_KZZZ_L_SOFTV_LOGIC   (37U)    /* 左吊舱控制装置逻辑软件版本 */
#define REDUN_INDEX_KZZZ_L_SOFTV_UPGRADE (38U)    /* 左吊舱控制装置在线升级应用软件版本 */
#define REDUN_INDEX_KZZZ_L_SOFTV_MLOGIC  (39U)    /* 左吊舱电驱动控制器逻辑软件版本 */
#define REDUN_INDEX_KZZZ_L_PRE_FUEL_FB   (40U)    /* 左吊舱预选油量接收反馈 */
#define REDUN_INDEX_KZZZ_L_FLIGHT_HOURS  (41U)    /* 左吊舱剩余飞行小时 */
#define REDUN_INDEX_KZZZ_L_REMAIN_LIFE   (42U)    /* 左吊舱剩余日历寿命 */
#define REDUN_INDEX_KZZZ_L_RG_LEN        (43U)    /* 左吊舱软管长度 */
#define REDUN_INDEX_KZZZ_L_STATE         (44U)    /* 左吊舱加油装置状态 */
#define REDUN_INDEX_KZZZ_L_COMPONENT     (45U)    /* 左吊舱部件状态 */
#define REDUN_INDEX_KZZZ_L_FAULT_INFO    (46U)    /* 左吊舱故障告警 */
#define REDUN_INDEX_KZZZ_L_TURBINE_SPEED (47U)    /* 左吊舱涡轮转速 */
#define REDUN_INDEX_KZZZ_L_FUEL_PRESS    (48U)    /* 左吊舱加油压力 */
#define REDUN_INDEX_KZZZ_L_FUEL_TEMP     (49U)    /* 左吊舱燃油温度 */
#define REDUN_INDEX_KZZZ_L_TP_PRESS      (50U)    /* 左吊舱涡轮泵出口压力 */
#define REDUN_INDEX_KZZZ_L_FUEL_FLOW     (51U)    /* 左吊舱加油流量 */
#define REDUN_INDEX_KZZZ_L_FUEL_LEVEL    (52U)    /* 左吊舱已加油量 */
#define REDUN_INDEX_KZZZ_L_TOTAL_FUEL    (53U)    /* 左吊舱累计加油量 */

#define REDUN_INDEX_KZZZ_R_CURR_TIME_REQ (54U)    /* 右吊舱请求当前时间 */
#define REDUN_INDEX_KZZZ_R_MBIT_FB       (55U)    /* 右吊舱维护BIT执行反馈 */
#define REDUN_INDEX_KZZZ_R_MBIT_INFO1    (56U)    /* 右吊舱维护BIT结果1 */
#define REDUN_INDEX_KZZZ_R_SOFTV_APP     (57U)    /* 右吊舱控制装置应用软件版本 */
#define REDUN_INDEX_KZZZ_R_SOFTV_MC      (58U)    /* 右吊舱电驱动控制器软件版本 */
#define REDUN_INDEX_KZZZ_R_SOFTV_SIGBOX  (59U)    /* 右吊舱油量测量信号盒软件版本 */
#define REDUN_INDEX_KZZZ_R_SOFTV_BRAKE   (60U)    /* 右吊舱电液刹车驱动控制器软件版本 */
#define REDUN_INDEX_KZZZ_R_SOFTV_BITAPP  (61U)    /* 右吊舱自检测装置应用软件版本 */
#define REDUN_INDEX_KZZZ_R_SOFTV_LOGIC   (62U)    /* 右吊舱控制装置逻辑软件版本 */
#define REDUN_INDEX_KZZZ_R_SOFTV_UPGRADE (63U)    /* 右吊舱控制装置在线升级应用软件版本 */
#define REDUN_INDEX_KZZZ_R_SOFTV_MLOGIC  (64U)    /* 右吊舱电驱动控制器逻辑软件版本 */
#define REDUN_INDEX_KZZZ_R_PRE_FUEL_FB   (65U)    /* 右吊舱预选油量接收反馈 */
#define REDUN_INDEX_KZZZ_R_FLIGHT_HOURS  (66U)    /* 右吊舱剩余飞行小时 */
#define REDUN_INDEX_KZZZ_R_REMAIN_LIFE   (67U)    /* 右吊舱剩余日历寿命 */
#define REDUN_INDEX_KZZZ_R_RG_LEN        (68U)    /* 右吊舱软管长度 */
#define REDUN_INDEX_KZZZ_R_STATE         (69U)    /* 右吊舱加油装置状态 */
#define REDUN_INDEX_KZZZ_R_COMPONENT     (70U)    /* 右吊舱部件状态 */
#define REDUN_INDEX_KZZZ_R_FAULT_INFO    (71U)    /* 右吊舱故障告警 */
#define REDUN_INDEX_KZZZ_R_TURBINE_SPEED (72U)    /* 右吊舱涡轮转速 */
#define REDUN_INDEX_KZZZ_R_FUEL_PRESS    (73U)    /* 右吊舱加油压力 */
#define REDUN_INDEX_KZZZ_R_FUEL_TEMP     (74U)    /* 右吊舱燃油温度 */
#define REDUN_INDEX_KZZZ_R_TP_PRESS      (75U)    /* 右吊舱涡轮泵出口压力 */
#define REDUN_INDEX_KZZZ_R_FUEL_FLOW     (76U)    /* 右吊舱加油流量 */
#define REDUN_INDEX_KZZZ_R_FUEL_LEVEL    (77U)    /* 右吊舱已加油量 */
#define REDUN_INDEX_KZZZ_R_TOTAL_FUEL    (78U)    /* 右吊舱累计加油量 */

#define REDUN_INDEX_CCDL_SYSST         (79U)    /* 系统状态数据 */
#define REDUN_INDEX_CCDL_CHTYPE        (80U)    /* 通道类型数据 */
#define REDUN_INDEX_CCDL_CHNVM         (81U)    /* 下次冷启动默认主通道ID */
#define REDUN_INDEX_CCDL_RADM          (82U)    /* 历史兼容字段2，保留索引 */
#define REDUN_INDEX_CCDL_SOFTVC        (83U)    /* DSP控制软件版本数据 */
#define REDUN_INDEX_CCDL_SOFTVO        (84U)    /* CCDL基础帧控制信息字 */
#define REDUN_INDEX_CCDL_SOFTVL        (85U)    /* CPLD逻辑软件版本数据 */

/* 余度数据状态宏定义 */
#define REDUN_DATA_STATE_1             (0x01U)  /* 数据来自通信1 */
#define REDUN_DATA_STATE_2             (0x02U)  /* 数据来自通信2 */
#define REDUN_DATA_STATE_3             (0x03U)  /* 数据来自通信3 */
#define REDUN_DATA_STATE_ERR           (0x00U)  /* 数据状态异常 */

/* 余度管理数据结构体 */
typedef struct _RedunData
{
    float  dataF_f;       /* 浮点数据 */
    Uint32 dataU_u32;      /* 整型数据 */
    Uint16 dataState_u16; /* 数据状态 */
} RedunData_t;

/**********************************************************************************/
/* 系统状态相关宏定义 */
#define SYS_STATE_0INIT          (0U)  /* 初始状态       */
#define SYS_STATE_1WORK          (1U)  /* 工作状态       */
#define SYS_STATE_2SAFETY        (2U)  /* 安全状态       */
#define SYS_STATE_3MAINTG        (3U)  /* 地面维护状态  */
#define SYS_STATE_4POWERDOWN     (4U)  /* 掉电状态          */

/************************/
/* 工作模式宏定义 */
#define WORK_MODE_NUM            (8U)  /* 工作模式数量   */

#define WORK_MODE_STANDBY            (0U)  /* 待机 */
#define WORK_MODE_LP_FIXEDWING       (1U)  /* 左吊舱固定翼加油模式 */
#define WORK_MODE_RP_FIXEDWING       (2U)  /* 右吊舱固定翼加油模式 */
#define WORK_MODE_LRP_FIXEDWING      (3U)  /* 左右吊舱固定翼加油模式 */
#define WORK_MODE_LP_HELI            (4U)  /* 左吊舱直升机加油模式 */
#define WORK_MODE_RP_HELI            (5U)  /* 右吊舱直升机加油模式 */
#define WORK_MODE_LRP_HELI           (6U)  /* 左右吊舱直升机加油模式 */
#define WORK_MODE_RECEIVE            (7U)  /* 受油模式 */

/************************/
/* 控制功能宏定义 */

#define CON_FUNC_0_STANDBY        (0U)  /* 待机控制 */
#define CON_FUNC_1_PRE_TASK_CHECK (1U)  /* 任务前状态检查 */
#define CON_FUNC_2_FUEL_PRESET    (2U)  /* 燃油预位控制 */
#define CON_FUNC_3_REFUEL_PROCESS (3U)  /* 加油过程控制 */
#define CON_FUNC_4_TASK_END       (4U)  /* 加油结束 */
#define CON_FUNC_5_MBIT           (5U)  /* 维护BIT流程 */

/************************/
/* 空中加油模式宏定义 */
#define AIR_OIL_MODE_L           (1U)  /* 空中低压加油    */
#define AIR_OIL_MODE_H           (2U)  /* 空中高压加油    */

/************************/
/* 控制功能迁入条件数目宏定义 */
#define MAINT_FUNC_0_INVALID     (0U)  /* 维护无效      */
#define MAINT_FUNC_1_MAINT       (1U)  /* 维护功能      */
#define MAINT_FUNC_2_CON         (2U)  /* 地面控制      */

#define CON_MODE_AUTO            (0U)  /* 自动控制模式      */
#define CON_MODE_MANUUAL         (1U)  /* 手动控制模式      */

#define CON_MODE_FLAG_INVALID    (0U)  /* 手动控制切换标志无效      */
#define CON_MODE_FLAG_VALID      (1U)  /* 手动控制切换标志有效      */

/************************/
/* 通道ID */
#define SYS_CH_ID_1              (1U)  /* 通道1 */
#define SYS_CH_ID_2              (2U)  /* 通道2 */

/************************************************************************/
/* 通道类型宏定义 */
#define CH_TYPE_INIT             (0U)  /* 通道类型为初始通道  */
#define CH_TYPE_CON              (1U)  /* 通道类型为控制通道   */
#define CH_TYPE_BF               (2U)  /* 通道类型为备份通道   */

#define TYPEJUDGE_CODE_NONE      (0U)  /* 无效类型判别码值  */
#define TYPEJUDGE_CODE_OC        (1U)  /* 对方通道为控制 */
#define TYPEJUDGE_CODE_OM        (2U)  /* 对方通道为备份 */
#define TYPEJUDGE_CODE_ERR       (3U)  /* 启动期主备状态识别失败，已走兜底裁决 */
#define TYPEJUDGE_CODE_RAND      (4U)  /* 启动期轮值异常，已按随机数仲裁 */

#define TYPEJUDGE_CNT_MAX        (10U)  /* 通道类型判别最大次数 */


/************************************************************************/
/* 控制输出状态宏定义 */
#define CON_OUT_STATE_VALID     (0x1U)        /* 控制输出状态有效 */
#define CON_OUT_STATE_INVALID   (0x0U)        /* 控制输出状态无效 */

/************************************************************************/
/* 运行期控制权归属宏定义 */
#define ROLE_BACKUP             (0U)          /* 当前不持有控制权 */
#define ROLE_MASTER             (1U)          /* 当前持有控制权 */
#define ROLE_PEER_LOSS_TIMEOUT_MS (200U)      /* 对端基础帧失联判据窗口 */
#define CONTROL_OWNER_HOLD_MS   (100U)        /* 控制权切换确认保持窗口 */

/************************************************************************/
/* 空中加油结束状态宏定义 */
#define AIR_CON_END_STATE_INVALID        (0x0U)  /* 空中加油结束状态无效 */
/************************************************************************/
/* 通道有效信号CHV宏定义 */

#define CHV_VALID                 (0x01U)       /* 通道有效信号输出有效  */
#define CHV_INVALID               (0x00U)       /* 通道有效信号输出无效  */

#define WDV_IN_NOMAL              (0x01U)     /* WDV正常  */
#define CPUV_IN_NOMAL             (0x01U)     /* CPUV正常  */
#define CPUV_IN_ERR               (0x00U)     /* CPUV异常  */

#define LATCH_EN_VALID            (0x01U)     /* 锁存使能有效  */

/************************************************************************/
/* 时间门限值相关宏定义 */


/************************/
/* 加油泵闭环控制宏定义 */
#define AIROIL_JYB_SPEED_H      (9300)  /* 加油泵转速上限，单位rmp  */

#define AIROIL_JYB_SPEED_STEP_H (200.0F)  /* 压力调节加油泵转速快步长 ，单位rmp  */
#define AIROIL_FLOW_MAX_H       (2400UL)  /*  高压加油瞬时流量体积上限，单位L/min  */

/************************/
/* 泵打开转速宏定义 */
#define OPEN_SPEED_AIR_H        (7600U)  /* 高压空中加油打开转速           */

/************************************************************************/
/* 压力控制相关宏定义 */


/***************************************************************************/
/* 舱门控制到位宏定义 */
#define VALID					(1U)
#define INVALID					(0U)




/************************************************************************/
/* 维护开关状态宏定义 */
#define MAINT_IO_VALID          (0x00U)       /* 维护开关有效  */
#define MAINT_IO_INVALID        (0x01U)       /* 维护开关无效  */

/* NMI中断源类型宏定义 */
#define NMI_SOURCE_POWER_DOWN   (0x11U)      /* NMI中断源为28V掉电      */
#define NMI_SOURCE_WDOG_RESET   (0x22U)      /* NMI中断源为看门狗复位   */
#define NMI_SOURCE_AB_NORMAL    (0x33U)      /* NMI中断源为异常复位      */

#define POWERDOWN_FLAG_INVALID  (0U)    /* 28V掉电标志无效 */
#define POWERDOWN_FLAG_VALID    (1U)    /* 28V掉电标志有效 */
#define POWERDOWN_FLAG_PENDING  (2U)    /* 28V掉电NMI已触发，等待主循环确认 */

#define POWERDOWN_COND_INVALID  (0U)    /* 掉电状态切换条件无效                 */
#define POWERDOWN_COND_ENTER    (1U)    /* 掉电状态切换条件进入掉电状态  */
#define POWERDOWN_COND_OUT      (2U)    /* 掉电状态切换条件退出掉电状态  */

#define POWERDOWN_FLAG_CLR_COUNT_MAX    (20U)     /* 掉电标志清除计数最大值 */

/************************************************************************/
/* 维护相关宏定义 */
#define MAINT_GROUND_IN_COND_INVALID    (0U)    /* 地面维护进入条件无效    */
#define MAINT_GROUND_IN_COND_VALID      (1U)    /* 地面维护进入条件有效    */
#define MAINT_GROUND_IN_COND_FORCE      (2U)    /* 地面维护强制进入(超时升级) */
#define MAINT_FORCE_ENTER_MS (5000UL)    /* 维护条件持续保持升级为强制的时间 */

#define COND_IN_INVALID                 (0U)    /* 进入条件无效    */
#define COND_IN_VALID                   (1U)    /* 进入条件有效    */

/* 地面维护指令执行状态  */
#define MAINT_CMD_EXE_DONE              (0x1234U)       /* 维护指令执行结束     */
#define MAINT_CMD_EXE_NEW               (0x0000U)       /* 维护指令执行未结束，有新指令 */

/************************************************************************/

#define COMM_SOURCE_1                   (0U)       /* 数据来源于通信1，默认值  */
#define COMM_SOURCE_2                   (1U)       /* 数据来源于通信2  */
#define COMM_SOURCE_3                   (2U)       /* 数据来源于通信3  */
#define COMM_SOURCE_INVALID             (3U)       /* 当前无有效通信来源 */



/************************************************************************/
/* 429通信非周期发送标志宏定义（待联试收敛）*/
#define COMM_APERI_TX_FLAG_INVALID      (0UL)  /* 429通信非周期发送标志无效 */


/* ***************************************************************** */
/* 受油模式相关常量定义 */
#define RECEIVE_VALVE_STATE_OPEN            (0x01U)
#define RECEIVE_VALVE_STATE_CLOSED          (0x02U)
#define RECEIVE_ST_STATE_RECEIVE_POS        (RECEIVE_VALVE_STATE_OPEN)    /* 三通阀反馈：受油位 */
#define RECEIVE_ST_STATE_CLOSED_POS         (RECEIVE_VALVE_STATE_CLOSED)  /* 三通阀反馈：关闭位 */
#define RECEIVE_ST_CMD_CLOSED_POS           (0U)                          /* 三通阀命令：关闭位 */
#define RECEIVE_ST_CMD_RECEIVE_POS          (1U)                          /* 三通阀命令：受油位 */
#define RECEIVE_TANK_COUNT                  (5U)
#define RECEIVE_COMPLETE_DELAY_MS           (10000UL)
#define RECEIVE_IMBALANCE_THRESHOLD_KG      (1200.0F)

enum
{
    RECEIVE_RIU_STATE_IDLE = 0U,
    RECEIVE_RIU_STATE_REQUEST_PRESET = 1U,
    RECEIVE_RIU_STATE_ACTIVE = 2U,
    RECEIVE_RIU_STATE_COMPLETE = 3U,
    RECEIVE_RIU_STATE_FAULT = 4U
};

enum
{
    RECEIVE_RIU_REASON_NONE = 0U,
    RECEIVE_RIU_REASON_HL_SENSOR = 1U,
    RECEIVE_RIU_REASON_MEASURE = 2U,
    RECEIVE_RIU_REASON_IMBALANCE = 3U,
    RECEIVE_RIU_REASON_PRESET_FAIL = 4U,
    RECEIVE_RIU_REASON_VALVE_TIMEOUT = 5U
};

/* 4.2.7 需求定义的受油分配阈值与时间 */
#define RECEIVE_ALLOC_MAX_TOTAL_KG          (33000.0F)  /* 最大预设受油总量 */
#define RECEIVE_ALLOC_TIER_LIMIT_KG         (16400.0F)  /* 单双轨分配逻辑分界点 */
#define RECEIVE_ALLOC_WING_TANK_MAX_KG      (4100.0F)   /* 1/2/3/4号油箱单体定额上限 */

typedef struct
{
    float  presetTotalKg_f;		// 预设总量
    float  perTankTargetKg_f[RECEIVE_TANK_COUNT];// 各油箱目标量
    float  initialTotalKg_f;	// 初始总量
    Uint16 presetReady_u16;		// 预设准备完成标志
    Uint16 rcvCloseMask_u16;	// 受油关闭油箱掩码
    Uint32 rcvCloseCmdTime_u32[RECEIVE_TANK_COUNT]; // 记录各个活门下发关闭指令的时间
    Uint16 faultActive_u16;		// 故障激活标志
    Uint16 faultCloseAllRcv_u16; // 故障期间是否保持全部RCV关闭
    Uint16 completionIssued_u16;// 完成指令已发出标志
    Uint16 completionSettled_u16;	// 完成状态已确认标志
    Uint32 completionTimestamp_u32;// 完成时间戳
} ReceiveModeContext_t;

typedef struct
{
    Uint16 commandIssued_u16;  /* 任务前检查命令已下发标志 */
    Uint16 rcvChecked_u16;     /* RCV关闭状态检查结果 */
    Uint16 valveChecked_u16;   /* 阀位关闭状态检查结果 */
    Uint16 measureChecked_u16; /* 测量系统状态检查结果 */
    Uint16 rcvTimeoutFault_u16;    /* RCV超时故障标志 */
    Uint16 valveTimeoutFault_u16;  /* 阀位超时故障标志 */
    Uint16 measureFault_u16;       /* 测量系统故障标志 */
} PreTaskCheckContext_t;

/************************************************************************/

/* 燃油预位子状态与供油决策 */
#define REFUEL_TARGET_TANK0          (1U)
#define REFUEL_TARGET_TANK23         (2U)
#define REFUEL_TARGET_LRP_ALL        (3U)

/* 加油过程供油切断阀状态 */
#define SUPPLY_SOURCE_TANK0          (0U)
#define SUPPLY_SOURCE_TANK23         (2U)

/* 加油过程平衡控制状态 */
#define BALANCING_VALVE_NONE         (0U)
#define BALANCING_VALVE_TANK2_CLOSED (2U)
#define BALANCING_VALVE_TANK3_CLOSED (3U)

typedef struct
{
    Uint16 targetTank_u16;           /* 目标供油油箱选择 (0:未决/1:0号/2:2_3号/3:LRP) */
    Uint16 commandSent_u16;          /* 预位指令已发送标志 */
    Uint16 presetReady_u16;          /* 燃油预位完成标志 */
    Uint16 supplySource_u16;         /* 实际供油源追踪 */
    Uint16 balancingValveClosed_u16; /* 当前因不平衡而被关闭的阀门 */
} RefuelModeContext_t;

/* ***************************************************************** */
/* 核心控制流程关联结构体提取自 Control.c */

typedef struct _ControlFaultEval
{
    Uint16 commFault_u16;      /* RIU通信故障 */
    Uint16 measureFault_u16;   /* 油量测量链路故障 */
    Uint16 imbalanceFault_u16; /* 油量不平衡故障 */
    Uint16 hasFault_u16;       /* 综合故障标志 */
    Uint16 reason_u16;         /* 故障原因码 */
} ControlFaultEval_t;

typedef struct _ControlFaultDebounce
{
    Uint16 commCnt_u16;        /* 通信故障连续计数 */
    Uint16 measureCnt_u16;     /* 测量故障连续计数 */
    Uint16 imbalanceCnt_u16;   /* 不平衡故障连续计数 */
} ControlFaultDebounce_t;

typedef struct _ControlModeDebounce
{
    Uint16 candidateMode_u16;  /* 当前候选工作模式 */
    Uint16 stableCnt_u16;      /* 候选模式连续稳定计数 */
} ControlModeDebounce_t;

/* 故障过滤与模式切换常量 */
#define CONTROL_FAULT_CONFIRM_CYCLES (3U) /* 故障确认拍数，避免单拍抖动误触发 */
#define CONTROL_FAULT_CLEAR_CYCLES (20U) /* 故障解除确认拍数，避免恢复抖动 */
#define CONTROL_FAULT_RECOVERY_COOLDOWN_CYCLES (30U) /* 故障恢复后冷却拍数，避免立刻重触发 */
#define CONTROL_MODE_SWITCH_CONFIRM_CYCLES (2U) /* 模式切换确认拍数，避免单拍指令抖动误切换 */
#define CONTROL_MAINT_ENTER_CONFIRM_MS (1000UL) /* 维护进入指令连续确认时间 */
#define PRE_TASK_CHECK_TIMEOUT_MS (5000UL) /* 任务前检查确认超时时间 */
#define INIT_STATE_TIMEOUT_MS (10000UL) /* 上电初始化态最大停留时间,超时强制进入安全态 */
/************************************************************************/

union CHVInInfo
{
    Uint16  all;        /* 控制信号数据 */
    struct{
        Uint16 myCHV_u16:1U;        /* bit0:本端运行期授权使用的本地CHV有效位，当前由localChvPermit代理写回 */
        Uint16 otherCHV_u16:1U;     /* bit1:对端CHV输入采样，当前来源为GPIO_IN_DSP_CHV */
        Uint16 WDV_u16:1U;          /* bit2:复位信号反馈   */
        Uint16 CPUV_u16:1U;         /* bit3:CPUV信号反馈  */
        Uint16 LATCH_EN_u16:1U;     /* bit4:锁存使能状态  */
        Uint16 rsvdHand_u16:1U;     /* bit5:握手成功反馈，暂时保留 */
        Uint16 otherHeart_u16:1U;   /* bit6:对方通道心跳 */
        Uint16 rsvd:9U;             /* bit7-15:预留 */
    }bit; /* 控制信号数据位域 */
};
typedef struct _ConOutData /* 控制输出数据结构体   */
{
	Uint16 conOutState_u16;  /* 控制输出状态         */
	Uint16 localChvPermit_u16; /* 本端CHV资格判据，同时作为运行期myCHV替代源 */
}ConOutData_Type;

union commDataSourse  /* 通信数据来源，用于表示当前数据采用哪一通信路数据  */
{
    Uint16  all;        /* 通信数据来源 */
    struct{
        Uint16 RIU:2U;   /* bit0-1:RIU通信数据来源编码 */
        Uint16 CCDL:2U;  /* bit2-3:CCDL通信数据来源编码 */
        Uint16 KZZZ:2U;  /* bit4-5:KZZZ通信数据来源编码，COMM_SOURCE_3 表示对端经CCDL镜像来源 */
        Uint16 rsvd:10U; /* bit6-15:预留 */
    }bit; /* 通信数据来源位域 */
};

/*******************************************/
/* 系统控制数据   */
typedef struct _ConData
{
    Uint16  ChType_u16;      /* 静态主备身份，仅由启动判型确定     */
    Uint16  ChTypeCode_u16;  /* 通道类型判别结果码，TYPEJUDGE_CODE_ERR表示主备状态识别故障 */
    Uint16  myChID_u16;      /* 本通道ID号  */
    Uint16  localPreferredMasterChId_u16; /* 本端记录的冷启动默认主通道ID */
    Uint16  peerPreferredMasterChId_u16;  /* 对端基础帧上报的冷启动默认主通道ID */
    Uint16  arbMasterChId_u16;       /* 本次启动仲裁得到的主通道ID */

    /*******************************************************************/
    Uint16 sysState_u16;        /* 系统状态                           */
    Uint16 sysStateLast_u16;    /* 系统状态上一拍,状态切换时更新    */

    Uint16 workMode_u16;        /* 工作模式      */
    Uint16 workModeLast_u16;    /* 工作模式上一拍,模式切换时更新   */

    Uint16 conFunc_u16;         /* 控制功能      */
    Uint16 conFuncLast_u16;     /* 上一拍控制功能,功能切换时更新      */
    Uint16 conMode_u16;         /* 控制模式      */
    Uint16 conModeFlag_u16;     /* 控制模式切换标志      */
    Uint16 maintFunc_u16;       /* 地面维护功能      */

    Uint16 OilMode_u16;         /* 高低压加油模式  */
    Uint16 airOilEndState_u16;  /* 空中加油结束状态     */
    Uint32 workModeTime_u32;    /* 工作模式开始时间ms */
    Uint16 runtimeRole_u16;     /* 动态控制权归属：MASTER=当前持有控制权，BACKUP=当前不持有控制权 */
    Uint32 roleEnterTime_u32;   /* 当前控制权归属进入时间，供诊断和保持窗口计时 */
    Uint16 peerAlive_u16;       /* 当前拍对端基础帧在线状态，仅作诊断使用 */
    Uint16 peerCtrlSeen_u16;    /* 当前拍是否观测到对端持有控制权，仅作诊断与控制权切换依据 */

    union commDataSourse commDataSourse_un16;  /* 通信数据来源  */

    Uint16 sysWorkTime_u16;        /* 系统单次工作时间,单位min，按照本次上电工作时间ms转换成min获取  */
    Uint16 sysWorkTimeSum_u16;     /* 系统累计工作时间,单位min */

    /*******************************************************************/
    ConOutData_Type ConOutData_t;  /* 控制输出数据     */
    union CHVInInfo CHVIn_un16;    /* 通道有效输入信号  */

    /*******************************************************************/
    Uint32 Comm429_Aperi_Flag_u32; /* 429通信非周期发送标志 */

}ConData_t;

/* ***************************************************************** */
/**
 * 供外部调用函数接口
 */
/* ***************************************************************** */

extern const RIU429SendData_t* RIU429SendDataGet(void);
extern const ConData_t* ConDataGet(void);
extern void   SysControl(void);
extern void   SysControlPowerDown(void);
extern void   SysConInit(void);
extern Uint16 SysWorkTimeGet(void);
extern void   MaintCMDExeStateClear(Uint16 v_exeState_u16);
extern void   ChTypeJudge(void);
extern void   ChTypeRoundRobinCommitColdStartup(void);
extern Uint16 RandomDataGenerate(void);
extern void   SysControlOut(void);
extern void Comm429KZZZPeriodInfoTx(void);
extern ControlFaultEval_t ControlFaultEvalGet(void);
extern Uint16 ControlErrStoreFlagGet(void);
/* ***************************************************************** */
/**
 * 余度与通道管理接口 (Control_Redundancy.c)
 */
/* ***************************************************************** */
extern void RedundancyInit(void);
extern void Redundancy(void);
extern RedunData_t RedunDataGet(Uint16 v_index_u16);

#endif /* CONTROL_H_ */

/* ========================================================================== */
/* 文件结束 */
/* ========================================================================== */
