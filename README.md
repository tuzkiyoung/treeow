# Treeow

本插件可将树新风中的设备接入HomeAssistant，理论上支持所有设备，目前只测试了T3。

> [!NOTE]
> 提交问题时请按Issues模版填写，未按模板填写问题会被忽略和关闭!!!

## 已支持实体
- Switch
- Number
- Select
- Sensor

## 安装

方法1：下载并复制`custom_components/treeow`文件夹到HomeAssistant根目录下的`custom_components`文件夹即可完成安装

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
