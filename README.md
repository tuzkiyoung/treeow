# Treeow Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/tuzkiyoung/treeow.svg)](https://github.com/tuzkiyoung/treeow/releases)
[![GitHub Stars](https://img.shields.io/github/stars/tuzkiyoung/treeow.svg)](https://github.com/tuzkiyoung/treeow/stargazers)
[![License](https://img.shields.io/github/license/tuzkiyoung/treeow.svg)](LICENSE)
[![Validate](https://github.com/tuzkiyoung/treeow/actions/workflows/validate.yml/badge.svg)](https://github.com/tuzkiyoung/treeow/actions/workflows/validate.yml)

**Treeow Home integration for Home Assistant** - Control your Treeow smart home devices (air purifiers, humidifiers) directly from Home Assistant. This custom component enables seamless integration of 树新风 (Treeow) smart appliances into your smart home ecosystem.

**树新风 Home Assistant 集成** - 将树新风智能家居设备（空气净化器、加湿器）接入 Home Assistant，实现智能家居统一控制。

[English](#english) | [中文](#中文)

---

## English

> [!NOTE]
> Treeow has 2 official apps. This integration **only supports devices from Treeow Home app**. Devices from the regular Treeow app are not supported.

### Features

- 🏠 **Full Home Assistant Integration** - Control Treeow devices alongside your other smart home devices
- 🔄 **Real-time Sync** - Device states are synchronized in real-time
- 🎛️ **Complete Control** - Access all device functions including power, modes, fan speed, and more
- 📊 **Sensor Data** - Monitor air quality, humidity levels, and filter status
- 🤖 **Automation Ready** - Create powerful automations with Home Assistant

### Tested Devices

| Device | Type | Status |
|--------|------|--------|
| T3 | Air Purifier | ✅ Tested |
| K3 | Air Purifier| ✅ Tested |
| G2 | Humidifier  | ✅ Tested |

*Other Treeow Home devices should also work. Please report your experience!*

### Supported Entity Types

- **Switch** - Power on/off, child lock, display, etc.
- **Number** - Fan speed, target humidity, timer, etc.
- **Select** - Operating modes, fan modes, etc.
- **Sensor** - Air quality, humidity, temperature, filter life, etc.

### Installation

#### Via HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add `https://github.com/tuzkiyoung/treeow` as repository URL
6. Select "Integration" as category
7. Click "Add"
8. Search for "Treeow" in HACS and install

#### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/tuzkiyoung/treeow/releases)
2. Extract the `custom_components/treeow` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

### Configuration

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "Treeow"
4. Enter your Treeow Home account credentials
5. Configure device and entity filters as needed

### Debugging

Add the following to your `configuration.yaml` to enable debug logging:

```yaml
logger:
  default: warn
  logs:
    custom_components.treeow: debug
```

---

## 中文

> [!NOTE]
> 树新风官方有2个app，本集成**只支持 Treeow Home** 中的设备。Treeow app 中的设备无法使用本集成。

### 简介

本插件可将**树新风 Treeow Home** 中的设备接入 **Home Assistant** 智能家居平台，实现设备的统一管理和自动化控制。理论上支持所有 Treeow Home 下设备。

### 功能特点

- 🏠 **完整集成** - 在 Home Assistant 中统一控制树新风设备
- 🔄 **实时同步** - 设备状态实时更新
- 🎛️ **全面控制** - 支持电源、模式、风速等所有设备功能
- 📊 **传感器数据** - 监测空气质量、湿度、滤芯状态等
- 🤖 **自动化支持** - 与 Home Assistant 自动化无缝配合

### 已测试设备

| 设备 | 类型 | 状态 |
|------|------|------|
| T3 | 空气净化器 | ✅ 已测试 |
| K3 | 空气净化器 | ✅ 已测试 |
| G2 | 加湿器 | ✅ 已测试 |

*其他 Treeow Home 设备理论上也能使用，欢迎反馈！*

### 已支持实体类型

- **Switch（开关）** - 电源开关、童锁、显示屏等
- **Number（数值）** - 风速、目标湿度、定时器等
- **Select（选择）** - 运行模式、风速档位等
- **Sensor（传感器）** - 空气质量、湿度、温度、滤芯寿命等

### 安装方式

#### 通过 HACS 安装（推荐）

1. 在 Home Assistant 中打开 HACS
2. 点击"集成"
3. 点击右上角的三个点
4. 选择"自定义存储库"
5. 添加 `https://github.com/tuzkiyoung/treeow` 作为存储库 URL
6. 选择"Integration"作为类别
7. 点击"添加"
8. 在 HACS 中搜索"Treeow"并安装

#### 手动安装

1. 从 [GitHub Releases](https://github.com/tuzkiyoung/treeow/releases) 下载最新版本
2. 将 `custom_components/treeow` 文件夹解压到 Home Assistant 的 `custom_components` 目录
3. 重启 Home Assistant

### 配置

1. 进入 **配置** > **设备与服务**
2. 点击 **添加集成**
3. 搜索 "Treeow"
4. 输入您的 Treeow Home 账户凭据
5. 根据需要配置设备和实体过滤器

### 调试

在 `configuration.yaml` 中加入以下配置来打开调试日志：

```yaml
logger:
  default: warn
  logs:
    custom_components.treeow: debug
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
