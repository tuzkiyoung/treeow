# Treeow Home Assistant Integration

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/tuzkiyoung/treeow.svg)](https://github.com/tuzkiyoung/treeow/releases)
[![GitHub Stars](https://img.shields.io/github/stars/tuzkiyoung/treeow.svg)](https://github.com/tuzkiyoung/treeow/stargazers)
[![License](https://img.shields.io/github/license/tuzkiyoung/treeow.svg)](LICENSE)
[![Validate](https://github.com/tuzkiyoung/treeow/actions/workflows/validate.yml/badge.svg)](https://github.com/tuzkiyoung/treeow/actions/workflows/validate.yml)

[![Open HACS Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tuzkiyoung&repository=treeow&category=integration)
[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=treeow)

**Treeow Home integration for Home Assistant** - Control your Treeow smart home devices (air purifiers, humidifiers) directly from Home Assistant. This custom component enables seamless integration of Treeow smart appliances into your smart home ecosystem.

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

- **Fan** - Unified fan control with speed and preset modes (auto-created when device has switch + fan_speed_enum)
- **Switch** - Power on/off, child lock, display, etc.
- **Number** - Fan speed, target humidity, timer, etc.
- **Select** - Operating modes, fan modes, etc.
- **Sensor** - Air quality, humidity, temperature, filter life, etc.

#### Fan Entity Features

When a device has `switch`, `fan_speed_enum`, and optionally `mode` attributes, a unified fan entity will be automatically created with the following features:

- **Power Control** - Turn the fan on/off
- **Speed Control** - Adjust fan speed with percentage (0-100%)
- **Preset Modes** - Select from available operation modes
- **Combined Commands** - Set multiple attributes (power, speed, mode) in a single command

**Usage Example:**

```yaml
# Turn on fan with speed and mode
service: fan.turn_on
target:
  entity_id: fan.treeow_19673_switch
data:
  percentage: 75
  preset_mode: "Strong Mode"

# Set fan speed
service: fan.set_percentage
target:
  entity_id: fan.treeow_19673_switch
data:
  percentage: 50

# Set preset mode
service: fan.set_preset_mode
target:
  entity_id: fan.treeow_19673_switch
data:
  preset_mode: "Sleep Mode"
```

### Installation

#### Via HACS (Recommended)

[![Open HACS Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tuzkiyoung&repository=treeow&category=integration)

1. Click the button above to open Treeow in HACS directly
2. Click "Download"
3. Restart Home Assistant

Or manually: Open HACS → Search "Treeow" → Download → Restart

#### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/tuzkiyoung/treeow/releases)
2. Extract the `custom_components/treeow` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

### Configuration

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=treeow)

1. Click the button above, or go to **Settings** > **Devices & Services**
2. Click **Add Integration** and search for "Treeow"
3. Enter your Treeow Home account credentials
4. Configure device and entity filters as needed

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

- **Fan（风扇）** - 统一的风扇控制，支持风速和模式（当设备具有 switch + fan_speed_enum 时自动创建）
- **Switch（开关）** - 电源开关、童锁、显示屏等
- **Number（数值）** - 风速、目标湿度、定时器等
- **Select（选择）** - 运行模式、风速档位等
- **Sensor（传感器）** - 空气质量、湿度、温度、滤芯寿命等

#### Fan 实体功能

当设备同时具有 `switch`、`fan_speed_enum`，以及可选的 `mode` 属性时，系统会自动创建一个统一的 fan 实体，具有以下功能：

- **电源控制** - 打开/关闭风扇
- **风速控制** - 使用百分比调节风速（0-100%）
- **预设模式** - 选择可用的运行模式
- **组合命令** - 一次性设置多个属性（电源、风速、模式）

**使用示例：**

```yaml
# 打开风扇并设置风速和模式
service: fan.turn_on
target:
  entity_id: fan.treeow_19673_switch
data:
  percentage: 75
  preset_mode: "强力模式"

# 调节风速
service: fan.set_percentage
target:
  entity_id: fan.treeow_19673_switch
data:
  percentage: 50

# 切换模式
service: fan.set_preset_mode
target:
  entity_id: fan.treeow_19673_switch
data:
  preset_mode: "睡眠模式"
```

### 安装方式

#### 通过 HACS 安装（推荐）

[![Open HACS Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tuzkiyoung&repository=treeow&category=integration)

1. 点击上方按钮直接打开 HACS 中的 Treeow 页面
2. 点击"下载"
3. 重启 Home Assistant

或手动安装：打开 HACS → 搜索 "Treeow" → 下载 → 重启

#### 手动安装

1. 从 [GitHub Releases](https://github.com/tuzkiyoung/treeow/releases) 下载最新版本
2. 将 `custom_components/treeow` 文件夹解压到 Home Assistant 的 `custom_components` 目录
3. 重启 Home Assistant

### 配置

[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=treeow)

1. 点击上方按钮，或进入 **配置** > **设备与服务**
2. 点击 **添加集成** 并搜索 "Treeow"
3. 输入您的 Treeow Home 账户凭据
4. 根据需要配置设备和实体过滤器

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
