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
 * 文件名称:    Comm429KZZZ.h
 *
 * 文件日期:   REDACTED
 *
 *
 * 程序版本:   V2.00
 *
 **********************************************************************************
 *
 * 功能说明:   功能说明
 *
 *
 *********************************************************************************/

#ifndef COMM429KZZZ_H

#define COMM429KZZZ_H

#include "CommDRI_429.h"

/******************************************************************/
/****************************发送（控制器 -> KZZZ）*****************************/
/* 发送报文标号，均为八进制  */
#define KZZZ_T_DATA_NUM                 (9U)   /* 发送标签个数 */

#define KZZZ_LABEL_T_CURR_DATE       (0261U) /* 当前日期 */
#define KZZZ_LABEL_T_CURR_TIME       (0262U) /* 当前时间 */
#define KZZZ_LABEL_T_MBIT_RUN        (0263U) /* 执行维护BIT */
#define KZZZ_LABEL_T_PZXX            (0264U) /* 发送配置信息 */
#define KZZZ_LABEL_T_PRE_FUEL        (0265U) /* 预选油量 */
#define KZZZ_LABEL_T_FUEL_DENSITY    (0266U) /* 燃油密度 */
#define KZZZ_LABEL_T_CTRL_CMD        (0267U) /* 控制指令 */
#define KZZZ_LABEL_T_LIFE_INFO       (0270U) /* 发送寿命信息 */
#define KZZZ_LABEL_T_FUEL_RESET      (0271U) /* 油量重置 */


/*************************************/
#define KZZZ_R_DATA_NUM                 (31U)   /* 接收标签个数 */

#define KZZZ_R_DATA_CURRENT_TIME             (0U)  /* 请求当前时间 */
#define KZZZ_R_DATA_MAINTENANCE_BIT_FB       (1U)  /* 维护BIT执行反馈 */
#define KZZZ_R_DATA_UPLOAD_MAINTENANCE_BIT   (2U)  /* 上传维护BIT结果 */
#define KZZZ_R_DATA_CTRL_SW_VERSION          (3U)  /* 控制装置应用软件版本信息（401） */
#define KZZZ_R_DATA_MOTOR_CTRL_SW_VERSION    (4U)  /* 电驱动控制器软件版本信息（402） */
#define KZZZ_R_DATA_FUEL_LEVEL_SIGNAL_BOX    (5U)  /* 油量测量信号盒软件版本信息（403） */
#define KZZZ_R_DATA_BRAKE_CTRL_SW_VERSION    (6U)  /* 电液刹车驱动控制器软件版本信息（404） */
#define KZZZ_R_DATA_BIT_APP_SW_VERSION       (7U)  /* 自检测装置应用软件版本信息（405） */
#define KZZZ_R_DATA_LOGIC_SW_VERSION         (8U)  /* 控制装置逻辑软件版本信息（406） */
#define KZZZ_R_DATA_UPGRADE_APP_SW_VERSION   (9U)  /* 控制装置在线升级应用软件版本信息（407） */
#define KZZZ_R_DATA_MOTOR_LOGIC_SW_VERSION   (10U) /* 电驱动控制器逻辑软件版本信息（408） */
#define KZZZ_R_DATA_SEL_FUEL_RECEIVE_FB      (11U) /* 预选油量接收反馈 */
#define KZZZ_R_DATA_REMAINING_FLIGHT_HRS     (12U) /* 剩余飞行小时 */
#define KZZZ_R_DATA_REMAINING_CALENDAR_LIFE  (13U) /* 剩余日历寿命 */
#define KZZZ_R_DATA_FUEL_RESET_RECEIVE_FB    (14U) /* 油量重置接收反馈 */
#define KZZZ_R_DATA_TURBINE_SPEED            (15U) /* 涡轮转速 */
#define KZZZ_R_DATA_FUEL_PRESSURE            (16U) /* 加油压力 */
#define KZZZ_R_DATA_TURBINE_PUMP_PRESSURE    (17U) /* 涡轮泵出口压力 */
#define KZZZ_R_DATA_FUEL_FLOW                (18U) /* 加油流量 */
#define KZZZ_R_DATA_FUEL_LEVEL               (19U) /* 已加油量 */
#define KZZZ_R_DATA_TOTAL_FUEL               (20U) /* 累计加油量 */
#define KZZZ_R_DATA_FUEL_TEMP                (21U) /* 燃油温度 */
#define KZZZ_R_DATA_RG_LEN                   (22U) /* 软管长度 */
#define KZZZ_R_DATA_COMPONENT_STATUS         (23U) /* 部件状态 */
#define KZZZ_R_DATA_FAULT_WARN               (24U) /* 故障告警 */
#define KZZZ_R_DATA_FAULT_WARN_I             (25U) /* 故障信息Ⅰ */
#define KZZZ_R_DATA_FAULT_WARN_II            (26U) /* 故障信息Ⅱ */
#define KZZZ_R_DATA_REFUEL_DEV_STATE         (27U) /* 加油设备状态 0250 */
#define KZZZ_R_DATA_CMD_SIGNAL_FB            (28U) /* 指令信号反馈 0255 */
#define KZZZ_R_DATA_MOTOR_SPEED              (29U) /* 电驱动电机转速 0256 */
#define KZZZ_R_DATA_MOTOR_TEMP               (30U) /* 电驱动控制器温度 0257 */

