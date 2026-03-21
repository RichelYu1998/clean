import os
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


def setup_logger(log_file: Optional[str] = None, log_level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger('FileCleaner')
    logger.setLevel(log_level)
    logger.handlers.clear()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def clean_old_files(
        directory: str,
        dry_run: bool = False,
        log_file: Optional[str] = None,
        log_level: int = logging.INFO
) -> None:
    logger = setup_logger(log_file, log_level)
    logger.info("=" * 60)
    logger.info("开始清理旧文件")
    logger.info(f"清理目录: {directory}")
    logger.info(f"保留规则: 最新的一组文件（'_'前完全一致的为一组）")
    logger.info(f"排序方式: 按文件下载到本地的毫秒时间")
    logger.info(f"测试模式: {'是' if dry_run else '否'}")
    logger.info("=" * 60)

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'}
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}
    valid_extensions = image_extensions | video_extensions
    pattern = re.compile(r'^wsxc(\d{10,})_(\d+)(\.[^.]+)$')

    directory = Path(directory)

    if not directory.exists():
        logger.error(f"目录不存在: {directory}")
        return

    if not directory.is_dir():
        logger.error(f"路径不是目录: {directory}")
        return

    matched_files = []
    logger.info("扫描文件中...")
    for file in directory.iterdir():
        if file.is_file():
            match = pattern.match(file.name)
            if match:
                main_num = match.group(1)
                sub_num = match.group(2)
                ext = match.group(3).lower()
                if ext in valid_extensions:
                    file_stat = file.stat()
                    mtime = file_stat.st_mtime
                    download_time = datetime.fromtimestamp(mtime)

                    matched_files.append({
                        'file': file,
                        'main_num': main_num,
                        'sub_num': int(sub_num),
                        'ext': ext,
                        'is_image': ext in image_extensions,
                        'is_video': ext in video_extensions,
                        'mtime': mtime,
                        'size': file_stat.st_size,
                        'download_time': download_time
                    })

    if not matched_files:
        logger.warning("没有找到符合命名规则的图片或视频文件")
        return

    matched_files.sort(key=lambda x: x['mtime'], reverse=True)
    logger.info(f"按文件下载到本地的毫秒时间排序（从最新到最旧）")

    total_files = len(matched_files)
    image_count = sum(1 for f in matched_files if f['is_image'])
    video_count = sum(1 for f in matched_files if f['is_video'])
    total_size = sum(f['size'] for f in matched_files)

    logger.info(f"找到 {total_files} 个符合条件的文件")
    logger.info(f"  - 图片: {image_count} 个")
    logger.info(f"  - 视频: {video_count} 个")
    logger.info(f"  - 总大小: {format_size(total_size)}")

    groups = {}
    for file_info in matched_files:
        main_num = file_info['main_num']
        if main_num not in groups:
            groups[main_num] = []
        groups[main_num].append(file_info)

    def get_group_latest_mtime(main_num):
        group_files = groups[main_num]
        return max(f['mtime'] for f in group_files)

    sorted_main_nums = sorted(groups.keys(), key=get_group_latest_mtime, reverse=True)

    logger.info(f"共 {len(groups)} 组文件（按'_'前部分分组）")
    for i, main_num in enumerate(sorted_main_nums[:5], 1):
        group_files = groups[main_num]
        latest_file = max(group_files, key=lambda x: x['mtime'])
        group_time = latest_file['download_time'].strftime('%Y-%m-%d %H:%M:%S')
        group_images = sum(1 for f in group_files if f['is_image'])
        group_videos = sum(1 for f in group_files if f['is_video'])
        logger.info(
            f"  组{i}: wsxc{main_num} - {len(group_files)}个文件 (图片:{group_images}, 视频:{group_videos}, 最新下载时间:{group_time})")

    if len(sorted_main_nums) > 5:
        logger.info(f"  ... 还有 {len(sorted_main_nums) - 5} 组")

    latest_main_num = sorted_main_nums[0]
    latest_group = groups[latest_main_num]
    latest_file = max(latest_group, key=lambda x: x['mtime'])
    latest_time_str = latest_file['download_time'].strftime('%Y-%m-%d %H:%M:%S')

    logger.info(f"\n将保留最新的一组文件（组名: wsxc{latest_main_num}, 最新下载时间: {latest_time_str}）")
    logger.info(f"  该组共 {len(latest_group)} 个文件")
    logger.info(f"  将删除其他 {len(sorted_main_nums) - 1} 组旧文件，共 {total_files - len(latest_group)} 个文件")

    logger.info("\n文件列表（从最新到最旧）：")
    for i, file_info in enumerate(matched_files[:10], 1):
        is_latest = file_info['main_num'] == latest_main_num
        status = "保留" if is_latest else "删除"
        file_type = "图片" if file_info['is_image'] else "视频"
        download_time_str = file_info['download_time'].strftime('%Y-%m-%d %H:%M:%S')
        logger.info(
            f"{i:3d}. [{status}] {file_info['file'].name} ({file_type}, {format_size(file_info['size'])}, 下载时间: {download_time_str})")

    if len(matched_files) > 10:
        logger.info(f"... 还有 {len(matched_files) - 10} 个文件")

    files_to_delete = [f for f in matched_files if f['main_num'] != latest_main_num]

    if not files_to_delete:
        logger.info("没有需要删除的文件")
        logger.info("清理完成")
        return

    delete_size = sum(f['size'] for f in files_to_delete)
    logger.info(f"\n准备删除 {len(files_to_delete)} 个旧文件，释放空间: {format_size(delete_size)}")

    for file_info in files_to_delete:
        file_type = "图片" if file_info['is_image'] else "视频"
        download_time_str = file_info['download_time'].strftime('%Y-%m-%d %H:%M:%S')
        logger.info(
            f"  - {file_info['file'].name} ({file_type}, {format_size(file_info['size'])}, 下载时间: {download_time_str})")

    if dry_run:
        logger.info("\n[测试模式] 未实际删除文件")
        logger.info("清理完成（测试模式）")
        return

    logger.info("\n开始删除文件...")
    deleted_count = 0
    failed_count = 0
    deleted_size = 0

    for file_info in files_to_delete:
        try:
            file_info['file'].unlink()
            deleted_count += 1
            deleted_size += file_info['size']
            logger.info(f"已删除: {file_info['file'].name} ({format_size(file_info['size'])})")
        except PermissionError:
            logger.error(f"删除失败（权限不足）: {file_info['file'].name}")
            failed_count += 1
        except FileNotFoundError:
            logger.warning(f"文件不存在（可能已被删除）: {file_info['file'].name}")
            failed_count += 1
        except Exception as e:
            logger.error(f"删除失败 {file_info['file'].name}: {e}")
            failed_count += 1

    logger.info("\n" + "=" * 60)
    logger.info("清理完成")
    logger.info(f"成功删除: {deleted_count} 个文件，释放空间: {format_size(deleted_size)}")
    if failed_count > 0:
        logger.warning(f"删除失败: {failed_count} 个文件")
    logger.info("=" * 60)


