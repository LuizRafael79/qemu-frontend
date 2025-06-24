# QEMU Frontend GUI (PyQt5)

A lightweight and modular GUI for creating, configuring and running VMs using QEMU via the command line.

## 🚀 Features

- Visual that matches Gnome, using Font Awesome
- Automatic detection of installed QEMU binaries
- Support for multiple architectures
- Visual editing of hardware parameters:
- CPUs, topology, KVM
- Machine type and memory
- Boot, BIOS and extras (RTC, USB, etc.)
- Modular interface separated by pages (Hardware, Storage, Network, etc.)
- Smart caching to speed up loading and parsing
- Reverse generation of QEMU arguments (`-cpu`, `-machine`, `-smp` etc.)

## 🧰 Requirements

- Python 3.8+
- QEMU installed and accessible via terminal
- Python dependencies:

```bash
Arch Linux - pacman -S python-qtawesome
Ohters Distros - pip install -r requirements.txt
```

### ⚠️ The project is currently tested mainly on Linux.

## 📂 Structure

```bash
| qemu-frontend/
├── app/
│      ├── context/ # Centralized AppContext
│      ├── utils/ # qemu_helper and cache
├── ui/
│     ├── pages/ # Modular frontend pages
│     ├── styles/ # Styles and themes
│     ├── widgets/ # Widgets (Side menu)
├── main.py # Entry point
├── config.json # Persistent configuration file
└── .gitignore
```

## 🖥️ How to run
```bash
python main.py
```
