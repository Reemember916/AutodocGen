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
 * 文件名称:    Comm429RIU.h
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
#ifndef COMM429RIU_H

#define COMM429RIU_H

#include "CommDRI_429.h"

/******************************************************************/
/* 发送报文标号（控制器 -> RIU），均为八进制 */
#define RIU_LABEL_T_BUS_HEART              (0200U) /* 总线心跳字 */
#define RIU_LABEL_T_PUBIT_ALARM_1          (0201U) /* 上电BIT告警 */
#define RIU_LABEL_T_MBIT_EXEC_FB           (0202U) /* 维护BIT执行反馈 */
#define RIU_LABEL_T_UPLOAD_MBIT_RESULT     (0203U) /* 上传维护BIT结果 */
#define RIU_LABEL_T_CTRL_CMD_1         (0220U) /* 控制指令1 */
#define RIU_LABEL_T_CTRL_CMD_2         (0221U) /* 控制指令2 */
#define RIU_LABEL_T_CTRL_CMD_3         (0222U) /* 控制指令3 */
#define RIU_LABEL_T_STATUS_INFO        (0230U) /* 状态信息 */
#define RIU_LABEL_T_FAULT_INFO_1       (0231U) /* 故障信息1 */
#define RIU_LABEL_T_FAULT_INFO_2       (0232U) /* 故障信息2 */
#define RIU_LABEL_T_WARN_INFO          (0233U) /* 告警信息  */
#define RIU_LABEL_T_TIP_INFO           (0234U) /* 提示信息  */
#define RIU_LABEL_T_CTRL_SWV_CH1       (0240U) /* 通道I控制软件版本信息 */
#define RIU_LABEL_T_CTRL_SWV_CH2       (0241U) /* 通道II控制软件版本信息 */
#define RIU_LABEL_T_LOGIC_SWV_CH1      (0242U) /* 通道I逻辑处理软件版本信息 */
#define RIU_LABEL_T_LOGIC_SWV_CH2      (0243U) /* 通道II逻辑处理软件版本信息 */
#define RIU_LABEL_T_LP_SOFTV_CTRL      (0244U) /* 左吊舱控制装置软件版本信息 */
#define RIU_LABEL_T_LP_SOFTV_MOTOR_CTRL (0245U) /* 左吊舱电驱动控制器软件版本信息 */
#define RIU_LABEL_T_LP_SOFTV_SIGNAL_BOX (0246U) /* 左吊舱油量测量信号盒软件版本信息 */
#define RIU_LABEL_T_LP_SOFTV_BRAKE_CTRL (0247U) /* 左吊舱电液刹车驱动控制器软件版本信息 */
#define RIU_LABEL_T_LP_SOFTV_BIT_APP   (0250U) /* 左吊舱自检测装置应用软件版本信息 */
#define RIU_LABEL_T_LP_SOFTV_CTRL_LOGIC (0251U) /* 左吊舱控制装置逻辑软件版本信息 */
#define RIU_LABEL_T_LP_SOFTV_MOTOR_LOGIC (0252U) /* 左吊舱电驱动控制器逻辑软件版本信息 */
#define RIU_LABEL_T_LP_SOFTV_CTRL_UPGRADE_APP (0253U) /* 左吊舱控制装置在线升级应用软件版本信息 */
#define RIU_LABEL_T_LP_PRE_FUEL_RCV_FB (0254U) /* 左吊舱预选油量接收反馈 */
#define RIU_LABEL_T_LP_REMAIN_FLIGHT_HOUR (0255U) /* 左吊舱剩余飞行小时 */
#define RIU_LABEL_T_LP_REMAIN_CALENDAR_LIFE (0256U) /* 左吊舱剩余日历寿命 */
#define RIU_LABEL_T_LP_OIL_RESET_RCV_FB (0257U) /* 左吊舱油量重置接收反馈 */
#define RIU_LABEL_T_LP_TURBINE_SPEED   (0260U) /* 左吊舱涡轮转速 */
#define RIU_LABEL_T_LP_FUEL_PRESS      (0261U) /* 左吊舱加油压力 */
#define RIU_LABEL_T_LP_PUMP_PRESS      (0262U) /* 左吊舱涡轮泵出口压力 */
#define RIU_LABEL_T_LP_FUEL_FLOW       (0263U) /* 左吊舱加油流量 */
#define RIU_LABEL_T_LP_FUEL_LEVEL      (0264U) /* 左吊舱已加油量 */
#define RIU_LABEL_T_LP_TOTAL_FUEL      (0265U) /* 左吊舱累计加油量 */
#define RIU_LABEL_T_LP_FUEL_TEMP       (0266U) /* 左吊舱燃油温度 */
#define RIU_LABEL_T_LP_RG_LEN          (0267U) /* 左吊舱软管长度 */
#define RIU_LABEL_T_LP_JYZZ_STATE      (0270U) /* 左吊舱加油设备状态 */
#define RIU_LABEL_T_LP_COMPONENT_STATE (0271U) /* 左吊舱部件状态 */
#define RIU_LABEL_T_LP_FAULT_WARN      (0272U) /* 左吊舱故障告警 */
#define RIU_LABEL_T_LP_FAULT_INFO_1    (0273U) /* 左吊舱故障告警I */
#define RIU_LABEL_T_LP_FAULT_INFO_2    (0274U) /* 左吊舱故障告警II */
#define RIU_LABEL_T_LP_CMD_FB          (0275U) /* 左吊舱指令信号反馈 */
#define RIU_LABEL_T_LP_MOTOR_SPEED     (0276U) /* 左吊舱电驱动电机转速 */
#define RIU_LABEL_T_LP_CTRL_TEMP       (0277U) /* 左吊舱电驱动控制器温度 */
#define RIU_LABEL_T_RP_SOFTV_CTRL      (0344U) /* 右吊舱控制装置软件版本信息 */
#define RIU_LABEL_T_RP_SOFTV_MOTOR_CTRL (0345U) /* 右吊舱电驱动控制器软件版本信息 */
#define RIU_LABEL_T_RP_SOFTV_SIGNAL_BOX (0346U) /* 右吊舱油量测量信号盒软件版本信息 */
#define RIU_LABEL_T_RP_SOFTV_BRAKE_CTRL (0347U) /* 右吊舱电液刹车驱动控制器软件版本信息 */
#define RIU_LABEL_T_RP_SOFTV_BIT_APP   (0350U) /* 右吊舱自检测装置应用软件版本信息 */
#define RIU_LABEL_T_RP_SOFTV_CTRL_LOGIC (0351U) /* 右吊舱控制装置逻辑软件版本信息 */
#define RIU_LABEL_T_RP_SOFTV_MOTOR_LOGIC (0352U) /* 右吊舱电驱动控制器逻辑软件版本信息 */
#define RIU_LABEL_T_RP_SOFTV_CTRL_UPGRADE_APP (0353U) /* 右吊舱控制装置在线升级应用软件版本信息 */
#define RIU_LABEL_T_RP_PRE_FUEL_RCV_FB (0354U) /* 右吊舱预选油量接收反馈 */
#define RIU_LABEL_T_RP_REMAIN_FLIGHT_HOUR (0355U) /* 右吊舱剩余飞行小时 */
#define RIU_LABEL_T_RP_REMAIN_CALENDAR_LIFE (0356U) /* 右吊舱剩余日历寿命 */
#define RIU_LABEL_T_RP_OIL_RESET_RCV_FB (0357U) /* 右吊舱油量重置接收反馈 */
#define RIU_LABEL_T_RP_TURBINE_SPEED   (0360U) /* 右吊舱涡轮转速 */
#define RIU_LABEL_T_RP_FUEL_PRESS      (0361U) /* 右吊舱加油压力 */
#define RIU_LABEL_T_RP_PUMP_PRESS      (0362U) /* 右吊舱涡轮泵出口压力 */
#define RIU_LABEL_T_RP_FUEL_FLOW       (0363U) /* 右吊舱加油流量 */
#define RIU_LABEL_T_RP_FUEL_LEVEL      (0364U) /* 右吊舱已加油量 */
#define RIU_LABEL_T_RP_TOTAL_FUEL      (0365U) /* 右吊舱累计加油量 */
#define RIU_LABEL_T_RP_FUEL_TEMP       (0366U) /* 右吊舱燃油温度 */
#define RIU_LABEL_T_RP_RG_LEN          (0367U) /* 右吊舱软管长度 */
#define RIU_LABEL_T_RP_JYZZ_STATE      (0370U) /* 右吊舱加油设备状态 */
#define RIU_LABEL_T_RP_COMPONENT_STATE (0371U) /* 右吊舱部件状态 */
#define RIU_LABEL_T_RP_FAULT_WARN      (0372U) /* 右吊舱故障告警 */
#define RIU_LABEL_T_RP_FAULT_INFO_1    (0373U) /* 右吊舱故障告警I */
#define RIU_LABEL_T_RP_FAULT_INFO_2    (0374U) /* 右吊舱故障告警II */
#define RIU_LABEL_T_RP_CMD_FB          (0375U) /* 右吊舱指令信号反馈 */
#define RIU_LABEL_T_RP_MOTOR_SPEED     (0376U) /* 右吊舱电驱动电机转速 */
#define RIU_LABEL_T_RP_CTRL_TEMP       (0377U) /* 右吊舱电驱动控制器温度 */