def format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def clean_old_files_by_time(
        directory: str,
        minutes: int = 5,
        dry_run: bool = False,
        log_file: Optional[str] = None,
        log_level: int = logging.INFO
) -> None:
    logger = setup_logger(log_file, log_level)
    logger.info("=" * 60)
    logger.info("开始按时间清理旧文件")
    logger.info(f"清理目录: {directory}")
    logger.info(f"删除规则: 删除 {minutes} 分钟前下载到本地的所有文件")
    logger.info(f"测试模式: {'是' if dry_run else '否'}")
    logger.info("=" * 60)

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'}
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}
    valid_extensions = image_extensions | video_extensions
    pattern = re.compile(r'^wsxc(\d{10,})_(\d+)(\.[^.]+)$')

    directory = Path(directory)

    if not directory.exists():
        logger.error(f"目录不存在: {directory}")
        return

    if not directory.is_dir():
        logger.error(f"路径不是目录: {directory}")
        return

    matched_files = []
    logger.info("扫描文件中...")

    current_time = datetime.now()
    cutoff_time = current_time.timestamp() - (minutes * 60)

    for file in directory.iterdir():
        if file.is_file():
            match = pattern.match(file.name)
            if match:
                main_num = match.group(1)
                sub_num = match.group(2)
                ext = match.group(3).lower()
                if ext in valid_extensions:
                    file_stat = file.stat()
                    mtime = file_stat.st_mtime
                    download_time = datetime.fromtimestamp(mtime)

                    matched_files.append({
                        'file': file,
                        'main_num': main_num,
                        'sub_num': int(sub_num),
                        'ext': ext,
                        'is_image': ext in image_extensions,
                        'is_video': ext in video_extensions,
                        'mtime': mtime,
                        'size': file_stat.st_size,
                        'download_time': download_time
                    })

    if not matched_files:
        logger.warning("没有找到符合命名规则的图片或视频文件")
        return

    matched_files.sort(key=lambda x: x['mtime'], reverse=True)

    total_files = len(matched_files)
    image_count = sum(1 for f in matched_files if f['is_image'])
    video_count = sum(1 for f in matched_files if f['is_video'])
    total_size = sum(f['size'] for f in matched_files)

    logger.info(f"找到 {total_files} 个符合条件的文件")
    logger.info(f"  - 图片: {image_count} 个")
    logger.info(f"  - 视频: {video_count} 个")
    logger.info(f"  - 总大小: {format_size(total_size)}")

    cutoff_time_str = datetime.fromtimestamp(cutoff_time).strftime('%Y-%m-%d %H:%M:%S')
    current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')

    logger.info(f"\n当前时间: {current_time_str}")
    logger.info(f"删除时间阈值: {cutoff_time_str} ( {minutes} 分钟前)")

    files_to_delete = [f for f in matched_files if f['mtime'] < cutoff_time]
    files_to_keep = [f for f in matched_files if f['mtime'] >= cutoff_time]

    logger.info(f"\n将保留 {len(files_to_keep)} 个文件（{minutes} 分钟内下载的）")
    logger.info(f"将删除 {len(files_to_delete)} 个文件（{minutes} 分钟前下载的）")

    if not files_to_delete:
        logger.info("没有需要删除的文件")
        logger.info("清理完成")
        return

    delete_size = sum(f['size'] for f in files_to_delete)
    logger.info(f"\n准备删除 {len(files_to_delete)} 个旧文件，释放空间: {format_size(delete_size)}")

    logger.info("\n将要删除的文件列表：")
    for i, file_info in enumerate(files_to_delete, 1):
        file_type = "图片" if file_info['is_image'] else "视频"
        download_time_str = file_info['download_time'].strftime('%Y-%m-%d %H:%M:%S')
        time_diff = (current_time - file_info['download_time']).total_seconds() / 60
        logger.info(
            f"{i:3d}. {file_info['file'].name} ({file_type}, {format_size(file_info['size'])}, 下载时间: {download_time_str}, {time_diff:.1f}分钟前)")

    if dry_run:
        logger.info("\n[测试模式] 未实际删除文件")
        logger.info("清理完成（测试模式）")
        return

    logger.info("\n开始删除文件...")
    deleted_count = 0
    failed_count = 0
    deleted_size = 0

    for file_info in files_to_delete:
        try:
            file_info['file'].unlink()
            deleted_count += 1
            deleted_size += file_info['size']
            logger.info(f"已删除: {file_info['file'].name} ({format_size(file_info['size'])})")
        except PermissionError:
            logger.error(f"删除失败（权限不足）: {file_info['file'].name}")
            failed_count += 1
        except FileNotFoundError:
            logger.warning(f"文件不存在（可能已被删除）: {file_info['file'].name}")
            failed_count += 1
        except Exception as e:
            logger.error(f"删除失败 {file_info['file'].name}: {e}")
            failed_count += 1

    logger.info("\n" + "=" * 60)
    logger.info("清理完成")
    logger.info(f"成功删除: {deleted_count} 个文件，释放空间: {format_size(deleted_size)}")
    if failed_count > 0:
        logger.warning(f"删除失败: {failed_count} 个文件")
    logger.info("=" * 60)


