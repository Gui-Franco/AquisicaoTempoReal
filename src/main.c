#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/logging/log.h> 
#include <stdlib.h>

LOG_MODULE_REGISTER(sensor_app, LOG_LEVEL_INF); 
 
#define MMA8451Q_I2C_ADDR    0x1D 
#define MMA8451Q_CTRL_REG1   0x2A 
 
#define MMA8451Q_ACTIVE_BIT  0x01 
#define MMA8451Q_ODR         (0x0 << 3) // Configura o Hardware para 800 Hz
 
#define STACK_SIZE 1024 
#define ACQ_PRIORITY 5   
#define COMM_PRIORITY 7  
 
static const struct device *const accel = DEVICE_DT_GET(DT_ALIAS(accel0)); 
static const struct device *const i2c_dev = DEVICE_DT_GET(DT_NODELABEL(i2c0)); 
 
struct sensor_data { 
    uint32_t t; 
    int32_t x_raw, y_raw, z_raw; 
    int32_t x_filt, y_filt, z_filt; 
    uint32_t taxa_hz; 
}; 

K_MSGQ_DEFINE(sensor_msgq, sizeof(struct sensor_data), 50, 4); 
 
void mma8451q_configurar_odr(void) 
{ 
    uint8_t buf[2]; 
    int ret; 
 
    buf[0] = MMA8451Q_CTRL_REG1; 
    buf[1] = 0x00; 
    ret = i2c_write(i2c_dev, buf, 2, MMA8451Q_I2C_ADDR); 
    if (ret) return; 
 
    buf[0] = MMA8451Q_CTRL_REG1; 
    buf[1] = MMA8451Q_ODR; 
    ret = i2c_write(i2c_dev, buf, 2, MMA8451Q_I2C_ADDR); 
    if (ret) return; 
 
    buf[0] = MMA8451Q_CTRL_REG1; 
    buf[1] = MMA8451Q_ODR | MMA8451Q_ACTIVE_BIT; 
    i2c_write(i2c_dev, buf, 2, MMA8451Q_I2C_ADDR); 
} 
 
#define FIR_TAPS 8  
static int64_t buffer_x[FIR_TAPS] = {0}; 
static int64_t buffer_y[FIR_TAPS] = {0}; 
static int64_t buffer_z[FIR_TAPS] = {0}; 
static int fir_index = 0; 
 
int64_t sv_to_micro(struct sensor_value *sv) { 
    return (int64_t)sv->val1 * 1000000LL + (int64_t)sv->val2; 
} 
 
void acq_thread(void) 
{ 
    struct sensor_data pacote; 
    int ret; 
    uint32_t tempo_atual = 0;
    uint32_t tempo_anterior = 0;
    uint32_t delta_t = 0;
 
    k_msleep(500);  
    printk("Iniciando Thread de Aquisição com Filtro FIR e Saída Customizada...\n"); 
 
    tempo_anterior = k_uptime_get_32();

    while (1) { 
        ret = sensor_sample_fetch(accel); 
        if (ret) { 
            k_msleep(20); 
            continue; 
        } 
 
        // Cálculo do Delta T e da Taxa Hz
        tempo_atual = k_uptime_get_32(); 
        delta_t = tempo_atual - tempo_anterior;
        pacote.t = tempo_atual;
        
        if (delta_t > 0) {
            pacote.taxa_hz = 1000 / delta_t;
            tempo_anterior = tempo_atual;
        }
 
        struct sensor_value raw_x, raw_y, raw_z; 
        sensor_channel_get(accel, SENSOR_CHAN_ACCEL_X, &raw_x); 
        sensor_channel_get(accel, SENSOR_CHAN_ACCEL_Y, &raw_y); 
        sensor_channel_get(accel, SENSOR_CHAN_ACCEL_Z, &raw_z); 
 
        // Armazena os valores brutos (Raw) inteiros na estrutura
        pacote.x_raw = raw_x.val1;
        pacote.y_raw = raw_y.val1;
        pacote.z_raw = raw_z.val1;
     
        // Alimenta o buffer do filtro com alta precisão
        buffer_x[fir_index] = sv_to_micro(&raw_x); 
        buffer_y[fir_index] = sv_to_micro(&raw_y); 
        buffer_z[fir_index] = sv_to_micro(&raw_z); 
         
        fir_index = (fir_index + 1) % FIR_TAPS; 
 
        // Processa a média móvel (FIR) de 8 pontos
        int64_t fir_out_x = 0, fir_out_y = 0, fir_out_z = 0; 
        for (int k = 0; k < FIR_TAPS; k++) { 
            fir_out_x += buffer_x[k]; 
            fir_out_y += buffer_y[k]; 
            fir_out_z += buffer_z[k]; 
        } 
 
        fir_out_x /= FIR_TAPS; 
        fir_out_y /= FIR_TAPS; 
        fir_out_z /= FIR_TAPS; 
 
        // Converte os microssegundos filtrados de volta para inteiros simples (escala do sensor)
        pacote.x_filt = (int32_t)(fir_out_x / 1000000LL);
        pacote.y_filt = (int32_t)(fir_out_y / 1000000LL);
        pacote.z_filt = (int32_t)(fir_out_z / 1000000LL);
 
        k_msgq_put(&sensor_msgq, &pacote, K_NO_WAIT); 
 
        k_msleep(8);  
    } 
} 
 
void comm_thread(void) 
{ 
    struct sensor_data received_data; 
 
    k_msleep(500); 
    LOG_INF("Iniciando Thread de Comunicação..."); 
 
    while (1) { 
        if (k_msgq_get(&sensor_msgq, &received_data, K_FOREVER) == 0) { 
             
            LOG_INF("T:%u XR:%d YR:%d ZR:%d XF:%d YF:%d ZF:%d | Taxa: %u Hz", 
                    received_data.t, 
                    received_data.x_raw, received_data.y_raw, received_data.z_raw,
                    received_data.x_filt, received_data.y_filt, received_data.z_filt,
                    received_data.taxa_hz);
        } 
    } 
} 
 
K_THREAD_DEFINE(acq_tid, STACK_SIZE, acq_thread, NULL, NULL, NULL, ACQ_PRIORITY, 0, 0); 
K_THREAD_DEFINE(comm_tid, STACK_SIZE, comm_thread, NULL, NULL, NULL, COMM_PRIORITY, 0, 0); 

void main(void) 
{ 
    if (!device_is_ready(accel) || !device_is_ready(i2c_dev)) { 
        return; 
    } 
    mma8451q_configurar_odr(); 
    while(1) { 
        k_sleep(K_FOREVER); 
    }
}