/****************************接收（KZZZ -> 控制器）*****************************/
/* 接收报文标号，均为八进制  */
#define KZZZ_LABEL_R_CURRENT_TIME            (0227U) /* 请求当前时间 */
#define KZZZ_LABEL_R_MAINTENANCE_BIT_FB      (0230U) /* 维护BIT执行反馈 */
#define KZZZ_LABEL_R_UPLOAD_MAINTENANCE_BIT  (0231U) /* 上传维护BIT结果 */
#define KZZZ_LABEL_R_REMAINING_FLIGHT_HRS    (0232U) /* 剩余飞行小时 */
#define KZZZ_LABEL_R_REMAINING_CALENDAR_LIFE (0233U) /* 剩余日历寿命 */
#define KZZZ_LABEL_R_CTRL_SW_VERSION         (0234U) /* 应用软件版本 */
#define KZZZ_LABEL_R_MOTOR_CTRL_SW_VERSION   (0235U) /* 电驱动软件版本 */
#define KZZZ_LABEL_R_FUEL_LEVEL_SIGNAL_BOX   (0236U) /* 信号盒软件版本 */
#define KZZZ_LABEL_R_SEL_FUEL_RECEIVE_FB     (0237U) /* 预选油量反馈 */
#define KZZZ_LABEL_R_TURBINE_SPEED           (0240U) /* 涡轮转速 */
#define KZZZ_LABEL_R_FUEL_PRESSURE           (0241U) /* 加油压力 */
#define KZZZ_LABEL_R_TURBINE_PUMP_PRESSURE   (0242U) /* 泵出口压力 */
#define KZZZ_LABEL_R_FUEL_FLOW               (0243U) /* 加油流量 */
#define KZZZ_LABEL_R_FUEL_LEVEL              (0244U) /* 已加油量 */
#define KZZZ_LABEL_R_TOTAL_FUEL              (0245U) /* 累计加油量 */
#define KZZZ_LABEL_R_FUEL_TEMP               (0246U) /* 燃油温度 */
#define KZZZ_LABEL_R_RG_LEN                  (0247U) /* 软管长度 */
#define KZZZ_LABEL_R_REFUEL_DEV_STATE        (0250U) /* 加油设备状态 */
#define KZZZ_LABEL_R_COMPONENT_STATUS        (0251U) /* 部件状态 */
#define KZZZ_LABEL_R_FAULT_WARN              (0252U) /* 故障告警 */
#define KZZZ_LABEL_R_FAULT_WARN_I            (0253U) /* 故障信息Ⅰ */
#define KZZZ_LABEL_R_FAULT_WARN_II           (0254U) /* 故障信息Ⅱ */
#define KZZZ_LABEL_R_CMD_SIGNAL_FB           (0255U) /* 指令信号反馈 */
#define KZZZ_LABEL_R_MOTOR_SPEED             (0256U) /* 电驱动电机转速 */
#define KZZZ_LABEL_R_MOTOR_TEMP              (0257U) /* 电驱动控制器温度 */
#define KZZZ_LABEL_R_FUEL_RESET_RECEIVE_FB   (0260U) /* 油量重置反馈 */
#define KZZZ_LABEL_R_BRAKE_CTRL_SW_VERSION   (0272U) /* 刹车驱动版本 */
#define KZZZ_LABEL_R_BIT_APP_SW_VERSION      (0273U) /* 自检应用版本 */
#define KZZZ_LABEL_R_LOGIC_SW_VERSION        (0274U) /* 逻辑软件版本 */
#define KZZZ_LABEL_R_UPGRADE_APP_SW_VERSION  (0275U) /* 升级应用版本 */
#define KZZZ_LABEL_R_MOTOR_LOGIC_SW_VERSION  (0276U) /* 电驱动逻辑版本 */