def list_files(
        directory: str,
        log_file: Optional[str] = None,
        log_level: int = logging.INFO
) -> None:
    logger = setup_logger(log_file, log_level)
    logger.info("=" * 60)
    logger.info("扫描文件列表")
    logger.info(f"扫描目录: {directory}")
    logger.info(f"排序方式: 按文件下载到本地的毫秒时间")
    logger.info("=" * 60)

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'}
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}
    valid_extensions = image_extensions | video_extensions
    pattern = re.compile(r'^wsxc(\d{10,})_(\d+)(\.[^.]+)$')

    directory = Path(directory)

    if not directory.exists():
        logger.error(f"目录不存在: {directory}")
        return

    matched_files = []
    logger.info("扫描文件中...")
    for file in directory.iterdir():
        if file.is_file():
            match = pattern.match(file.name)
            if match:
                main_num = match.group(1)
                sub_num = match.group(2)
                ext = match.group(3).lower()
                if ext in valid_extensions:
                    file_stat = file.stat()
                    mtime = file_stat.st_mtime
                    download_time = datetime.fromtimestamp(mtime)

                    matched_files.append({
                        'file': file,
                        'main_num': main_num,
                        'sub_num': int(sub_num),
                        'ext': ext,
                        'is_image': ext in image_extensions,
                        'is_video': ext in video_extensions,
                        'mtime': mtime,
                        'size': file_stat.st_size,
                        'download_time': download_time
                    })

    if not matched_files:
        logger.warning("没有找到符合命名规则的图片或视频文件")
        return

    matched_files.sort(key=lambda x: x['mtime'], reverse=True)

    total_files = len(matched_files)
    image_count = sum(1 for f in matched_files if f['is_image'])
    video_count = sum(1 for f in matched_files if f['is_video'])
    total_size = sum(f['size'] for f in matched_files)

    logger.info(f"找到 {total_files} 个符合条件的文件")
    logger.info(f"  - 图片: {image_count} 个")
    logger.info(f"  - 视频: {video_count} 个")
    logger.info(f"  - 总大小: {format_size(total_size)}")

    logger.info("\n文件列表：")
    for i, file_info in enumerate(matched_files, 1):
        file_type = "图片" if file_info['is_image'] else "视频"
        download_time_str = file_info['download_time'].strftime('%Y-%m-%d %H:%M:%S')
        logger.info(
            f"{i:3d}. {file_info['file'].name} ({file_type}, {format_size(file_info['size'])}, 下载时间: {download_time_str})")

    logger.info("\n扫描完成")