#define RIU_POD_PERIODIC_FIELD_NUM     (16U) /* 吊舱周期发送字段数量 */
#define RIU_POD_EVENT_SOFTV_FIELD_NUM  (8U)  /* 吊舱软件版本事件字段数量 */
#define RIU_EVENT_REQ_NUM              (6U)  /* RIU事件请求计数数量 */

typedef struct _RIUEventReqTrack
{
    Uint16 currCnt_u16;     /* 当前计数 */
    Uint16 lastCnt_u16;     /* 上次计数 */
    Uint16 changed_u16;     /* 是否变化 */
    Uint16 inited_u16;      /* 是否已初始化 */
}RIUEventReqTrack_t;


/*************************************/  /* RIU接收索引（按20260127 docx） */

#define RIU_R_DATA_INDEX_DATE_YMD        (0U)  /* 年、月、日 */
#define RIU_R_DATA_INDEX_TIME_HMS        (1U)  /* 时、分、秒 */
#define RIU_R_DATA_INDEX_MAINT_CMD       (2U)  /* 维护指令 */
#define RIU_R_DATA_INDEX_WHEEL_LOAD      (3U)  /* 轮载状态 */
#define RIU_R_DATA_INDEX_HEART           (4U)  /* 总线心跳字 */
#define RIU_R_DATA_INDEX_MBIT_EXEC       (5U)  /* 执行维护BIT */
#define RIU_R_DATA_INDEX_SOFTV_REQ       (6U)  /* 软件版本请求信息 */
#define RIU_R_DATA_INDEX_OIL_RESET       (7U)  /* 油量重置 */
#define RIU_R_DATA_INDEX_LIFE_INFO       (8U)  /* 发送寿命信息 */
#define RIU_R_DATA_INDEX_CTRL_CMD        (9U)  /* 控制指令 */
#define RIU_R_DATA_INDEX_RCV             (10U) /* 压力加油控制活门状态 */
#define RIU_R_DATA_INDEX_VALVE1          (11U) /* 通气阀位置信息 */
#define RIU_R_DATA_INDEX_HL_SENSOR       (12U) /* 高油面及超压信号 */
#define RIU_R_DATA_INDEX_VALVE2          (13U) /* 切断阀位置信息 */
#define RIU_R_DATA_INDEX_FUELPUMP        (14U) /* 加油泵状态信号 */
#define RIU_R_DATA_INDEX_FAULTINFO       (15U) /* 信号转换盒和油量传感器故障信息 */
#define RIU_R_DATA_INDEX_FQ_TANK0        (16U) /* 0号油箱油量值 */
#define RIU_R_DATA_INDEX_FQ_TANK1        (17U) /* 1号油箱油量值 */
#define RIU_R_DATA_INDEX_FQ_TANK2        (18U) /* 2号油箱油量值 */
#define RIU_R_DATA_INDEX_FQ_TANK3        (19U) /* 3号油箱油量值 */
#define RIU_R_DATA_INDEX_FQ_TANK4        (20U) /* 4号油箱油量值 */
#define RIU_R_DATA_INDEX_TOTAL_FUEL      (21U) /* 全机总油量 */
#define RIU_R_DATA_INDEX_PRV             (22U) /* 预设受油量值 */
#define RIU_R_DATA_INDEX_LP_PFV          (23U) /* 左吊舱预选油量 */
#define RIU_R_DATA_INDEX_RP_PFV          (24U) /* 右吊舱预选油量 */
#define RIU_R_DATA_INDEX_IAS             (25U) /* 指示空速 */
#define RIU_R_DATA_INDEX_FUEL_DENSITY    (26U) /* 燃油密度 */
#define RIU_R_DATA_INDEX_LP_BRIGHTNESS   (27U) /* 左吊舱通道灯亮度调节 */
#define RIU_R_DATA_INDEX_RP_BRIGHTNESS   (28U) /* 右吊舱通道灯亮度调节 */