/*********************************/
/* 宏定义     */
#define AIR_SPEED_T_RATIO          (0.1F) /* 发送空速转换比例 */
#define KZZZ_RG_LENGTH_R_RATIO     (10.0F) /* 接收软管长度转换比例 */

#define KZZZ_SOFTV_NUM              (8U)    /* 控制装置软件版本数目 */

#define KZZZ_SOFTV_INDEX_APP               (0U)
#define KZZZ_SOFTV_INDEX_MOTOR_CTRL        (1U)
#define KZZZ_SOFTV_INDEX_SIGNAL_BOX        (2U)
#define KZZZ_SOFTV_INDEX_BRAKE_CTRL        (3U)
#define KZZZ_SOFTV_INDEX_BIT_APP           (4U)
#define KZZZ_SOFTV_INDEX_LOGIC             (5U)
#define KZZZ_SOFTV_INDEX_UPGRADE_APP       (6U)
#define KZZZ_SOFTV_INDEX_MOTOR_LOGIC       (7U)

/******************************************************************/
/* 接收数据宏定义及结构体     */
/********************************************/
/* 请求当前时间宏定义     */
#define KZZZ_TIME_REQUEST_VALID     (1U)
#define KZZZ_TIME_REQUEST_INVALID   (0U)

/********************************************/
/* 加电BIT反馈宏定义 */
#define KZZZ_PUBIT_FB_PASS          (0UL)
#define KZZZ_PUBIT_FB_FAIL          (1UL)

/* 加电BIT反馈结构体 (Label 227) */
typedef union{
	Uint32 all;
	struct{
		Uint32 rsvd_1_u32:11U;          /* bit0-10:预留 */
		Uint32 puBitRequest_u32:1U;     /* bit11:请求当前时间 */
		Uint32 puBitResult_u32:1U;      /* bit12:加电BIT结果 */
		Uint32 rsvd_2_u32:19U;          /* bit13-31:预留 */
	} bit;
}KZZZPuBITFb_t;

/********************************************/
/* 维护BIT执行反馈宏定义     */
#define KZZZ_MBIT_INVALID       (0U)
#define KZZZ_MBIT_UNDONE        (1U)
#define KZZZ_MBIT_UNKNOWN       (2U)
#define KZZZ_MBIT_TEST_FORBID   (3U)
#define KZZZ_MBIT_PASS          (4U)
#define KZZZ_MBIT_FAIL          (5U)

/********************************************/
/* 维护BIT结果1结构体 (Label 231) */
typedef union{
	Uint32 all;
	struct{
		Uint32 rsvd_1_u32:11U;           /* bit0-10:预留 */
		Uint32 mBitResult_u32:2U;        /* bit11-12:测试结果 */
		Uint32 rsvd_2_u32:19U;           /* bit13-31:预留 */
	} bit;
}KZZZMBITData1_t;


/* 加油设备状态结构体 (Label 0250)
 * ICD: bit11-12 工作状态(00全收藏/01拖曳/10加油响应/11回绕)
 *      bit13 工作模式 1手动/0自动
 *      bit14 信号灯模式 1隐蔽/0正常
 *      bit15-16 红色信号灯  bit17-18 黄色信号灯  bit19-20 绿色信号灯
 *      bit22 电驱控制器反馈地面维护状态  bit23 吊舱系统地面维护状态
 */
