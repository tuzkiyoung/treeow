# Treeow Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/tuzkiyoung/treeow.svg)](https://github.com/tuzkiyoung/treeow/releases)
[![GitHub Stars](https://img.shields.io/github/stars/tuzkiyoung/treeow.svg)](https://github.com/tuzkiyoung/treeow/stargazers)
[![License](https://img.shields.io/github/license/tuzkiyoung/treeow.svg)](LICENSE)

[English](#english) | [中文](#中文)

## English

This Home Assistant integration allows you to connect Treeow Home devices to Home Assistant. The integration supports all devices available in the Treeow Home app.

> [!NOTE]
> Treeow has 2 official apps. This integration **only supports devices from Treeow Home**. Devices from the regular Treeow app are not supported.

### Tested Devices
- T3 Air Purifier
- G2 Humidifier

### Supported Entity Types
- Switch
- Number
- Select
- Sensor

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
1. Download the latest release from GitHub
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
> 树新风官方有2个app，本集成**只支持Treeow Home**中的设备。Treeow无法使用本集成。

本插件可将树新风Treeow Home中的设备接入HomeAssistant，理论上支持所有Treeow Home下设备。

### 已测试设备
* T3空气净化器
* G2加湿器

### 已支持实体类型
- Switch
- Number 
- Select
- Sensor

### 安装方式

#### 通过 HACS 安装（推荐）
1. 在 Home Assistant 中打开 HACS
2. 点击"集成"
3. 点击右上角的三个点
4. 选择"自定义存储库"
5. 添加 `https://github.com/tuzkiyoung/treeow` 作为存储库URL
6. 选择"Integration"作为类别
7. 点击"添加"
8. 在 HACS 中搜索"Treeow"并安装

#### 手动安装
1. 从 GitHub 下载最新版本
2. 将 `custom_components/treeow` 文件夹解压到 Home Assistant 的 `custom_components` 目录
3. 重启 Home Assistant

### 配置

1. 进入 **配置** > **设备与服务**
2. 点击 **添加集成**
3. 搜索 "Treeow"
4. 输入您的 Treeow Home 账户凭据
5. 根据需要配置设备和实体过滤器

### 调试
在`configuration.yaml`中加入以下配置来打开调试日志：

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
