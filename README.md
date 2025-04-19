# Treeow

> [!NOTE]
> 树新风官方有2个app，本集成**只支持Treeow Home**中的设备。Treeow无法使用本集成。

本插件可将树新风Treeow Home中的设备接入HomeAssistant，理论上支持所有Treeow Home下设备。目前已测试：
* T3空气净化器
* G2加湿器

## 已支持实体
- Switch
- Number
- Select
- Sensor

## 安装

1. 下载并复制`custom_components/treeow`文件夹到HomeAssistant根目录下的`custom_components`文件夹即可完成安装

## 配置

配置 > 设备与服务 >  集成 >  添加集成 > 搜索`treeow`

## 调试
在`configuration.yaml`中加入以下配置来打开调试日志。

```yaml
logger:
  default: warn
  logs:
    custom_components.treeow: debug
```