#define RIU_R_DATA_NUM                   (29U) /* RIU接收标签个数 */

#define RIU_T_DATA_NUM                   (72U) /* RIU发送标签个数 */

/* 接收报文标号（RIU -> 控制器），均为八进制 */
#define RIU_LABEL_R_DATE_YMD             (0201U) /* 年、月、日 */
#define RIU_LABEL_R_TIME_HMS             (0202U) /* 时、分、秒 */
#define RIU_LABEL_R_MAINT_CMD            (0203U) /* 维护指令 */
#define RIU_LABEL_R_WHEEL_LOAD           (0204U) /* 轮载状态 */
#define RIU_LABEL_R_HEART                (0200U) /* 总线心跳字 */
#define RIU_LABEL_R_MBIT_EXEC            (0205U) /* 执行维护BIT */
#define RIU_LABEL_R_SOFTV_REQ_INFO       (0206U) /* 软件版本请求信息 */
#define RIU_LABEL_R_OIL_RESET            (0207U) /* 油量重置 */
#define RIU_LABEL_R_LIFE_INFO            (0210U) /* 发送寿命信息 */
#define RIU_LABEL_R_CTRL_CMD             (0211U) /* 控制指令 */
#define RIU_LABEL_R_FQ_TANK0             (0251U) /* 0号油箱油量值 */
#define RIU_LABEL_R_FQ_TANK1             (0252U) /* 1号油箱油量值 */
#define RIU_LABEL_R_FQ_TANK2             (0253U) /* 2号油箱油量值 */
#define RIU_LABEL_R_FQ_TANK3             (0254U) /* 3号油箱油量值 */
#define RIU_LABEL_R_FQ_TANK4             (0255U) /* 4号油箱油量值 */
#define RIU_LABEL_R_TOTAL_FUEL           (0256U) /* 全机总油量 */
#define RIU_LABEL_R_RCV                  (0257U) /* 压力加油控制活门状态 */
#define RIU_LABEL_R_VALVE1               (0260U) /* 通气阀位置信息 */
#define RIU_LABEL_R_HL_SENSOR            (0261U) /* 高油面及超压信号 */
#define RIU_LABEL_R_VALVE2               (0262U) /* 切断阀位置信息 */
#define RIU_LABEL_R_FUELPUMP             (0263U) /* 加油泵状态信号 */
#define RIU_LABEL_R_FAULTINFO            (0264U) /* 信号转换盒和油量传感器故障信息 */
#define RIU_LABEL_R_PRV                  (0265U) /* 预设受油量值 */
#define RIU_LABEL_R_LP_PFV               (0266U) /* 左吊舱预选油量 */
#define RIU_LABEL_R_RP_PFV               (0267U) /* 右吊舱预选油量 */
#define RIU_LABEL_R_IAS                  (0270U) /* 指示空速 */
#define RIU_LABEL_R_FUEL_DENSITY         (0271U) /* 燃油密度 */
#define RIU_LABEL_R_LP_BRIGHTNESS        (0272U) /* 左吊舱通道灯亮度调节 */
#define RIU_LABEL_R_RP_BRIGHTNESS        (0273U) /* 右吊舱通道灯亮度调节 */

