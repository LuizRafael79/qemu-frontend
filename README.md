# QEMU Frontend GUI (PyQt5)

Uma interface gráfica leve e modular para criar, configurar e executar VMs usando QEMU via linha de comando.

## 🚀 Funcionalidades

- Detecção automática de binários QEMU instalados
- Suporte a múltiplas arquiteturas
- Edição visual de parâmetros de hardware:
  - CPUs, topology, KVM
  - Tipo de máquina e memória
  - Boot, BIOS e extras (RTC, USB, etc.)
- Interface modular separada por páginas (Hardware, Storage, Network, etc.)
- Cache inteligente para agilizar carregamento e parse
- Geração reversa de argumentos QEMU (`-cpu`, `-machine`, `-smp` etc.)

## 🧰 Requisitos

- Python 3.8+
- QEMU instalado e acessível via terminal
- Dependências Python:

```bash
pip install -r requirements.txt
```
### ⚠️ O projeto atualmente é testado principalmente em Linux.

## 📂 Estrutura

```bash
| qemu-frontend/
├── app/
│   ├── context/           # AppContext centralizado
│   ├── utils/             # qemu_helper e cache
├── ui/
│   ├── pages/             # Páginas modulares da interface
│   ├── styles/            # Estilos e temas
│   ├── widgets/           # Widgets (Menu lateral)
├── main.py                # Ponto de entrada
├── config.json            # Arquivo de configuração persistente
└── .gitignore
```

## 🖥️ Como executar
```bash
python main.py
```
