#ifndef CONTROL_PRIV_H_
#define CONTROL_PRIV_H_

typedef void (*SysStateHandler_t)(void);
typedef void (*WorkModeHandler_t)(ConData_t *);

typedef struct _RoleConfirmContext
{
    Uint16 active_u16;
    Uint32 startTime_u32;
}RoleConfirmContext_t;

#define REFUEL_VALVE_CMD_OPEN  (0U)
#define REFUEL_VALVE_CMD_CLOSE (1U)
#define CONTROL_CRITICAL_CONFIRM_MS (10UL) /* 对端基础状态关键失效确认窗口 */

/* 控制模块内部共享状态 */
extern ConData_t s_sysConData_t;
extern Uint16 s_maintCMDExeState_u16;
extern Uint16 s_maintCMDExeCnt_u16;
extern RIU429SendData_t s_RIUSendData_t;
extern ControlModeDebounce_t s_controlModeDebounce_t;
extern Uint16 s_controlModeReentryLatch_u16;
extern RefuelModeContext_t s_refuelCtx_t;
extern ReceiveModeContext_t s_receiveCtx_t;
extern PreTaskCheckContext_t s_preTaskCheckCtx_t;
extern ControlFaultDebounce_t s_controlFaultDebounce_t;
extern ControlFaultEval_t s_controlFaultEval_t;
extern Uint16 s_controlFaultTripActive_u16;
extern Uint16 s_controlFaultClearCnt_u16;
extern Uint16 s_controlFaultRecoveryCooldownCnt_u16;

/* 控制模块内部跨文件调用接口。 */
extern Uint16 ControlRIUActiveSourceSelect(Uint16 *vp_commID_u16, Uint16 *vp_valid_u16);
extern Uint16 ControlCCDLActiveSourceSelect(Uint16 *vp_commID_u16, Uint16 *vp_valid_u16);
extern void ControlModeDebounceReset(void);
extern void ControlModeReentryLatchReset(void);
extern void ControlModeReentryLatchSet(Uint16 v_workMode_u16);
extern union fuelCmd_Data ControlRiuFuelCmdGet(void);
extern void PreTaskCheckContextReset(void);
extern void SysStateProcessDefault(void);
extern Uint16 ControlCriticalFaultExist(void);
extern Uint16 ControlPeerCriticalFaultExist(void);
extern void ControlFaultDebounceReset(void);
extern Uint16 ControlFaultRawExists(void);
extern void ControlFaultEvaluate(ControlFaultEval_t *v_p_faultEval_t);
extern void ControlFaultActionApply(const ControlFaultEval_t *v_p_faultEval_t, ConData_t *v_p_ConData_t);
extern Uint16 WorkModeRIUDataCheck(Uint16 v_objectData_u16, Uint16 v_modeData_u16);
extern void WorkModeDataObtain(void);
extern void StandbyFuncUpdate(void);
extern void GroundMaintStateUpdate(void);
extern void WorkModeProcessReceive(ConData_t *v_p_ConData_t);
extern void WorkModeProcessRefuel(ConData_t *v_p_ConData_t);
extern void CommDataSourceUpdate(void);
extern void CHVConDataObtain(void);
extern void RuntimeRoleUpdate(void);
extern void ConOutStateUpdate(void);
extern void SysStateJudge(void);
/* ***************************************************************** */
/**
 * 【函数名】:ControlMeasureFaultExists
 *
 * 【功能描述】判断当前故障字是否满足测量系统故障组合条件
 *             统一把总测量故障、降级和各翼箱传感器故障视为测量异常
 * 【输入参数说明】v_faultInfo_un16：故障字快照
 * 【输出参数说明】无
 * 【其他说明】       与加油/受油阶段内的测量故障口径保持一致
 * 【返回】          VALID-异常 / INVALID-正常
 */
/* ***************************************************************** */
extern Uint16 ControlMeasureFaultExists(union faultInfo_Data v_faultInfo_un16);

/* ***************************************************************** */
/**
 * 【函数名】:ControlConFuncSwitch
 *
 * 【功能描述】控制功能阶段切换公共收口
 *             统一完成 conFuncLast/conFunc/workModeTime 三连赋值
 * 【输入参数说明】vp_ConData_t：系统控制数据指针
 * 【输入参数说明】v_conFunc_u16：目标控制功能阶段
 * 【输入参数说明】v_time_u32：阶段切换时间戳(由调用方传入,保持原 sysTime 或局部捕获时间口径)
 * 【输出参数说明】无
 * 【其他说明】       各阶段切换点复用,避免跨文件重复拼接三连语句
 * 【返回】          无
 */
/* ***************************************************************** */
extern void ControlConFuncSwitch(ConData_t *vp_ConData_t, Uint16 v_conFunc_u16, Uint32 v_time_u32);
extern void SysStateProcess(void);

#endif /* CONTROL_PRIV_H_ */
