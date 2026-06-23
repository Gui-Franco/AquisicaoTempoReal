import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import collections
import re  

COM_PORT = 'COM8' 
BAUD_RATE = 115200
SAMPLES_DISPLAY = 100

# Limites fixos para o eixo Y (Aceleração) - Ajuste aqui se necessário
Y_MIN = -4000
Y_MAX = 4000

# Inicialização de buffers independentes para os 3 eixos
buffers = {
    'xr': collections.deque(maxlen=SAMPLES_DISPLAY),
    'yr': collections.deque(maxlen=SAMPLES_DISPLAY),
    'zr': collections.deque(maxlen=SAMPLES_DISPLAY),
    'xf': collections.deque(maxlen=SAMPLES_DISPLAY),
    'yf': collections.deque(maxlen=SAMPLES_DISPLAY),
    'zf': collections.deque(maxlen=SAMPLES_DISPLAY)
}

try:
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.1)
    ser.reset_input_buffer()
    print(f"Conectado com sucesso na porta {COM_PORT}!")
except Exception as e:
    print(f"Erro ao abrir a porta serial {COM_PORT}: {e}")
    exit()

# Criação de 3 subplots verticais (um para cada eixo)
fig, (ax_x, ax_y, ax_z) = plt.subplots(3, 1, sharex=True, figsize=(8, 10))
fig.suptitle("Acelerômetro MMA8451Q - Filtro Média Móvel de 6 pontos", fontsize=14)

# Linhas do Eixo X
line_xr, = ax_x.plot([], [], label='X Original (Raw)', color='blue', alpha=0.5)
line_xf, = ax_x.plot([], [], label='X Filtrado (MA)', color='blue', linewidth=2, linestyle='--')
ax_x.set_ylabel("Aceleração X")
ax_x.legend(loc='upper right')
ax_x.grid(True)

# Linhas do Eixo Y
line_yr, = ax_y.plot([], [], label='Y Original (Raw)', color='green', alpha=0.5)
line_yf, = ax_y.plot([], [], label='Y Filtrado (MA)', color='green', linewidth=2, linestyle='--')
ax_y.set_ylabel("Aceleração Y")
ax_y.legend(loc='upper right')
ax_y.grid(True)

# Linhas do Eixo Z
line_zr, = ax_z.plot([], [], label='Z Original (Raw)', color='red', alpha=0.5)
line_zf, = ax_z.plot([], [], label='Z Filtrado (MA)', color='red', linewidth=2, linestyle='--')
ax_z.set_ylabel("Aceleração Z")
ax_z.set_xlabel("Amostras")
ax_z.legend(loc='upper right')
ax_z.grid(True)

def update(frame):
    # Limita a leitura por frame para evitar o congelamento do Matplotlib
    amostras_por_frame = 30
    cont_leitura = 0
    
    while ser.in_waiting > 0 and cont_leitura < amostras_por_frame:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            cont_leitura += 1
            
            # Casamento com o padrão estendido do LOG_INF do Zephyr
            match = re.search(r"XR:(-?\d+)\s+YR:(-?\d+)\s+ZR:(-?\d+)\s+XF:(-?\d+)\s+YF:(-?\d+)\s+ZF:(-?\d+)", line)
            
            if match:
                buffers['xr'].append(int(match.group(1)))
                buffers['yr'].append(int(match.group(2)))
                buffers['zr'].append(int(match.group(3)))
                buffers['xf'].append(int(match.group(4)))
                buffers['yf'].append(int(match.group(5)))
                buffers['zf'].append(int(match.group(6)))
        except Exception:
            pass

    # Renderiza os gráficos apenas se houver dados coletados
    if len(buffers['xr']) > 0:
        eixo_horizontal = list(range(len(buffers['xr'])))
        
        # Atualização dos vetores de dados de cada linha
        line_xr.set_data(eixo_horizontal, list(buffers['xr']))
        line_xf.set_data(eixo_horizontal, list(buffers['xf']))
        
        line_yr.set_data(eixo_horizontal, list(buffers['yr']))
        line_yf.set_data(eixo_horizontal, list(buffers['yf']))
        
        line_zr.set_data(eixo_horizontal, list(buffers['zr']))
        line_zf.set_data(eixo_horizontal, list(buffers['zf']))
        
        # Aplicação da escala horizontal e vertical FIXA em todos os subplots
        for ax in [ax_x, ax_y, ax_z]:
            ax.set_xlim(0, SAMPLES_DISPLAY)
            ax.set_ylim(Y_MIN, Y_MAX)
                
    return line_xr, line_xf, line_yr, line_yf, line_zr, line_zf

# Configura a animação para atualizar a cada 30 milissegundos
ani = animation.FuncAnimation(fig, update, interval=30, blit=False)
plt.tight_layout()
plt.show()

ser.close()
print("Porta serial fechada.")