/*********************************/
/* 空速宏定义     */
#define AIR_SPEED_MIN     (0.0F) /* 空速最小值，单位km/h */
#define AIR_SPEED_MAX     (832.0F) /* 空速最大值，单位km/h */
#define AIR_SPEED_RATIO   (0.1F)     /* 指示空速分辨率，单位km/h */
#define OIL_MD_RATIO      (1.0F)     /* 燃油密度分辨率，单位kg/m3 */
#define OIL_TANK_RATIO    (10.0F)    /* 油箱/总油量分辨率，单位kg */
#define OIL_RATIO         (100.0F)   /* 预设/预选油量分辨率，单位kg */


/* ***************************************************************** */
/* RIU通信解析数据内部宏定义 (Comm429RIU.c 内部引用) */
#define RIU429_IDATA_NUM               (1U)     /* 数据数组中的个数   */
#define RIU429_INFODATA_UPDATE_ERR    (0x01U << 0U)     /* 信息数据更新异常 */

#define TMIE_WORK_SUM_MAX        (60000U)   /* 系统累计工作时间，单位min */


#define RIU429_IDATA_MAX_COUNT    (5U)             /* 数据状态检测过滤数 */

/************GMP2液压油量低****************/
#define RIU429_OIL_LOW_NO      (0x0U)    /* 非低  */
#define RIU429_OIL_LOW_INVALID (0x1U)    /* 无效  */
#define RIU429_OIL_LOW_YES     (0x3U)    /* 低  */

/*************燃油系统指令1******************/
#define RIU429_OBJECT_HELICOPTER    (0x0U)    /* 直升机        */
#define RIU429_OBJECT_FIXEDWING       (0x1U)    /* 固定翼     */

#define RIU429_MODE_OFF       (0x0U)    /* 关断模式 */
#define RIU429_MODE_LP       (0x1U)    /* 左吊舱加油模式 */
#define RIU429_MODE_RP       (0x2U)    /* 右吊舱加油模式 */
#define RIU429_MODE_LRP       (0x3U)    /* 左右吊舱加油模式      */
#define RIU429_MODE_RECEIVE       (0x4U)    /* 受油模式     */
#define RIU429_MODE_MANUAL       (0x7U)    /* 手动模式     */

/************单电源****************/

#define RIU_DK_AIR              (0U) /* 兼容聚合空地量：空中 */
#define RIU_DK_GROUND           (1U) /* 兼容聚合空地量：地面 */

#define RIU_WHEEL_LOAD_UNKNOWN  (0U) /* 轮载表决值：未知 */
#define RIU_WHEEL_LOAD_GROUND   (1U) /* 轮载表决值：地面 */
#define RIU_WHEEL_LOAD_AIR      (2U) /* 轮载表决值：空中 */
#define RIU_WHEEL_LOAD_RSVD     (3U) /* 轮载表决值：预留 */

#define RIU_DK_FLAG_INVALID    (0x00U) /* 地空状态有效标志无效 */
#define RIU_DK_FLAG_VALID      (0x01U) /* 地空状态有效标志有效 */

/*******************************/
#define RIU_AIR_SPEED_INVALID  (0x00U) /* 指示空速表决值有效标志无效 */
#define RIU_AIR_SPEED_VALID    (0x01U) /* 指示空速表决值有效标志有效 */