def clean_all_files(
        directory: str,
        dry_run: bool = False,
        log_file: Optional[str] = None,
        log_level: int = logging.INFO
) -> None:
    logger = setup_logger(log_file, log_level)
    logger.info("=" * 60)
    logger.info("开始删除所有文件")
    logger.info(f"清理目录: {directory}")
    logger.info(f"删除规则: 删除所有图片和视频文件，不保留任何文件")
    logger.info(f"测试模式: {'是' if dry_run else '否'}")
    logger.info("=" * 60)

    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'}
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}
    valid_extensions = image_extensions | video_extensions
    wsxc_pattern = re.compile(r'^wsxc(\d{10,})_(\d+)(\.[^.]+)$')
    screenshot_pattern = re.compile(r'^ScreenShot.*\.png$', re.IGNORECASE)
    wechat_pattern = re.compile(r'^微信图片_(\d{14})_(\d+)_(\d+)\.jpg$', re.IGNORECASE)
    qq_pattern = re.compile(r'^QQ.*', re.IGNORECASE)

    directory = Path(directory)

    if not directory.exists():
        logger.error(f"目录不存在: {directory}")
        return

    if not directory.is_dir():
        logger.error(f"路径不是目录: {directory}")
        return

    matched_files = []
    logger.info("扫描文件中...")

    for file in directory.iterdir():
        if file.is_file():
            wsxc_match = wsxc_pattern.match(file.name)
            screenshot_match = screenshot_pattern.match(file.name)
            wechat_match = wechat_pattern.match(file.name)
            qq_match = qq_pattern.match(file.name)
            
            if wsxc_match:
                main_num = wsxc_match.group(1)
                sub_num = int(wsxc_match.group(2))
                ext = wsxc_match.group(3).lower()
            elif screenshot_match:
                # 对于ScreenShot文件，使用文件名作为main_num，sub_num设为0
                main_num = file.name
                sub_num = 0
                ext = '.png'
            elif wechat_match:
                # 对于微信图片，使用时间戳作为main_num，第一个数字作为sub_num
                main_num = wechat_match.group(1)  # 日期时间戳
                sub_num = int(wechat_match.group(2))  # 第一个数字
                ext = '.jpg'
            elif qq_match:
                # 对于QQ开头文件，保留文件名作为主键，按扩展名识别
                main_num = file.name
                sub_num = 0
                ext = file.suffix.lower() or ''
            else:
                # 检查是否为有效的图片或视频文件扩展名
                file_ext = file.suffix.lower()
                if file_ext in valid_extensions:
                    main_num = file.name
                    sub_num = 0
                    ext = file_ext
                else:
                    continue
                
            if ext in valid_extensions:
                file_stat = file.stat()
                mtime = file_stat.st_mtime
                download_time = datetime.fromtimestamp(mtime)

                matched_files.append({
                    'file': file,
                    'main_num': main_num,
                    'sub_num': sub_num,
                    'ext': ext,
                    'is_image': ext in image_extensions,
                    'is_video': ext in video_extensions,
                    'mtime': mtime,
                    'size': file_stat.st_size,
                    'download_time': download_time
                })

    if not matched_files:
        logger.warning("没有找到图片或视频文件")
        return

    matched_files.sort(key=lambda x: x['mtime'], reverse=True)

    total_files = len(matched_files)
    image_count = sum(1 for f in matched_files if f['is_image'])
    video_count = sum(1 for f in matched_files if f['is_video'])
    total_size = sum(f['size'] for f in matched_files)

    logger.info(f"找到 {total_files} 个符合条件的文件")
    logger.info(f"  - 图片: {image_count} 个")
    logger.info(f"  - 视频: {video_count} 个")
    logger.info(f"  - 总大小: {format_size(total_size)}")

    logger.info(f"\n将删除所有 {total_files} 个文件，释放空间: {format_size(total_size)}")

    logger.info("\n文件列表：")
    for i, file_info in enumerate(matched_files, 1):
        file_type = "图片" if file_info['is_image'] else "视频"
        download_time_str = file_info['download_time'].strftime('%Y-%m-%d %H:%M:%S')
        logger.info(
            f"{i:3d}. {file_info['file'].name} ({file_type}, {format_size(file_info['size'])}, 下载时间: {download_time_str})")

    if dry_run:
        logger.info("\n[测试模式] 未实际删除文件")
        logger.info("清理完成（测试模式）")
        return

    logger.info("\n开始删除文件...")
    deleted_count = 0
    failed_count = 0
    deleted_size = 0

    for file_info in matched_files:
        try:
            file_info['file'].unlink()
            deleted_count += 1
            deleted_size += file_info['size']
            logger.info(f"已删除: {file_info['file'].name} ({format_size(file_info['size'])})")
        except PermissionError:
            logger.error(f"删除失败（权限不足）: {file_info['file'].name}")
            failed_count += 1
        except FileNotFoundError:
            logger.warning(f"文件不存在（可能已被删除）: {file_info['file'].name}")
            failed_count += 1
        except Exception as e:
            logger.error(f"删除失败 {file_info['file'].name}: {e}")
            failed_count += 1

    logger.info("\n" + "=" * 60)
    logger.info("清理完成")
    logger.info(f"成功删除: {deleted_count} 个文件，释放空间: {format_size(deleted_size)}")
    if failed_count > 0:
        logger.warning(f"删除失败: {failed_count} 个文件")
    logger.info("=" * 60)


