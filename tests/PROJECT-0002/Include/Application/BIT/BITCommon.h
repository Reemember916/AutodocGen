/**********************************************************************************
 *
 * 文件名称:   BITCommon
 *
 * 功能说明:   IFBIT/MBIT共用数据结构与状态更新接口
 *
 *********************************************************************************/

#ifndef BIT_COMMON_H_
#define BIT_COMMON_H_

typedef struct _BITCommonData
{
    Uint16 currState_u16;
    Uint16 recoAble_u16;
    Uint16 faultCount_u16;
    Uint16 faultValidCount_u16;
    Uint16 recoCount_u16;
    Uint16 recoValidCount_u16;
    Uint16 faultLevel_u16;
    Uint32 errInfo_u32;
}BITCommonData_t;

/* BIT 通用状态约定(0=OK/可恢复, 1=ERR/不可恢复,三种BIT模块均一致) */
#define BIT_TEST_OK         (0U)    /* BIT 通用 OK 状态 */
#define BIT_TEST_ERR        (1U)    /* BIT 通用 ERR 状态 */
#define BIT_RECOABLE        (0U)    /* 故障可恢复 */
#define BIT_UN_RECOABLE     (1U)    /* 故障不可恢复 */

/* 设置当前 BIT 上下文的模块全局(IFBIT/MBIT 初始化时各调用一次) */
extern void BITCommonCtxInit(Uint32 *vp_resultBits_u32,
                             Uint16 *vp_faultLevel_u16);

extern Uint32 BITCommonInfoGet(const BITCommonData_t *vp_data_t,
                               Uint16 v_num_u16,
                               Uint16 v_index_u16);

extern void BITCommonStateUpdate(BITCommonData_t *vp_data_t,
                                 Uint16 v_num_u16,
                                 Uint16 v_index_u16,
                                 Uint16 v_newState_u16,
                                 Uint32 v_info_u32);

extern void BITCommonPowerTest(BITCommonData_t *vp_data_t,
                               Uint16 v_num_u16,
                               Uint16 v_bitStartIndex_u16);

extern Uint16 BITCommonADResultGet(void);

extern Uint16 BITCommon429LoopbackResultGet(Uint32 v_lastTxData_u32,
                                            Uint16 v_loopbackEnAddr_u16,
                                            Uint16 v_loopbackCntAddr_u16,
                                            Uint16 v_loopbackLAddr_u16,
                                            Uint16 v_loopbackHAddr_u16);

extern Uint16 BITCommonOkCountGet(const BITCommonData_t *vp_data_t,
                                  Uint16 v_num_u16,
                                  Uint16 v_startIndex_u16,
                                  Uint16 v_count_u16);

/* ***************************************************************** */
/* BITCommon.c 私有宏定义 */
/* ***************************************************************** */
#define BIT_COMMON_POWER_TEST_NUM    (5U)

#endif /* BIT_COMMON_H_ */