/*******************************/
#define RIU_FLIGHT_HEIGHT_INVALID  (0x00U) /* 飞行高度表决值有效标志无效  */
#define RIU_FLIGHT_HEIGHT_VALID    (0x01U) /* 飞行高度表决值有效标志有效  */

/* ***************************************************************** */
typedef struct _RIU429Data       /* RIU429信息数据结构体 */
{
    Uint16 currData_u16;                   /* 最近一次有效的数据 */
    Uint16 checkState_u16;                 /* 数据检查状态       */
    Uint16 currState_u16;                  /* 数据当前检查状态       */
    Uint32 checkTime_u32;                  /* 最近一次数据状态检查时间 */
    Uint16 dataCount_u16;                  /* 有效数据计数 */
    Uint32 rxTime_u32;                     /* 最近一次接收到有效数据时间 */
    Uint16 StateChangeCount_u16;           /* 状态计数 */

}RIU429Data_Type;

/*****************************/
/* 燃油系统指令1联合体 */
struct ryxtCMD_1_DataBit
{
	Uint32 rsvd_1_u16:6U;       /* bit0-5:预留1  */
	Uint32 GMP_2_oillow_u16:2U; /* bit6-7:GMP2号液压油量低  */
	Uint32 modeCMD_u16:4U;      /* bit8-11:工作模式指令           */
	Uint32 rsvd_2_u16:4U;       /* bit12-15:预留2 */
	Uint32 singlePower_u16:2U;  /* bit16-17:单电源  */
	Uint32 rsvd_3_u16:14U;      /* bit18-31:预留         */
};

union ryxtCMD_1_Data
{
    Uint32  all;        /* 燃油系统指令1数据 */
    struct ryxtCMD_1_DataBit bit; /* 燃油系统指令1数据位域  */
};
/*****************************/
/* 加油指令联合体 */
struct fuelCmd_DataBit
{
	Uint8 fuelObject_u8:1U;       /* bit0:加油对象	0：直升机；1：固定翼 */
	Uint8 rsvd_1_u8:2U;
	Uint8 fuelMode_u8:3U; /* bit3-5: 加受油模式 	000：关断；001：左吊舱加油模式；010：右吊舱加油模式；011：左右吊舱加油模式；100：受油模式；111：手动模式 */
	Uint8 rsvd_2_u8:2U;
};

union fuelCmd_Data
{
    Uint8  all;        /* 加油指令数据 */
    struct fuelCmd_DataBit bit; /*加油指令数据位域  */
};

/*****************************/
/* 压力加油控制活门状态联合体 */  		// 1：已上电/已到位；0：未上电/未到位
struct RCV_DataBit
{
	Uint16 RCV0_state_u16:1U;       /* 0号压力加油控制活门状态 */
	Uint16 RCV1_state_u16:1U;       /* 1号压力加油控制活门状态 */
	Uint16 RCV2_state_u16:1U;       /* 2号压力加油控制活门状态 */
	Uint16 RCV3_state_u16:1U;       /* 3号压力加油控制活门状态 */
	Uint16 RCV4_state_u16:1U;       /* 4号压力加油控制活门状态 */
	Uint16 rsvd_1_u16:2U;
	Uint16 RCV0_Close_u16:1U;       /* 0号压力加油控制活门关闭到位状态 */
	Uint16 RCV1_Close_u16:1U;       /* 1号压力加油控制活门关闭到位状态 */
	Uint16 RCV2_Close_u16:1U;       /* 2号压力加油控制活门关闭到位状态 */
	Uint16 RCV3_Close_u16:1U;       /* 3号压力加油控制活门关闭到位状态 */
	Uint16 RCV4_Close_u16:1U;       /* 4号压力加油控制活门关闭到位状态 */
	Uint16 rsvd_2_u16:4;
};

union RCV_Data
{
    Uint16  all;
    struct RCV_DataBit bit;
};
/*****************************/
/* 阀状态信号1（0260） */  		// Bit9-Bit16：00无效；01打开；10关闭；11故障；
struct valve1_DataBit
{
	Uint16 LDDTQ_state_u16:2U;       /* 左电动通气阀门位置 */
	Uint16 RDDTQ_state_u16:2U;       /* 右电动通气阀门位置 */
	Uint16 ST_state_u16:2U;          /* 三通阀位置，协议01=受油位，10=关闭位 */
	Uint16 LT_state_u16:2U;          /* 连通阀位置 */
	Uint16 rsvd:8U;
};

union valve1_Data
{
    Uint16  all;
    struct valve1_DataBit bit;
};
/*****************************/
/* 阀状态信号2（0262） */  		// Bit9-Bit26：00无效；01打开；10关闭；11故障；
struct valve2_DataBit
{
	Uint32 Pump2_cutoff_state_u32:2U;      /* 2号加油泵切断阀状态 */
	Uint32 Pump0_Lcutoff_state_u32:2U;     /* 0左加油泵切断阀状态 */
	Uint32 Pump0_Rcutoff_state_u32:2U;     /* 0右加油泵切断阀状态 */
	Uint32 Pump3_cutoff_state_u32:2U;      /* 3号加油泵切断阀状态 */
	Uint32 LPQD_state_u32:2U;              /* 左吊舱切断阀状态 */
	Uint32 RPQD_state_u32:2U;              /* 右吊舱切断阀状态 */
	Uint32 LYJFY_state_u32:2U;             /* 左应急放油切断阀状态 */
	Uint32 RYJFY_state_u32:2U;             /* 右应急放油切断阀状态 */
	Uint32 rsvd:2U;
};