typedef union{
	Uint32 all;
	struct{
		Uint32 rsvd_0_u32:10U;                 /* bit0-9:预留(SDI/帧位) */
		Uint32 workState_u32:2U;               /* bit11-12:工作状态 */
		Uint32 workMode_u32:1U;                /* bit13:工作模式 */
		Uint32 ledMode_u32:1U;                 /* bit14:信号灯模式 */
		Uint32 redLed_u32:2U;                  /* bit15-16:红色信号灯 */
		Uint32 yellowLed_u32:2U;               /* bit17-18:黄色信号灯 */
		Uint32 greenLed_u32:2U;                /* bit19-20:绿色信号灯 */
		Uint32 rsvd_1_u32:1U;                  /* bit21:预留 */
		Uint32 motorCtrlMaintMode_u32:1U;      /* bit22:电驱控制器反馈地面维护状态 */
		Uint32 podSystemMaintMode_u32:1U;      /* bit23:吊舱系统地面维护状态 */
		Uint32 rsvd_2_u32:8U;                  /* bit24-31:预留 */
	} bit;
}KZZZState_t;

/********************************************/
/* 指令信号反馈结构体 (Label 0255, DISC)
 * ICD: bit11 主开关、bit12 软管、bit13 回油、bit14 投放软管、bit15 紧急脱离
 *      bit19 工作模式、bit20 手动加油、bit21 脱离
 */
typedef union{
    Uint32 all;
    struct{
        Uint32 rsvd_0_u32:10U;                  /* bit0-9:预留 */
        Uint32 masterSwitch_u32:1U;             /* bit11:主开关控制指令 */
        Uint32 hoseCtrl_u32:1U;                 /* bit12:软管控制指令 */
        Uint32 returnFuel_u32:1U;               /* bit13:回油指令 */
        Uint32 releaseHose_u32:1U;              /* bit14:投放软管指令 */
        Uint32 emergencyRelease_u32:1U;         /* bit15:紧急脱离指令 */
        Uint32 rsvd_1_u32:3U;                   /* bit16-18:预留 */
        Uint32 workModeCmd_u32:1U;              /* bit19:工作模式指令 */
        Uint32 manualRefuel_u32:1U;             /* bit20:手动加油指令 */
        Uint32 releaseCmd_u32:1U;               /* bit21:脱离指令 */
        Uint32 rsvd_2_u32:10U;                  /* bit22-31:预留 */
    } bit;
}CmdSignalFb_t;

/********************************************/
/* 电驱动电机转速换算 (Label 0256, BNR, 1 r/min, ±10000 r/min) */
#define KZZZ_MOTOR_SPEED_R_RATIO   (1.0F)
/* 电驱动控制器温度换算 (Label 0257, BNR, 1℃, -55~200℃) */
#define KZZZ_MOTOR_TEMP_R_RATIO    (1.0F)

/********************************************/
typedef union{
	Uint32 all;
	struct{
		Uint32 rsvd_0_u32:3U;              /* bit0-2:预留 */
		Uint32 drainValveOpen_u32:1U;      /* bit11:归算至 bit3 */
		Uint32 drainValveClose_u32:1U;     /* bit12:归算至 bit4 */
		Uint32 refuelValveOpen_u32:1U;     /* bit13:归算至 bit5 */
		Uint32 refuelValveClose_u32:1U;    /* bit14:归算至 bit6 */
		Uint32 rsvd_1_u32:25U;
	} bit;
}ComponentState_t;


/********************************************/
/* 故障告警结构体 (依据任务书精简) */
typedef union{
	Uint32 all;
	struct{
		Uint32 rsvd_1_u32:15U;              /* bit0-14:预留 */
		Uint32 rsvd_2_u32:17U;              /* bit15-31:预留 */
	} bit;
}FaultInfo_t;

