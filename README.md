# QEMU Frontend GUI (PyQt5)

A lightweight and modular GUI for creating, configuring and running VMs using QEMU via the command line.<br>
The purpose of this project is to be a "middle ground" between the "bureaucratic" ease of Virt Manager for example, and Qemu's own "For experts" command line.

## 🚀 Features

- Visual that matches Gnome, using Font Awesome (not tested in KDE Plasma or Windows)
- Automatic detection of installed QEMU binaries (not tested in Windows, and that probably don't work)
- Support for multiple architectures (Qemu Architectures... not SO Archs)
- Visual editing of hardware parameters:
- CPUs, topology, KVM
- Machine type and memory
- Boot, BIOS and extras (RTC, USB, etc.) and more
- Modular interface separated by pages (Hardware, Storage, Network, etc.)
- Smart caching to speed up loading and parsing
- Direct generation of QEMU arguments (CLI --> GUI) auto populating the respective pages (Hardware, Storage etc)
- Reverse generation of QEMU arguments (GUI --> CLI) auto generating a complete command line args to use with Qemu

## 🧰 Requirements

- Python 3.8+
- QEMU installed and accessible via terminal
- Python dependencies:

```bash
Arch Linux - pacman -S PyQt python-qtawesome <QTVersion Above 5>
Ohters Distros - pip install PyQt qtawesome
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

## TODO
- Finish the remaining pages (Network, Audio, Display etc)
- Implement a feature that converts the virt-manager XML lists to command line arguments for Qemu
- ... a lot of others things, the repository is updated daily