union valve2_Data
{
    Uint32  all;
    struct valve2_DataBit bit;
};
/*****************************/
/* 高油面信号器信号 */  		// 		 00：未到位；01：关到位；10：开到位；
struct HLSensor_DataBit
{
	Uint16 tank0_HL_sensor_u16:1U;       /* 0号油箱高油面信号器信号 */
	Uint16 tank1_HL_sensor_u16:1U;       /* 1号油箱高油面信号器信号 */
	Uint16 tank2_HL_sensor_u16:1U;       /* 2号油箱高油面信号器信号 */
	Uint16 tank3_HL_sensor_u16:1U;       /* 3号油箱高油面信号器信号 */
	Uint16 tank4_HL_sensor_u16:1U;       /* 4号油箱高油面信号器信号 */
	Uint16 rsvd:11U;
};

union HLSensor_Data
{
    Uint16  all;
    struct HLSensor_DataBit bit;
};
/*****************************/
/* 故障信息 */  		// 		 1：有效；0：无效；
struct faultInfo_DataBit
{
	Uint16 STB1_fault_u16:1U;       /* 1号信号转换盒故障 */
	Uint16 STB2_fault_u16:1U;       /* 2号信号转换盒故障 */
	Uint16 STB3_fault_u16:1U;       /* 3号信号转换盒故障 */
	Uint16 STB4_fault_u16:1U;       /* 4号信号转换盒故障 */
	Uint16 rsvd1:2U;
	Uint16 tank1_sensor_fault_u16:1U;	/*1号油箱油量传感器故障*/
	Uint16 tank2_sensor_fault_u16:1U;	/*2号油箱油量传感器故障*/
	Uint16 tank3_sensor_fault_u16:1U;	/*3号油箱油量传感器故障*/
	Uint16 tank4_sensor_fault_u16:1U;	/*4号油箱油量传感器故障*/
	Uint16 rsvd2:2U;
	Uint16 oilMS_falut_u16:1U;		/*燃油测量系统故障*/
	Uint16 oilMS_downGrade_u16:1U;		/*燃油测量系统降级*/
	Uint16 rsvd3:2U;
};

union faultInfo_Data
{
    Uint16  all;
    struct faultInfo_DataBit bit;
};
/*****************************/
/* 加油泵状态信号 */  		// 		 1：有效；0：无效；
struct fuelPump_DataBit
{
	Uint16 FP0_left_state_u16:1U;       /* 1号信号转换盒故障 */
	Uint16 FP0_right_state_u16:1U;       /* 2号信号转换盒故障 */
	Uint16 FP2_state_u16:1U;       /* 3号信号转换盒故障 */
	Uint16 FP3_state_u16:1U;       /* 4号信号转换盒故障 */
	Uint16 rsvd:12U;

};

union fuelPump_Data
{
    Uint16  all;
    struct fuelPump_DataBit bit;
};
/*****************************/
typedef struct _RIU429OrigData        /* RIU429数据结构体 */
{
	Orig429Data_t Orig_Rx_t[RIU_R_DATA_NUM];   /* 接收原始数据    */

}RIU429OrigData_t;

/*****************************/
typedef struct _RIU429InfoData        /* RIU429数据结构体 */
{
	Uint16 heartB_u16;              /* 设备心跳     */
	DateTime_t DTData_t;            /* 日期时间数据 */
	float airSpeed_f;               /* 空速，单位km/h */
	union ryxtCMD_1_Data ryxtCMD_1_un32; /* 燃油系统指令1 */
	float  oilMD_f;                 /* 燃油密度 ,单位kg/m3  */
	union fuelCmd_Data fuelCmd_t;   /*加油指令*/
	union RCV_Data RCV_t;		/*压力加油控制活门状态*/
	union valve1_Data valve1_t;	/*阀状态信号1*/
	union valve2_Data valve2_t;	/*阀状态信号2*/
	union fuelPump_Data fuelPump_t;
	union HLSensor_Data HLSensor_t;
	union faultInfo_Data faultInfo_t;
	float PRV_f;		/*预设受油量值*/
	float lpPFV_f;		/*左吊舱预选油量值*/
	float rpPFV_f;		/*右吊舱预选油量值*/
	float PFV_f;		/*兼容字段：默认复用左吊舱预选油量值*/
	float tank0_vol_f; /*0号油箱油量值*/
	float tank1_vol_f; /*1号油箱油量值*/
	float tank2_vol_f; /*2号油箱油量值*/
	float tank3_vol_f; /*3号油箱油量值*/
	float tank4_vol_f; /*4号油箱油量值*/
	float totalFuel_f; /*全机总油量*/
	Uint16 maintCmd_u16;           /* 维护指令 */
	Uint16 wheelLoad_u16;          /* 兼容聚合空地量 */
	Uint16 wheelLoadNose_u16;      /* 前起轮载表决值 */
	Uint16 wheelLoadLeftMain_u16;  /* 左主起轮载表决值 */
	Uint16 wheelLoadRightMain_u16; /* 右主起轮载表决值 */
	Uint16 mbitExec_u16;           /* 执行维护BIT */
	Uint16 softVersionReq_u16;     /* 软件版本请求信息 */
	Uint16 oilResetCmd_u16;        /* 油量重置 */
	Uint32 lifeInfo_u32;           /* 发送寿命信息原始值 */
	Uint16 ctrlCmd_u16;            /* 控制指令原始值 */
	Uint16 lpBrightness_u16;       /* 左吊舱通道灯亮度调节 */
	Uint16 rpBrightness_u16;       /* 右吊舱通道灯亮度调节 */
	Uint32 softVersion_deploy;     /* 兼容字段：软件版本请求有效位 */

}RIU429InfoData_t;