def clean_png_files(
        directory: str,
        dry_run: bool = False,
        log_file: Optional[str] = None,
        log_level: int = logging.INFO
) -> None:
    logger = setup_logger(log_file, log_level)
    logger.info("=" * 60)
    logger.info("开始删除PNG文件")
    logger.info(f"清理目录: {directory}")
    logger.info(f"删除规则: 删除所有以.png结尾的文件，不保留任何文件")
    logger.info(f"测试模式: {'是' if dry_run else '否'}")
    logger.info("=" * 60)

    image_extensions = {'.png'}  # 只处理PNG文件
    valid_extensions = image_extensions

    directory = Path(directory)

    if not directory.exists():
        logger.error(f"目录不存在: {directory}")
        return

    if not directory.is_dir():
        logger.error(f"路径不是目录: {directory}")
        return

    matched_files = []
    logger.info("扫描文件中...")

    for file in directory.iterdir():
        if file.is_file() and file.name.lower().endswith('.png'):
            file_stat = file.stat()
            mtime = file_stat.st_mtime
            download_time = datetime.fromtimestamp(mtime)

            matched_files.append({
                'file': file,
                'main_num': file.name,  # 使用完整文件名作为标识
                'sub_num': 0,
                'ext': '.png',
                'is_image': True,
                'is_video': False,
                'mtime': mtime,
                'size': file_stat.st_size,
                'download_time': download_time
            })

    if not matched_files:
        logger.warning("没有找到PNG文件")
        return

    matched_files.sort(key=lambda x: x['mtime'], reverse=True)

    total_files = len(matched_files)
    total_size = sum(f['size'] for f in matched_files)

    logger.info(f"找到 {total_files} 个PNG文件")
    logger.info(f"  - 总大小: {format_size(total_size)}")

    logger.info(f"\n将删除所有 {total_files} 个PNG文件，释放空间: {format_size(total_size)}")

    logger.info("\n文件列表：")
    for i, file_info in enumerate(matched_files, 1):
        download_time_str = file_info['download_time'].strftime('%Y-%m-%d %H:%M:%S')
        logger.info(
            f"{i:3d}. {file_info['file'].name} ({format_size(file_info['size'])}, 下载时间: {download_time_str})")

    if dry_run:
        logger.info("\n[测试模式] 未实际删除文件")
        logger.info("清理完成（测试模式）")
        return

    logger.info("\n开始删除文件...")
    deleted_count = 0
    failed_count = 0
    deleted_size = 0

    for file_info in matched_files:
        try:
            file_info['file'].unlink()
            deleted_count += 1
            deleted_size += file_info['size']
            logger.info(f"已删除: {file_info['file'].name} ({format_size(file_info['size'])})")
        except PermissionError:
            logger.error(f"删除失败（权限不足）: {file_info['file'].name}")
            failed_count += 1
        except FileNotFoundError:
            logger.warning(f"文件不存在（可能已被删除）: {file_info['file'].name}")
            failed_count += 1
        except Exception as e:
            logger.error(f"删除失败 {file_info['file'].name}: {e}")
            failed_count += 1

    logger.info("\n" + "=" * 60)
    logger.info("清理完成")
    logger.info(f"成功删除: {deleted_count} 个文件，释放空间: {format_size(deleted_size)}")
    if failed_count > 0:
        logger.warning(f"删除失败: {failed_count} 个文件")
    logger.info("=" * 60)


