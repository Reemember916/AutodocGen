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
extern void ControlFaultDebounceReset(void);
extern Uint16 ControlFaultRawExists(void);
extern void ControlFaultEvaluate(ControlFaultEval_t *v_p_faultEval_t);
extern void ControlFaultActionApply(const ControlFaultEval_t *v_p_faultEval_t, ConData_t *v_p_ConData_t);
extern Uint16 WorkModeRIUDataCheck(Uint16 v_objectData_u16, Uint16 v_modeData_u16);
extern void WorkModeDataObtain(void);
extern void StandbyFuncUpdate(void);
extern void GroundMaintStateUpdate(void);
extern void WorkModeProcessReceive(ConData_t *v_p_ConData_t);
extern void CommDataSourceUpdate(void);
extern void CHVConDataObtain(void);
extern void RuntimeRoleUpdate(void);
extern void ConOutStateUpdate(void);
extern void SysStateJudge(void);
extern void SysStateProcess(void);

#endif /* CONTROL_PRIV_H_ */