/* ***************************************************************** */

/* 压力加油控制活门关闭控制指令 */  		// 		 1：有效；0：无效；
struct RCV_CmdBit
{
	Uint16 RCV0_CloseCmd_u16:1U;       /* 0号压力加油控制活门关闭控制指令 */
	Uint16 RCV1_CloseCmd_u16:1U;       /* 1号压力加油控制活门关闭控制指令 */
	Uint16 RCV2_CloseCmd_u16:1U;       /* 2号压力加油控制活门关闭控制指令 */
	Uint16 RCV3_CloseCmd_u16:1U;       /* 3号压力加油控制活门关闭控制指令 */
	Uint16 RCV4_CloseCmd_u16:1U;       /* 4号压力加油控制活门关闭控制指令 */
	Uint16 RCV0_OffCloseCmd_u16:1U;       /* 0号压力加油控制活门断电关闭控制指令 */
	Uint16 RCV1_OffCloseCmd_u16:1U;       /* 1号压力加油控制活门断电关闭控制指令 */
	Uint16 RCV2_OffCloseCmd_u16:1U;       /* 2号压力加油控制活门断电关闭控制指令 */
	Uint16 RCV3_OffCloseCmd_u16:1U;       /* 3号压力加油控制活门断电关闭控制指令 */
	Uint16 RCV4_OffCloseCmd_u16:1U;       /* 4号压力加油控制活门断电关闭控制指令 */
	Uint16 rsvd1:6U;

};

union RCV_Cmd
{
    Uint16  all;
    struct RCV_CmdBit bit;
};

/* 阀控制 */  		// 		 0：打开；1：关闭；
struct ValveCTRLBit
{
	Uint16 Pump2_cutoff_ctrl_u16:1U;       /* 2号加油泵切断阀控制指令，0：打开；1：关闭 */
	Uint16 Pump0_Lcutoff_ctrl_u16:1U;       /* 0左加油泵切断阀控制指令，0：打开；1：关闭 */
	Uint16 Pump0_Rcutoff_ctrl_u16:1U;       /* 0右加油泵切断阀控制指令，0：打开；1：关闭 */
	Uint16 Pump3_cutoff_ctrl_u16:1U;       /* 3号加油泵切断阀控制指令，0：打开；1：关闭 */
	Uint16 LPQD_ctrl_u16:1U;       /* 左吊舱切断阀控制指令，0：打开；1：关闭 */
	Uint16 RPQD_ctrl_u16:1U;       /* 右吊舱切断阀控制指令，0：打开；1：关闭 */
	Uint16 LYJFY_ctrl_u16:1U;       /* 左应急放油切断阀控制指令，0：打开；1：关闭 */
	Uint16 RYJFY_ctrl_u16:1U;       /* 右应急放油切断阀控制指令，0：打开；1：关闭 */
	Uint16 LT_ctrl_u16:1U;       /* 连通阀控制指令，0：打开；1：关闭 */
	Uint16 ST_ctrl_u16:1U;       /* 三通阀控制指令，0：关闭位；1：受油位 */
	Uint16 rsvd1:6U;

};

union ValveCTRL
{
    Uint16  all;
    struct ValveCTRLBit bit;
};

