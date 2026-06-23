import serial
import re
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import time
import threading

# --- CONFIGURAÇÕES FIXAS (NÃO ALTERAR) ---
PORTA_SERIAL = 'COM3'  
BAUD_RATE = 115200  # Travado conforme o padrão do seu prj.conf
MAX_AMOSTRAS = 200 

# Buffers de dados compartilhados entre as threads
tempos = deque(maxlen=MAX_AMOSTRAS)
eixo_xr = deque(maxlen=MAX_AMOSTRAS)
eixo_yr = deque(maxlen=MAX_AMOSTRAS)
eixo_zr = deque(maxlen=MAX_AMOSTRAS)
eixo_xf = deque(maxlen=MAX_AMOSTRAS)
eixo_yf = deque(maxlen=MAX_AMOSTRAS)
eixo_zf = deque(maxlen=MAX_AMOSTRAS)

padrao_regex = re.compile(
    r"T:(\d+)\s+XR:([+-]?\d+)\s+YR:([+-]?\d+)\s+ZR:([+-]?\d+)\s+XF:([+-]?\d+)\s+YF:([+-]?\d+)\s+ZF:([+-]?\d+)"
)

# Variáveis de controle
contador_amostras = 0
ultimo_tempo_hz = time.time()
rodando = True

try:
    ser = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=0.01)
    ser.reset_input_buffer()
    print(f"Conectado em {PORTA_SERIAL} a {BAUD_RATE} bps.")
except Exception as e:
    print(f"Erro ao abrir serial: {e}")
    exit()

# --- THREAD EXCLUSIVA PARA LEITURA DA SERIAL ---
# Ela roda em paralelo e não deixa o buffer do Windows acumular nada
def thread_leitura_serial():
    global contador_amostras, rodando
    while rodando:
        if ser.in_waiting > 0:
            try:
                linha_bruta = ser.readline().decode('utf-8', errors='ignore').strip()
                if not linha_bruta:
                    continue
                
                match = padrao_regex.search(linha_bruta)
                if match:
                    t = int(match.group(1))
                    xr = int(match.group(2))
                    yr = int(match.group(3))
                    zr = int(match.group(4))
                    xf = int(match.group(5))
                    yf = int(match.group(6))
                    zf = int(match.group(7))
                    
                    # Armazenamento rápido nos deques
                    tempos.append(t)
                    eixo_xr.append(xr)
                    eixo_yr.append(yr)
                    eixo_zr.append(zr)
                    eixo_xf.append(xf)
                    eixo_yf.append(yf)
                    eixo_zf.append(zf)
                    
                    contador_amostras += 1
            except Exception:
                pass
        else:
            time.sleep(0.001) # Evita uso de 100% da CPU

# Inicializa e dispara a thread de background
thread_uart = threading.Thread(target=thread_leitura_serial, daemon=True)
thread_uart.start()

# --- CONFIGURAÇÃO GRÁFICA (MATPLOTLIB OTIMIZADO) ---
fig, (ax_x, ax_y, ax_z) = plt.subplots(3, 1, sharex=True, figsize=(10, 8))
fig.suptitle('Filtro do Acelerômetro - Modo Multithread Otimizado', fontsize=14)

linha_xr, = ax_x.plot([], [], label='X Raw', color='blue', alpha=0.3)
linha_xf, = ax_x.plot([], [], label='X Filt', color='blue', linewidth=2, linestyle='--')
linha_yr, = ax_y.plot([], [], label='Y Raw', color='green', alpha=0.3)
linha_yf, = ax_y.plot([], [], label='Y Filt', color='green', linewidth=2, linestyle='--')
linha_zr, = ax_z.plot([], [], label='Z Raw', color='red', alpha=0.3)
linha_zf, = ax_z.plot([], [], label='Z Filt', color='red', linewidth=2, linestyle='--')

for ax in [ax_x, ax_y, ax_z]:
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.set_ylim(-4000, 4000) # Ajuste a escala inicial se necessário

def atualizar_grafico(frame):
    global ultimo_tempo_hz, contador_amostras
    
    tempo_atual = time.time()
    if tempo_atual - ultimo_tempo_hz >= 1.0:
        print(f"Taxa de Aquisição Efetiva no Python: {contador_amostras} Hz")
        contador_amostras = 0
        ultimo_tempo_hz = tempo_atual

    # Apenas plota o que a outra thread já colheu, sem travar a recepção
    if len(tempos) > 0:
        # Copia rápida das deques para evitar conflito entre threads durante o plot
        t_snapshot = list(tempos)
        linha_xr.set_data(t_snapshot, list(eixo_xr))
        linha_xf.set_data(t_snapshot, list(eixo_xf))
        linha_yr.set_data(t_snapshot, list(eixo_yr))
        linha_yf.set_data(t_snapshot, list(eixo_yf))
        linha_zr.set_data(t_snapshot, list(eixo_zr))
        linha_zf.set_data(t_snapshot, list(eixo_zf))
        
        ax_x.set_xlim(t_snapshot[0], t_snapshot[-1])
        
        # Auto-escala vertical leve baseada apenas no último snapshot
        for ax, raw_data in zip([ax_x, ax_y, ax_z], [eixo_xr, eixo_yr, eixo_zr]):
            if len(raw_data) > 0:
                ax.set_ylim(min(raw_data) - 10, max(raw_data) + 10)

    return linha_xr, linha_xf, linha_yr, linha_yf, linha_zr, linha_zf

# Usamos blit=True para renderização ultra veloz
ani = animation.FuncAnimation(fig, atualizar_grafico, interval=30, blit=True, cache_frame_data=False)

try:
    plt.tight_layout()
    plt.show()
except KeyboardInterrupt:
    pass
finally:
    rodando = False
    thread_uart.join(timeout=1.0)
    ser.close()
    print("Conexão encerrada.")