/********************************************/
/* 故障信息Ⅰ结构体 (Label 253 / 故障信息Ⅰ) */
typedef union{
    Uint32 all;
    struct{
        Uint32 rsvd_1_u32:11U;                  /* bit0-10:预留 */
        Uint32 cmdSignalFault_u32:1U;           /* bit11:指令信号异常 */
        Uint32 ctrlUnitFault_u32:1U;            /* bit12:控制装置故障 */
        Uint32 pduFault_u32:1U;                 /* bit13:配电装置故障 */
        Uint32 rsvd_2_u32:1U;                   /* bit14:预留 */
        Uint32 posSensorFault_u32:1U;           /* bit15:位置信号器状态异常 */
        Uint32 rsvd_3_u32:5U;                   /* bit16-20:预留 */
        Uint32 brakePosFault_u32:1U;            /* bit21:刹车位置状态异常 */
        Uint32 rsvd_4_u32:10U;                  /* bit22-31:预留 */
    } bit;
}FaultInfo1_t;

/********************************************/
/* 故障信息Ⅱ结构体 (Label 254 / 故障信息Ⅱ) */
typedef union{
    Uint32 all;
    struct{
        Uint32 rsvd_1_u32:11U;                  /* bit0-10:预留 */
        Uint32 pressSensorFault_u32:1U;         /* bit11:温压传感器-压力故障 */
        Uint32 turbineSpeedEMFault_u32:1U;      /* bit12:涡轮转速传感器EM故障 */
        Uint32 turbineSpeedOPFault_u32:1U;      /* bit13:涡轮转速传感器OP故障 */
        Uint32 refuelSwitchFault_u32:1U;        /* bit14:加油开关故障 */
        Uint32 dumpSwitchFault_u32:1U;          /* bit15:放油开关故障 */
        Uint32 stepMotorCtrlFault_u32:1U;       /* bit16:步进电机控制器故障 */
        Uint32 driveCtrlFault_u32:1U;           /* bit17:电驱动控制器故障 */
        Uint32 rsvd_2_u32:14U;                  /* bit18-31:预留 */
    } bit;
}FaultInfo2_t;

/*****************************/
/* 当前时间结构体 */
typedef union{
    Uint32  all;
    struct{
    	Uint32 rsvd_1_u32:5U;
    	Uint32 gwHour_u32:4U;
    	Uint32 swHour_u32:2U;
    	Uint32 gwMin_u32:4U;
        Uint32 swMin_u32:4U;
        Uint32 rsvd_2_u32:13U;
    }bit;
}CurrTime_t;

/*****************************/
/* 寿命信息结构体 */
typedef union{
    Uint32  all;
    struct{
    	Uint32 workhourget_u32:1U;
    	Uint32 leftLife_u32:1U;
    	Uint32 sfcs_u32:1U;
    	Uint32 djcs_u32:1U;
    	Uint32 rsvd_1_u32:28U;
    }bit;
}LifeInfo_t;

/*************************************************************/
/* KZZZ429数据结构体      */
typedef struct _KZZZ429OrigData
{
	Orig429Data_t Orig_Rx_t[KZZZ_R_DATA_NUM];
}KZZZ429OrigData_t;

/*****************************/
/* KZZZ429接收解析结果结构体 */
typedef struct _KZZZ429InfoData
{
	Uint16 currTimeAsk_u16;                 /* 请求当前时间 */
	Uint16 MBITStateLast_u16;               /* 维护BIT执行上一拍反馈 */
	Uint16 MBITFB_u16;                      /* 维护BIT执行反馈 */
	KZZZMBITData1_t MBITFInfo_1_t;          /* 上传维护BIT结果 */
	SoftVData_t SoftV_t[KZZZ_SOFTV_NUM];    /* 软件版本信息组 */
	Uint16 Pre_FuelQtyRcv_FB_u16;           /* 预选油量接收反馈 */
	Uint16 flightHours_u16;                 /* 剩余飞行小时 */
	Uint16 oilReset_u16;                    /* 油量重置接收反馈 */
	float rgLength_f;                       /* 软管长度 */
	KZZZState_t jyzzState_t;                /* 加油装置状态 */
	ComponentState_t componentState_t;      /* 部件状态 */
	FaultInfo_t faultInfo_t;                /* 故障告警 */
    FaultInfo1_t faultInfo_1_t;            /* 故障信息Ⅰ */
    FaultInfo2_t faultInfo_2_t;            /* 故障信息Ⅱ */
	Uint16 turbineSpeed_u16;                /* 涡轮转速 */
	Uint16 fuelPressure_u16;                /* 加油压力 */
	Int16 fuelTemperature_i16;              /* 燃油温度 */
	Uint16 turbinePumpPressure_u16;         /* 涡轮泵出口压力 */
	Uint16 fuelFlow_u16;                    /* 加油流量 */
	Uint16 fuelLevel_u16;                   /* 已加油量 */
	Uint16 totalFuel_u16;                   /* 累计加油量 */
	RemainLife_t remainLife_t;              /* 剩余日历寿命 */
	CmdSignalFb_t cmdSignalFb_t;            /* 指令信号反馈 0255 */
	Int16 motorSpeed_i16;                   /* 电驱动电机转速 0256 r/min */
	Int16 motorTemp_i16;                    /* 电驱动控制器温度 0257 ℃ */
}KZZZ429InfoData_t;