/* 故障信息1 */  		// 		 1：故障；0：正常；
struct RIUfltInfo1Bit
{
	Uint16 Pump2_cutoff_fault_u16:1U;       /* 2号加油泵切断阀故障 */
	Uint16 Pump0_Lcutoff_fault_u16:1U;       /* 0左加油泵切断阀故障 */
	Uint16 Pump0_Rcutoff_fault_u16:1U;       /* 0右加油泵切断阀故障 */
	Uint16 Pump3_cutoff_fault_u16:1U;       /* 3号加油泵切断阀故障 */
	Uint16 LPQD_fault_u16:1U;       /* 左吊舱切断阀到位状态 */
	Uint16 RPQD_fault_u16:1U;       /* 右吊舱切断阀到位状态 */
	Uint16 ST_fault_u16:1U;       /* 三通阀空中受油位/关闭位到位状态 */
	Uint16 LT_fault_u16:1U;       /* 连通阀打开位到位状态 */
	Uint16 LYJFY_fault_u16:1U;       /* 左应急放油切断阀关闭位到位状态 */
	Uint16 RYJFY_fault_u16:1U;       /* 右应急放油切断阀关闭位到位状态 */
	Uint16 LDDTQ_fault_u16:1U;       /* 左电动通气阀打开位到位状态 */
	Uint16 RDDTQ_fault_u16:1U;       /* 右电动通气阀打开位到位状态 */
	Uint16 rsvd1:4U;

};

union RIUfltInfo1
{
    Uint16  all;
    struct RIUfltInfo1Bit bit;
};

/* 故障信息2 */  		// 		 1：故障；0：正常；
struct RIUfltInfo2Bit
{
	Uint16 RCV0_fault_u16:1U;       /* 0号油箱压力加油控制活门关闭故障 */
	Uint16 RCV1_fault_u16:1U;       /* 1号油箱压力加油控制活门关闭故障 */
	Uint16 RCV2_fault_u16:1U;       /* 2号油箱压力加油控制活门关闭故障 */
	Uint16 RCV3_fault_u16:1U;       /* 3号油箱压力加油控制活门关闭故障 */
	Uint16 RCV4_fault_u16:1U;       /* 4号油箱压力加油控制活门关闭故障 */
	Uint16 oilMS_falut_u16:1U;       /* 燃油测量系统故障 */
	Uint16 EMS_fault_u16:1U;       /* 与机电系统通讯故障 */
	Uint16 rsvd1:9U;

};

union RIUfltInfo2
{
    Uint16  all;
    struct RIUfltInfo2Bit bit;
};
typedef struct _RIU429SendData       /* RIU429信息发送数据结构体 */
{
    union RCV_Cmd RCVcmd_t;                   /* 压力加油控制活门关闭控制指令 */
    union RIUfltInfo1 RIUfltInfo1_t;
    union RIUfltInfo2 RIUfltInfo2_t;
    union ValveCTRL ValveCtrl_t;
    Uint16 checkState_u16;                 /* 数据检查状态       */
    Uint16 currState_u16;                  /* 数据当前状态       */
    Uint32 checkTime_u32;                  /* 最后一次更新状态检查时间 */
    Uint16 dataCount_u16;                  /* 有效数据计数 */
    Uint32 rxTime_u32;                     /* 最后一次接收到有效数据时间 */
    Uint16 StateChangeCount_u16;           /* 状态变化计数 */
    Uint16 press34PlaceholderActive_u16;   /* 压力3/4占位发送标识 */

}RIU429SendData_t;

/* RIU429健康统计 */
typedef struct _RIU429HealthData
{
    Uint32 rxLabelCnt_u32[RIU_R_DATA_NUM];
    Uint16 txLabel_u16[RIU_T_DATA_NUM];
    Uint32 txLabelCnt_u32[RIU_T_DATA_NUM];
    Uint32 rxTotalCnt_u32[COMM429_RIU_NUM];
    Uint32 rxUnknownLabelCnt_u32[COMM429_RIU_NUM];
    Uint32 rxTimeoutCnt_u32[COMM429_RIU_NUM];
    Uint32 txTotalCnt_u32;
    Uint32 press34PlaceholderCnt_u32;
    Uint16 press34PlaceholderActive_u16;
}RIU429HealthData_t;

/* ***************************************************************** */
/**
 *  对外部调用函数接口
 */
/* ***************************************************************** */

extern void   Comm429RIUInit(void);
extern void   Comm429RIUDataProcess(void);
extern void Comm429RIUPeriodInfoTx(void);
/* ***************************************************************** */
extern RIU429InfoData_t Comm429RIURxDataGet(Uint16 v_ID_u16);
extern RIU429OrigData_t Comm429RIUOrigDataGet(Uint16 v_ID_u16);
extern A429Info_t Comm429RIURxStateGet(Uint16 v_ID_u16);

extern Uint32 Comm429RIUTxLastWordGet(void);
/* ***************************************************************** */
#define RIU_POD_EVENT_GROUP_SOFTV      (0U)
#define RIU_POD_EVENT_GROUP_PRE_FUEL   (1U)
#define RIU_POD_EVENT_GROUP_LIFE       (2U)
#define RIU_POD_EVENT_GROUP_OIL_RESET  (3U)
#define RIU_TX_PERIOD_MS             (100UL)   /* RIU ICD周期发送 10次/S */
#define RIU_HEART_PATTERN_A          (0xAAU)
#define RIU_HEART_PATTERN_B          (0x55U)


#endif /* COMM429RIU_H 头文件保护结束 */

//============================================================================//
//======================= 文件结束  =======================================//
//============================================================================//