def clean_media_files(
        directory: str,
        dry_run: bool = False,
        log_file: Optional[str] = None,
        log_level: int = logging.INFO
) -> None:
    logger = setup_logger(log_file, log_level)
    logger.info("=" * 60)
    logger.info("开始删除媒体文件")
    logger.info(f"清理目录: {directory}")
    logger.info(f"删除规则: 删除所有以.png、.jpg、.gif和.mp4结尾的文件，不保留任何文件")
    logger.info(f"测试模式: {'是' if dry_run else '否'}")
    logger.info("=" * 60)

    # 处理PNG图片、JPG图片、GIF图片和MP4视频
    valid_extensions = {'.png', '.jpg', '.gif', '.mp4'}

    directory = Path(directory)

    if not directory.exists():
        logger.error(f"目录不存在: {directory}")
        return

    if not directory.is_dir():
        logger.error(f"路径不是目录: {directory}")
        return

    matched_files = []
    logger.info("扫描文件中...")

    for file in directory.iterdir():
        if file.is_file():
            ext = file.name.lower().split('.')[-1] if '.' in file.name else ''
            ext_with_dot = f'.{ext}' if ext else ''
            
            if ext_with_dot in valid_extensions:
                file_stat = file.stat()
                mtime = file_stat.st_mtime
                download_time = datetime.fromtimestamp(mtime)

                matched_files.append({
                    'file': file,
                    'main_num': file.name,  # 使用完整文件名作为标识
                    'sub_num': 0,
                    'ext': ext_with_dot,
                    'is_image': ext_with_dot in {'.png', '.jpg', '.gif'},
                    'is_video': ext_with_dot == '.mp4',
                    'mtime': mtime,
                    'size': file_stat.st_size,
                    'download_time': download_time
                })

    if not matched_files:
        logger.warning("没有找到PNG、JPG、GIF或MP4文件")
        return

    matched_files.sort(key=lambda x: x['mtime'], reverse=True)

    total_files = len(matched_files)
    png_count = sum(1 for f in matched_files if f['ext'] == '.png')
    jpg_count = sum(1 for f in matched_files if f['ext'] == '.jpg')
    gif_count = sum(1 for f in matched_files if f['ext'] == '.gif')
    video_count = sum(1 for f in matched_files if f['is_video'])
    total_size = sum(f['size'] for f in matched_files)

    logger.info(f"找到 {total_files} 个媒体文件")
    logger.info(f"  - PNG图片: {png_count} 个")
    logger.info(f"  - JPG图片: {jpg_count} 个")
    logger.info(f"  - GIF图片: {gif_count} 个")
    logger.info(f"  - MP4视频: {video_count} 个")
    logger.info(f"  - 总大小: {format_size(total_size)}")

    logger.info(f"\n将删除所有 {total_files} 个媒体文件，释放空间: {format_size(total_size)}")

    logger.info("\n文件列表：")
    for i, file_info in enumerate(matched_files, 1):
        if file_info['ext'] == '.png':
            file_type = "PNG图片"
        elif file_info['ext'] == '.jpg':
            file_type = "JPG图片"
        elif file_info['ext'] == '.gif':
            file_type = "GIF图片"
        else:
            file_type = "MP4视频"
        download_time_str = file_info['download_time'].strftime('%Y-%m-%d %H:%M:%S')
        logger.info(
            f"{i:3d}. {file_info['file'].name} ({file_type}, {format_size(file_info['size'])}, 下载时间: {download_time_str})")

    if dry_run:
        logger.info("\n[测试模式] 未实际删除文件")
        logger.info("清理完成（测试模式）")
        return

    logger.info("\n开始删除文件...")
    deleted_count = 0
    failed_count = 0
    deleted_size = 0

    for file_info in matched_files:
        try:
            file_info['file'].unlink()
            deleted_count += 1
            deleted_size += file_info['size']
            if file_info['ext'] == '.png':
                file_type = "PNG图片"
            elif file_info['ext'] == '.jpg':
                file_type = "JPG图片"
            elif file_info['ext'] == '.gif':
                file_type = "GIF图片"
            else:
                file_type = "MP4视频"
            logger.info(f"已删除: {file_info['file'].name} ({file_type}, {format_size(file_info['size'])})")
        except PermissionError:
            logger.error(f"删除失败（权限不足）: {file_info['file'].name}")
            failed_count += 1
        except FileNotFoundError:
            logger.warning(f"文件不存在（可能已被删除）: {file_info['file'].name}")
            failed_count += 1
        except Exception as e:
            logger.error(f"删除失败 {file_info['file'].name}: {e}")
            failed_count += 1

    logger.info("\n" + "=" * 60)
    logger.info("清理完成")
    logger.info(f"成功删除: {deleted_count} 个文件，释放空间: {format_size(deleted_size)}")
    if failed_count > 0:
        logger.warning(f"删除失败: {failed_count} 个文件")
    logger.info("=" * 60)