/* KZZZ429健康统计 */
typedef struct _KZZZ429HealthData
{
    Uint32 rxLabelCnt_u32[KZZZ_R_DATA_NUM];
    Uint16 txLabel_u16[KZZZ_T_DATA_NUM];
    Uint32 txLabelCnt_u32[KZZZ_T_DATA_NUM];
    Uint32 rxTotalCnt_u32[COMM429_KZZZ_NUM];
    Uint32 rxUnknownLabelCnt_u32[COMM429_KZZZ_NUM];
    Uint32 rxTimeoutCnt_u32[COMM429_KZZZ_NUM];
    Uint32 txTotalCnt_u32;
}KZZZ429HealthData_t;

/* ***************************************************************** */
/**
 *  供外部调用函数接口
 */
/* ***************************************************************** */
extern void   Comm429KZZZInit(void);
extern void   Comm429KZZZDataProcess(void);
extern KZZZ429InfoData_t Comm429KzzzRxDataGet(Uint16 v_ID_u16);
extern KZZZ429OrigData_t Comm429KzzzRxOrigDataGet(Uint16 v_ID_u16);
extern A429Info_t Comm429KZZZRxStateGet(Uint16 v_ID_u16);
extern void Comm429KZZZSendDual(Uint16 v_label_u16, Uint32 v_data_u32);
extern void Comm429KZZZSendPreFuel(Uint16 v_kzzzID_u16, float v_data_f);
extern void Comm429KZZZSendFuelDensity(float v_data_f);
extern void Comm429KZZZSendCtrlCmd(Uint16 v_lowFuel_u16, Uint16 v_air_u16, Uint16 v_fuelReset_u16);
extern void Comm429KZZZCurrTimeTx(Uint16 v_kzzzID_u16, RIU429InfoData_t v_RIU429RxData_t);
extern void Comm429KZZZSendLifeInfo(Uint16 v_kzzzID_u16, Uint16 v_valid_u16);
extern void Comm429KZZZSendOilReset(Uint16 v_kzzzID_u16, Uint16 v_valid_u16);
extern Uint16 Comm429KZZZCcdlExtValidGet(Uint16 v_ccdlID_u16, Uint16 v_kzzzID_u16);
extern KZZZ429InfoData_t Comm429KZZZCcdlExtDataGet(Uint16 v_ccdlID_u16, Uint16 v_kzzzID_u16);

extern Uint32 Comm429KZZZTxLastWordGet(Uint16 v_ID_u16);
/* ***************************************************************** */
/* Comm429KZZZ.c 私有宏定义 */
/* ***************************************************************** */
#define COMM429_KZZZ_TIMEOUT_MS    (400UL) /* 需求接收周期约200ms，按两个接收周期判定KZZZ链路中断。 */
#define KZZZ_PRE_FUEL_MAX_KG       (80000.0F)
#define KZZZ_FUEL_DENSITY_MAX      (1023.0F)

#endif /* COMM429KZZZ_H */

/* ========================================================================== */
/* 文件结束 */
/* ========================================================================== */
