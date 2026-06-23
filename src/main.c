#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/logging/log.h> 
#include <stdlib.h>

LOG_MODULE_REGISTER(app, LOG_LEVEL_INF);

#define MMA8451Q_I2C_ADDR    0x1D
#define MMA8451Q_CTRL_REG1   0x2A
#define MMA8451Q_ACTIVE_BIT  0x01
#define MMA8451Q_ODR         (0x02 << 3) //Output Data Rate: 200 Hz 

#define STACK_SIZE 1024

#define ACQ_PRIORITY  5   // Maior prioridade (menor número)
#define COMM_PRIORITY 7   // Menor prioridade (maior número)

static const struct device *const accel = DEVICE_DT_GET(DT_NODELABEL(mma8451q));
static const struct device *const i2c_dev = DEVICE_DT_GET(DT_NODELABEL(i2c0));

struct dados_t {
    uint32_t t;
    int32_t x_raw, y_raw, z_raw;
    uint32_t taxa_hz; 
}; 
K_MSGQ_DEFINE(sensor_msgq, sizeof(struct dados_t), 10, 4); 

void mma8451q_configurar_odr(void)
{
    uint8_t buf[2];
    buf[0] = MMA8451Q_CTRL_REG1;
    buf[1] = 0x00;
    i2c_write(i2c_dev, buf, 2, MMA8451Q_I2C_ADDR);

    buf[0] = MMA8451Q_CTRL_REG1;
    buf[1] = MMA8451Q_ODR;
    i2c_write(i2c_dev, buf, 2, MMA8451Q_I2C_ADDR);

    buf[0] = MMA8451Q_CTRL_REG1;
    buf[1] = MMA8451Q_ODR | MMA8451Q_ACTIVE_BIT;
    i2c_write(i2c_dev, buf, 2, MMA8451Q_I2C_ADDR);
}

void thread_transmissao(void *arg1, void *arg2, void *arg3)
{
    struct dados_t msg; 
    while(1) {
        if(k_msgq_get(&sensor_msgq, &msg, K_FOREVER) == 0) {
            LOG_INF("T:%u XR:%d YR:%d ZR:%d | Taxa: %u Hz", 
                    msg.t, 
                    msg.x_raw, msg.y_raw, msg.z_raw,
                    msg.taxa_hz);
        }
    }
}

void thread_aquisicao(void *arg1, void *arg2, void *arg3)
{
    struct sensor_value ax, ay, az;
    int ret;
    struct dados_t pacote;

    uint32_t tempo_atual = 0;
    uint32_t tempo_anterior = 0;
    uint32_t delta_t = 0;

    if (!device_is_ready(accel) || !device_is_ready(i2c_dev)) {
        return;
    }

    mma8451q_configurar_odr();
    k_msleep(200);

    tempo_anterior = k_uptime_get_32();

    while (1) {
        ret = sensor_sample_fetch(accel);
        if (ret) {
            k_msleep(20);
            continue;
        }
        
        tempo_atual = k_uptime_get_32();
        delta_t = tempo_atual - tempo_anterior;

        pacote.t = tempo_atual;
        
        if (delta_t > 0) {
            pacote.taxa_hz = 1000 / delta_t; 
            tempo_anterior = tempo_atual; // Atualiza apenas quando o milissegundo muda
        }

        sensor_channel_get(accel, SENSOR_CHAN_ACCEL_X, &ax);
        sensor_channel_get(accel, SENSOR_CHAN_ACCEL_Y, &ay);
        sensor_channel_get(accel, SENSOR_CHAN_ACCEL_Z, &az);

        pacote.x_raw = ax.val1;
        pacote.y_raw = ay.val1;
        pacote.z_raw = az.val1;

        k_msgq_put(&sensor_msgq, &pacote, K_NO_WAIT);

  
        k_msleep(4);
    }
}

// 4. Mapeamento das novas prioridades invertidas
K_THREAD_DEFINE(transmissao_tid, STACK_SIZE, thread_transmissao, NULL, NULL, NULL, COMM_PRIORITY, 0, 0);
K_THREAD_DEFINE(aquisicao_tid, STACK_SIZE, thread_aquisicao, NULL, NULL, NULL, ACQ_PRIORITY, 0, 0);