def generate_pdf(directory: str) -> None:
    """生成 PDF 格式的脚本使用说明"""
    try:
        from fpdf import FPDF
    except ImportError:
        print("需要安装 fpdf 库才能生成 PDF: pip install fpdf")
        print("将改为生成 README.md 文件")
        generate_readme(directory, os.path.basename(__file__))
        return
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 16)
            self.cell(0, 10, '文件清理工具使用说明', 0, 1, 'C')
            self.ln(10)
        
        def chapter_title(self, title):
            self.set_font('Arial', 'B', 14)
            self.cell(0, 10, title, 0, 1, 'L')
            self.ln(5)
        
        def chapter_body(self, body):
            self.set_font('Arial', '', 12)
            self.multi_cell(0, 10, body)
            self.ln()
    
    pdf = PDF()
    pdf.add_page()
    
    # 标题
    pdf.chapter_title('项目描述')
    pdf.chapter_body('这是一个用于清理下载目录中旧文件或特定类型文件的 Python 脚本。')
    
    # 功能特性
    pdf.chapter_title('功能特性')
    features = """
- 按组清理 (clean): 保留最新的一组文件（'_'前完全一致的为一组），删除其他旧文件
- 按时间清理 (time): 删除指定分钟前下载的文件
- 列出文件 (list): 仅列出符合条件的文件，不进行删除
- 删除所有文件 (all): 删除所有图片和视频文件
- 删除PNG文件 (png): 仅删除PNG格式的图片文件
- 删除媒体文件 (media): 删除PNG、JPG、GIF图片和MP4视频文件
"""
    pdf.chapter_body(features)
    
    # 支持的文件格式
    pdf.chapter_title('支持的文件格式')
    formats = """
- 图片: .jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff, .svg
- 视频: .mp4, .avi, .mov, .mkv, .flv, .wmv, .webm, .m4v
- 特殊格式: ScreenShot*.png, 微信图片_*.jpg
"""
    pdf.chapter_body(formats)
    
    # 文件命名规则
    pdf.chapter_title('文件命名规则')
    naming = """
脚本主要处理以下命名格式的文件：
- wsxc[数字]_[数字].[扩展名] (如: wsxc1234567890_1.jpg)
- ScreenShot*.png
- 微信图片_[时间戳]_[数字]_[数字].jpg
"""
    pdf.chapter_body(naming)
    
    # 使用方法
    pdf.chapter_title('使用方法')
    usage = """
1. 修改脚本底部的配置变量
2. 运行 python clean.py

配置参数：
- DOWNLOAD_DIR: 要清理的目录路径（默认为脚本所在目录）
- LOG_FILE: 日志文件路径（默认为 "clean_files.log"）
- LOG_LEVEL: 日志级别（默认为 logging.INFO）
- DRY_RUN: 是否为测试模式（True=测试模式，不实际删除文件）
- MODE: 清理模式 ("clean", "time", "list", "all", "png", "media")
- CLEAN_MINUTES: 按时间清理时的分钟数（默认为5分钟）
"""
    pdf.chapter_body(usage)
    
    # 示例
    pdf.chapter_title('示例')
    examples = """
测试模式运行（不实际删除文件）:
DRY_RUN = True
MODE = "clean"

删除5分钟前的文件:
MODE = "time"
CLEAN_MINUTES = 5

仅列出文件:
MODE = "list"
"""
    pdf.chapter_body(examples)
    
    # 注意事项
    pdf.chapter_title('注意事项')
    notes = """
1. 备份重要文件：在运行删除操作前，请确保已备份重要文件
2. 测试模式：首次使用建议开启 DRY_RUN = True 进行测试
3. 权限问题：确保脚本有删除文件的权限
4. 文件锁定：正在使用的文件可能删除失败
5. 不可逆操作：删除的文件无法恢复
"""
    pdf.chapter_body(notes)
    
    # 依赖项
    pdf.chapter_title('依赖项')
    deps = """
- Python 3.6+
- fpdf (用于生成PDF): pip install fpdf
"""
    pdf.chapter_body(deps)
    
    # 版本信息
    pdf.chapter_title('版本信息')
    version_info = f"""
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
脚本位置: {os.path.abspath(__file__)}
清理目录: {directory}
"""
    pdf.chapter_body(version_info)
    
    pdf_path = os.path.join(directory, "脚本使用说明.pdf")
    try:
        pdf.output(pdf_path)
        print(f"PDF 说明文档已生成: {pdf_path}")
    except Exception as e:
        print(f"生成 PDF 失败: {e}")


