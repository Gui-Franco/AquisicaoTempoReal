import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import collections
import re  

COM_PORT = 'COM3' 
BAUD_RATE = 115200
SAMPLES_DISPLAY = 100

# Limites fixos para o eixo Y (Aceleração)
Y_MIN = -20
Y_MAX = 20

# Inicialização apenas dos buffers dos eixos originais
buffers = {
    'xr': collections.deque(maxlen=SAMPLES_DISPLAY),
    'yr': collections.deque(maxlen=SAMPLES_DISPLAY),
    'zr': collections.deque(maxlen=SAMPLES_DISPLAY)
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
fig.suptitle("Acelerômetro MMA8451Q - Dados Originais (Sem Filtro)", fontsize=14)

# Linha do Eixo X
line_xr, = ax_x.plot([], [], label='X Original', color='blue', linewidth=1.5)
ax_x.set_ylabel("Aceleração X")
ax_x.legend(loc='upper right')
ax_x.grid(True)

# Linha do Eixo Y
line_yr, = ax_y.plot([], [], label='Y Original', color='green', linewidth=1.5)
ax_y.set_ylabel("Aceleração Y")
ax_y.legend(loc='upper right')
ax_y.grid(True)

# Linha do Eixo Z
line_zr, = ax_z.plot([], [], label='Z Original', color='red', linewidth=1.5)
ax_z.set_ylabel("Aceleração Z")
ax_z.set_xlabel("Amostras")
ax_z.legend(loc='upper right')
ax_z.grid(True)

def update(frame):
    amostras_por_frame = 30
    cont_leitura = 0
    
    while ser.in_waiting > 0 and cont_leitura < amostras_por_frame:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            cont_leitura += 1
            
            # Nova Regex adaptada para: "T:XXXX XR:X YR:X ZR:X | Taxa: X Hz"
            match = re.search(r"XR:(-?\d+)\s+YR:(-?\d+)\s+ZR:(-?\d+)\s+\|\s+Taxa:\s+(\d+)\s+Hz", line)
            
            if match:
                buffers['xr'].append(int(match.group(1)))
                buffers['yr'].append(int(match.group(2)))
                buffers['zr'].append(int(match.group(3)))
                
                # Opcional: Se quiser capturar a taxa para alguma lógica, ela está no match.group(4)
                # taxa_atual = int(match.group(4))
                
        except Exception:
            pass

    # Renderiza os gráficos apenas se houver dados coletados
    if len(buffers['xr']) > 0:
        eixo_horizontal = list(range(len(buffers['xr'])))
        
        # Atualização dos vetores de dados de cada linha
        line_xr.set_data(eixo_horizontal, list(buffers['xr']))
        line_yr.set_data(eixo_horizontal, list(buffers['yr']))
        line_zr.set_data(eixo_horizontal, list(buffers['zr']))
        
        # Aplicação da escala horizontal e vertical FIXA em todos os subplots
        for ax in [ax_x, ax_y, ax_z]:
            ax.set_xlim(0, SAMPLES_DISPLAY)
            ax.set_ylim(Y_MIN, Y_MAX)
                
    return line_xr, line_yr, line_zr

# Configura a animação para atualizar a cada 30 milissegundos
ani = animation.FuncAnimation(fig, update, interval=30, blit=False)
plt.tight_layout()
plt.show()

ser.close()
print("Porta serial fechada.")