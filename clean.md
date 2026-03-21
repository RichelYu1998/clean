# 文件清理工具

版本: v1.2

这是一个用于清理下载目录中旧文件或特定类型文件的 Python 脚本。

## 功能特性

- **按组清理** (`clean`): 保留最新的一组文件（'_'前完全一致的为一组），删除其他旧文件
- **按时间清理** (`time`): 删除指定分钟前下载的文件
- **列出文件** (`list`): 仅列出符合条件的文件，不进行删除
- **删除所有文件** (`all`): 删除所有图片和视频文件
- **删除PNG文件** (`png`): 仅删除PNG格式的图片文件
- **删除媒体文件** (`media`): 删除PNG、JPG、GIF图片和MP4视频文件

## 支持的文件格式

- **图片**: .jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff, .svg
- **视频**: .mp4, .avi, .mov, .mkv, .flv, .wmv, .webm, .m4v
- **特殊格式**: ScreenShot*.png, 微信图片_*.jpg

## 文件命名规则

脚本主要处理以下命名格式的文件：
- `wsxc[数字]_[数字].[扩展名]` (如: wsxc1234567890_1.jpg)
- `ScreenShot*.png`
- `微信图片_[时间戳]_[数字]_[数字].jpg`

## 使用方法

### 命令行运行

使用命令行参数运行脚本：

```bash
python clean.py --mode clean --dry-run
```

或使用批处理文件：

Windows: `clean.bat --mode clean --dry-run`

Linux/Mac: `./clean.sh --mode clean --dry-run`

### 参数说明

- `--directory`: 要清理的目录路径（默认为脚本所在目录）
- `--log-file`: 日志文件路径（默认为 "clean_files.log"）
- `--log-level`: 日志级别（默认为 logging.INFO）
- `--dry-run`: 启用测试模式（不实际删除文件）
- `--mode`: 清理模式
  - `clean`: 按组清理
  - `time`: 按时间清理
  - `list`: 仅列出文件
  - `all`: 删除所有文件
  - `png`: 删除PNG文件
  - `media`: 删除媒体文件
- `--minutes`: 时间模式下的分钟数（默认为5分钟）

### 示例

#### 测试模式运行（不实际删除文件）
```python
DRY_RUN = True
MODE = "clean"
```

#### 删除5分钟前的文件
```python
MODE = "time"
CLEAN_MINUTES = 5
```

#### 仅列出文件
```python
MODE = "list"
```

## 日志输出

脚本会输出详细的日志信息，包括：
- 扫描到的文件数量和大小
- 将要删除的文件列表
- 删除进度和结果统计
- 错误信息（如删除失败）

日志同时输出到控制台和指定的日志文件。

## 注意事项

1. **备份重要文件**: 在运行删除操作前，请确保已备份重要文件
2. **测试模式**: 首次使用建议开启 `DRY_RUN = True` 进行测试
3. **权限问题**: 确保脚本有删除文件的权限
4. **文件锁定**: 正在使用的文件可能删除失败
5. **不可逆操作**: 删除的文件无法恢复

## 依赖项

- Python 3.6+
- 无需额外安装包（使用标准库）

## 版本信息

生成时间: 2026-03-21 23:16:53
脚本位置: /Users/yu/Downloads/clean/clean.py
清理目录: /Users/yu/Downloads/clean


## 版本历史

- 2026年3月21日: 修改脚本以生成以脚本文件命名的 README 文件；添加命令行参数支持，并生成Windows批处理文件(clean.bat)和Linux Shell脚本(clean.sh)用于运行脚本