def generate_readme(directory: str, script_name: str) -> None:
    """生成 README.md 文件（备用）"""
    readme_content = f"""# 文件清理工具

版本: v1.2.1

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

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
脚本位置: {os.path.abspath(__file__)}
清理目录: {directory}
"""
    
    readme_filename = os.path.splitext(script_name)[0] + ".md"
    readme_path = os.path.join(directory, readme_filename)
    readme_content += f"""

## 版本历史

- 2026年3月21日: 修改脚本以生成以脚本文件命名的 README 文件；添加命令行参数支持，并生成Windows批处理文件(clean.bat)和Linux Shell脚本(clean.sh)用于运行脚本

"""
    try:
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        print(f"README.md 已生成: {readme_path}")
    except Exception as e:
        print(f"生成 README.md 失败: {e}")


if __name__ == "__main__":
    import argparse
    import platform
    import os
    
    parser = argparse.ArgumentParser(description='File cleaner script')
    parser.add_argument('--directory', default=os.path.dirname(os.path.abspath(__file__)), help='Directory to clean')
    parser.add_argument('--log-file', default='clean_files.log', help='Log file path')
    parser.add_argument('--log-level', type=int, default=logging.INFO, help='Log level')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('--mode', choices=['clean', 'time', 'list', 'all', 'png', 'media'], default='all', help='Clean mode')
    parser.add_argument('--minutes', type=int, default=5, help='Minutes for time mode')
    
    args = parser.parse_args()
    
    # 生成 README.md
    script_name = os.path.basename(__file__)
    generate_readme(args.directory, script_name)
    
    if args.mode == "clean":
        clean_old_files(
            directory=args.directory,
            dry_run=args.dry_run,
            log_file=args.log_file,
            log_level=args.log_level
        )
    elif args.mode == "time":
        clean_old_files_by_time(
            directory=args.directory,
            minutes=args.minutes,
            dry_run=args.dry_run,
            log_file=args.log_file,
            log_level=args.log_level
        )
    elif args.mode == "list":
        list_files(
            directory=args.directory,
            log_file=args.log_file,
            log_level=args.log_level
        )
    elif args.mode == "all":
        clean_all_files(
            directory=args.directory,
            dry_run=args.dry_run,
            log_file=args.log_file,
            log_level=args.log_level
        )
    elif args.mode == "png":
        clean_png_files(
            directory=args.directory,
            dry_run=args.dry_run,
            log_file=args.log_file,
            log_level=args.log_level
        )
    elif args.mode == "media":
        clean_media_files(
            directory=args.directory,
            dry_run=args.dry_run,
            log_file=args.log_file,
            log_level=args.log_level
        )