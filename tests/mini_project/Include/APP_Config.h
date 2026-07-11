#ifndef _APP_CONFIG_H_
#define _APP_CONFIG_H_

/* 应用层配置 */

#define TASK_PERIOD_MS      10
#define MAX_SENSOR_COUNT    8
#define COMM_RS422_HEAD_1   0x5A
#define COMM_RS422_HEAD_2   0xA5

typedef struct {
    Uint16 status;
    Uint16 error_code;
    Uint16 data[MAX_SENSOR_COUNT];
} SensorData_t;

extern void InitSystem(void);
extern void TimeCountInit(void);
extern Uint16 CheckSensor(Uint16 sensor_id, SensorData_t *p_data);
extern void FdataAverage(Uint16 *p_buf, Uint16 count, float *p_avg);
extern Uint16 Comm422FrameCheck(Uint16 *buf, Uint16 len);

#endif /* _APP_CONFIG_H_ */