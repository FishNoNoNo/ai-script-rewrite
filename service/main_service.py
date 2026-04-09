import asyncio
import json
import os
from pathlib import Path
import random
import time
from typing import Dict, Set, Tuple

# from api.baidu_api import api as baidu_api
from api.openai_api import api as openai_api
import logging
from docx import Document
from utils.path import get_project_path
from utils.rag import rag_text_by_regex
from config.prompt import *

logger = logging.getLogger(__name__)


class TaskInfo:
    def __init__(self, idx):
        self.start_time = time.time()
        self.idx = idx

        self.status = "running"

        self.last_active_time = time.time()


class MainService:

    # get_abstract->rag->get_names->tag_names->translate->rewrite
    def __init__(self, max_retry_times=3, retry_delay=5):
        self.max_retry_times = max_retry_times
        self.retry_delay = retry_delay
        self.task_active_map: Dict[int, TaskInfo] = {}

    @staticmethod
    def _offset(d: float, r: int):
        # TODO:完善补偿曲线
        y = int(
            max(0.3, 1 - r * 0.15) * (0.00258936 * d**2 + 0.0359019 * d + 0.0532195)
        )
        if d < 0:
            return int(-d + y)
        else:
            return int(d + y)

    @staticmethod
    def read_docx(file_path) -> str:
        doc = Document(file_path)
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text

    @staticmethod
    async def _get_style(text):
        result = await openai_api.chat(prompt=EXTRACT_STYLE, text=text)
        logger.debug(result)
        return result

    @staticmethod
    async def _find_chapter(text):
        result = await openai_api.chat(prompt=FIND_CHAPTER_PATTERN, text=text)
        logger.debug(result)
        return result

    @staticmethod
    async def _get_entities(text):
        result = await openai_api.chat(prompt=EXTRACT_ENTITIES, text=text)
        logger.debug(result)
        return result

    @staticmethod
    async def _get_outline(text):
        result = await openai_api.chat(prompt=EXTRACT_OUTLINE, text=text)
        logger.debug(result)
        return result

    @staticmethod
    async def _get_names(text):
        result = await openai_api.chat(prompt=EXTRACT_NAME, text=text)
        logger.debug(result)
        return result

    @staticmethod
    def _after_solve(text: str) -> str:
        if not text:
            return ""

        result_chars = []
        length = len(text)

        punctuation_set: Set[str] = {
            ",",
            ";",
            ":",
            "、",
            "：",
            "（",
            "）",
            "(",
            ")",
            "《",
            "》",
            "【",
            "】",
            "“",
            "”",
            '"',
            "'",
            "「",
            "」",
            "『",
            "』",
        }

        for i, char in enumerate(text):
            result_chars.append(char)

            if i < length - 1:
                next_char = text[i + 1]
                should_newline = False

                if char == "。":
                    if next_char not in ("”", "\n"):
                        should_newline = True

                elif char == "”":
                    if (
                        next_char not in ("。", "\n")
                        and next_char not in punctuation_set
                    ):
                        should_newline = True

                if should_newline:
                    result_chars.append("\n")

        return "".join(result_chars)

    def _tag_name(self, text, names):
        _list = []  # 改用列表，允许重复索引（不同名字可能在相同位置，虽然概率低）

        for name in names:
            start = 0
            while True:
                idx = text.find(name, start)  # 从start位置开始查找
                if idx == -1:
                    break
                _list.append((idx, name))
                # 只替换当前找到的这一个，避免影响后续查找
                text = text[:idx] + "@@@@@@@@@" + text[idx + len(name) :]
                start = idx + 9  # 跳过替换后的占位符（9个@）

        # 按索引排序并转换为字典列表
        sorted_list = [
            {"idx": idx, "name": name}
            for idx, name in sorted(_list, key=lambda x: x[0])
        ]

        return text, sorted_list

    def _clear_tag(self, text: str, name_list):
        for item in name_list:
            name = item.get("name")
            text = text.replace("@@@@@@@@@", name, 1)

    def _update_active_time(self, idx):
        if idx not in self.task_active_map:
            return
        self.task_active_map[idx].last_active_time = time.time()

    def _update_status(self, idx, status):
        if idx not in self.task_active_map:
            return
        self.task_active_map[idx].status = status

    def _add_task_info(self, idx):
        self.task_active_map[idx] = TaskInfo(idx)

    def _del_task_info(self, idx):
        if idx not in self.task_active_map:
            return
        del self.task_active_map[idx]

    def _clear(self):
        self.task_active_map = {}

    @staticmethod
    async def _to_json(_text, callback=None, **kwargs):
        try:
            return json.loads(_text)
        except Exception as e:
            logger.exception(f"格式转换失败，原始文本: {_text[:200]}...")
            if callback:
                try:
                    new_text = await callback(**kwargs)
                    return await MainService._to_json(
                        _text=new_text, callback=callback, **kwargs
                    )
                except Exception as callback_e:
                    logger.exception(f"回调执行也失败: {callback_e}")
                    return _text
            return _text

    async def _rewrite(
        self, style, outline, entities, _text, text_len, idx: int, last_text=None
    ):
        retry_times = 0
        result_history = []
        length_history = []
        stable_length_count = {}
        max_retry_times = 10

        text = f"""
## 故事摘要（核心剧情）:
{outline}

## 剧本风格:
{style}

## 专有名词:
{entities}

## 字数限制:
{text_len}

## 上下文信息：
- 当前章节：第{idx}章
- 上一章主要情节：{last_text}

## 待改写文本:
{_text}
"""
        last_rewrite = _text
        self._update_active_time(idx)
        result = await openai_api.chat(prompt=REWRITE, text=text)
        self._update_active_time(idx)
        logger.debug(result)
        length = len(result)
        logger.info(
            f"[第{idx}集] 文本长度：{text_len}->{length}:d={abs(text_len - length)}"
        )
        result_history.append({"text": result, "length": length})
        length_history.append(length)

        while abs(length - text_len) > 50:
            retry_times += 1
            if retry_times > max_retry_times:
                best = min(result_history, key=lambda x: abs(x["length"] - text_len))
                if abs(best["length"] - text_len) > 100:
                    raise Exception("偏差过大，等待进入重试")
                return best["text"]

            last_length = length
            stable_length_count[length] = stable_length_count.get(length, 0) + 1

            is_oscillating = stable_length_count[length] >= 3

            logger.info(f"[第{idx}集] 进入第{retry_times}次重试")
            jitter = random.randint(-20, 20) if retry_times > 2 else 0
            adjusted_target = text_len + jitter

            d = length - adjusted_target
            offset = MainService._offset(d, retry_times - 1)

            length_history.append(length)

            text = f"""
## 故事摘要（核心剧情）:
{outline}

## 剧本风格:
{style}

## 专有名词:
{entities}

## 文本长度限制:
{text_len}

## 上下文信息）
- 当前章节：第{idx}章
- 上一章主要情节：{last_text}

## 当前状态:
- 目标字数：{text_len}字
- 当前字数：{length}字

## 审核后改写要求(严格遵守):
- {'扩写内容，增加细节描写' if d < 0 else '精简表达，删除冗余修饰，保留核心剧情'}
- 需要{'增加' if d < 0 else '减少'}约{offset}字（允许误差±50字）

## 上一次改写结果(可能为空):
{last_rewrite}

## 待改写文本:
{result}
"""
            last_rewrite = result

            if is_oscillating:
                raise Exception("oscillating")
            else:
                self._update_active_time(idx)
                result = await openai_api.chat(prompt=REWRITE, text=text)
                self._update_active_time(idx)
            logger.debug(result)
            length = len(result)
            result_history.append({"text": result, "length": length})

            logger.info(
                f"[第{idx}集-第{retry_times}次重试]文本长度：{last_length}->{length}:d={abs(length - text_len)}"
            )

        logger.info(f"[第{idx}集]最终文本长度：{length}")
        return result

    async def rewrite(self, style, chunk: str, idx: int, last_text=None):
        self._add_task_info(idx)
        retry_times = 0
        max_retry_times = 3
        while retry_times < max_retry_times:
            try:
                self._update_status(idx, "running")
                logger.info(f"[第{idx}集] 开始提取专有名词")
                self._update_active_time(idx)
                entities_text = await self._get_entities(chunk)
                self._update_active_time(idx)

                entities = await self._to_json(
                    entities_text, self._get_entities, text=chunk
                )
                logger.info(f"[第{idx}集] 提取专有名词完成")

                logger.info(f"[第{idx}集] 开始提取大纲")
                self._update_active_time(idx)
                outline_text = await self._get_outline(chunk)
                self._update_active_time(idx)
                outline = await self._to_json(
                    outline_text, self._get_outline, text=chunk
                )
                logger.info(f"[第{idx}集] 提取大纲完成")

                logger.info(f"[第{idx}集] 开始重写")
                text_len = len(chunk)
                logger.info(f"[第{idx}集] 字数限制：{text_len}")

                self._update_active_time(idx)
                result = await self._rewrite(
                    style=style,
                    outline=outline,
                    entities=entities,
                    _text=chunk,
                    text_len=text_len,
                    idx=idx,
                    last_text=last_text,
                )
                logger.info(f"[第{idx}集] 重写完成")
                self._update_active_time(idx)

                self._update_status(idx, "done")

                self._del_task_info(idx)

                return {
                    "idx": idx,
                    "result": result,
                }

            except Exception as e:
                self._update_status(idx, "error")

                logger.error(f"[第{idx}集] {e}")
                retry_times += 1

                if retry_times < max_retry_times:
                    self._update_status(idx, "waiting")
                    await asyncio.sleep(5)
                else:
                    self._update_status(idx, "cancelled")
                    self._del_task_info(idx)
                    return {
                        "idx": idx,
                        "chunk": chunk,
                        "last_text": last_text,
                        "error": str(e),
                    }

    async def run_task(self, file_path) -> Tuple[str, bool]:
        start_time = time.time()
        text = self.read_docx(file_path)

        prefix = "第"
        suffix = "集"
        logger.info(f"开始提取章节分隔符")
        chapter_text = await self._find_chapter(text)
        chapter = await self._to_json(chapter_text, self._find_chapter, text=text)
        logger.info(f"提取章节分隔符完成")
        confidence = chapter.get("confidence", "high")
        if confidence != "high":
            logger.warning(f"提取章节失败，置信度为{confidence}")
            return "", False
        prefix = chapter.get("prefix", prefix)
        suffix = chapter.get("suffix", suffix)
        pattern = rf"{prefix}\s*[零一二三四五六七八九十百千万\d]+\s*{suffix}\s*[：:、。，.,]?\s*[^\r\n]*"
        chunks = rag_text_by_regex(pattern, text)

        logger.info(f"共提取{len(chunks)}集")
        logger.info(f"开始提取文章风格")
        style_text = await self._get_style(text)
        style = await self._to_json(style_text, self._get_style, text=text)
        logger.info(f"提取文章风格完成")

        results = ""

        tasks = []

        asyncio.create_task(self._monitor_task())

        for idx, chunk in enumerate(chunks, 1):
            task = asyncio.create_task(
                self.rewrite(
                    style=style,
                    chunk=chunk,
                    idx=idx,
                    last_text=chunks[idx - 2] if idx > 2 else None,
                )
            )
            tasks.append(task)

            await asyncio.sleep(1)

        result_map = {}
        task_to_retry = {}
        for task in tasks:
            task_result = await task
            item = task_result
            idx = item.get("idx")
            result = item.get("result")

            if item.get("error"):
                logger.error(f"[第{idx}集] {item.get('error')}")
                task_to_retry[idx] = item
                continue

            result_map[idx] = self._after_solve(result)

        await self._handle_retries(style, result_map, task_to_retry)

        sorted_map = sorted(result_map.items(), key=lambda x: x[0])

        success = True

        for idx, result in sorted_map:
            if result == "重写失败":
                success = False
            results += f"第{idx}集" + "\n\n" + result + "\n\n"

        end_time = time.time()
        logger.info(f"任务完成，用时 {end_time - start_time:.2f} 秒")
        self._clear()
        return results, success

    async def _handle_retries(self, style, results_map, tasks_to_retry):
        """处理重试逻辑"""
        current_attempt = 1

        while tasks_to_retry and current_attempt <= self.max_retry_times:
            logger.info(
                f"开始第 {current_attempt} 轮重试，涉及任务: {list(tasks_to_retry.keys())}"
            )

            next_round_retries = {}

            tasks = []

            # 启动重试
            for idx, item in tasks_to_retry.items():
                logger.info(f"重试第 {idx} 集 (第{current_attempt}次)")

                task = asyncio.create_task(
                    self.rewrite(
                        style=style,
                        chunk=item["chunk"],
                        idx=idx,
                        last_text=item["last_text"],
                    )
                )

                tasks.append(task)

            # 等待重试完成
            for task in tasks:
                task_result = await task
                idx = task_result["idx"]
                if task_result.get("error"):
                    logger.warning(
                        f"[{idx}] 重试失败 (第{current_attempt}次): {task_result['error']}"
                    )
                    if current_attempt >= self.max_retry_times:
                        logger.error(
                            f"[{idx}] 彻底失败 (已达最大重试次数): {task_result.get('error')}"
                        )
                        results_map[idx] = "重写失败"
                        continue
                    next_round_retries[idx] = task_result
                else:
                    results_map[idx] = self._after_solve(task_result["result"])

            # 更新重试队列
            tasks_to_retry = next_round_retries
            current_attempt += 1

            # 等待后重试
            if tasks_to_retry:
                wait_time = self.retry_delay * current_attempt
                logger.info(f"等待 {wait_time} 秒后进行下一轮重试...")
                await asyncio.sleep(wait_time)

    def _write_file(self, file_path, text):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

    async def _monitor_task(self, timeout=5):
        while True:
            if len(self.task_active_map) == 0:
                await asyncio.sleep(10)
                if len(self.task_active_map) == 0:
                    break

            current_time = time.time()

            for task in self.task_active_map.values():
                # 检查总运行时间
                elapsed = current_time - task.start_time

                # 检查最后活动时间
                last_active = task.last_active_time
                idle_time = current_time - last_active

                if idle_time > 180:  # 3分钟
                    logger.warning(f"线程 {task.idx} 空闲时间过长 ({idle_time:.2f}s)")
                elif idle_time > 60:  # 1分钟
                    logger.debug(f"线程 {task.idx} 空闲时间较长 ({idle_time:.2f}s)")

                # 记录状态日志
                logger.info(
                    f"线程 {task.idx} 状态: 运行时间 {elapsed:.2f}s, 空闲 {idle_time:.2f}s, 状态: {task.status}"
                )

            await asyncio.sleep(timeout)

    async def one_file_mode(self, file_path, output_dir):
        file_name = Path(file_path).name.split(".")[0]
        result, success = await main_service.run_task(file_path)
        output_file_name = f"{file_name}.txt" if success else f"{file_name}_failed.txt"
        result_path = output_dir / output_file_name
        logger.debug(result)
        self._write_file(result_path, str(result))
        logger.info(f"文件 {file_name} 重写完成,输出到 {result_path}")

    async def dir_mode(self, input_dir, output_dir):
        files = os.listdir(input_dir)
        for file in files:
            file_path = input_dir / file
            await self.one_file_mode(file_path, output_dir=output_dir)


main_service = MainService()


async def main():
    mode = input(
        """
开始
- 选择模式(输入数字,q结束)
  1.单文件模式
  2.文件夹模式(input文件夹下的文件)
"""
    )
    if mode == "q":
        return

    cwd = get_project_path()
    output_dir = cwd / "output"
    if mode == "1":
        file_path = input("请输入文件路径:")
        await main_service.one_file_mode(file_path, output_dir=output_dir)
    else:
        input_dir = cwd / "input"
        await main_service.dir_mode(input_dir, output_dir=output_dir)

    return
