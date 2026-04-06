import json
import os
import re
import sys

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task

# --- 配置参数 (Configuration) ---
# 单个Chunk最大字符长度：超过则触发二次切分（适配大模型上下文窗口）
DEFAULT_MAX_CONTENT_LENGTH = 2000
# 短Chunk合并阈值：同父标题的短Chunk会被合并，减少碎片化
MIN_CONTENT_LENGTH = 500


def step1_split_param(state: ImportGraphState):
    md_content = state["md_content"]
    if not md_content:
        # 说明md不存在，直接把凭此片
        logger.error("[node_document_split] md_content内容不存在，无法进行后续节点")
        raise ValueError("[node_document_split] md_content内容不存在，无法进行后续节点")
    # 将md内容中的换行统一替换为 /n格式
    md_content = md_content.replace("\r\n", "\n").replace("\r", "\n")
    file_title = state["file_title"]
    return md_content, file_title


def step2_document_first_split(md_content, file_title):
    # 按标题切割，
    # 准备正则
    # 按换行符切割
    # 记录是否为代码块
    #
    # 记录当前行，当前标题，当前行数
    sections = []
    pattern = r'(?m)^(?=#\s)'
    current_lines = []
    current_title = None
    title_count = 0
    is_code_buffer = False
    lines = md_content.split("\n")
    for line in lines:
        strip_line = line.strip()
        # 判断是否是代码块
        if strip_line.startswith("```") or strip_line.startswith("~~~"):
            # 说明是代码块
            is_code_buffer = not is_code_buffer
            current_lines.append(strip_line)
            continue
        if not is_code_buffer and re.match(pattern, strip_line):
            # 说明是标题
            # 如果不是第一次，要将标题存起来
            if current_title:
                # 说明不是第一次的标题
                section = {
                    "title": current_title,
                    "content": "\n".join(current_lines),
                    "file_title": file_title
                }
                sections.append(section)
            current_title = strip_line
            current_lines = [current_title]
            title_count += 1
        else:
            current_lines.append(line)
    if current_title:
        section = {
            "title": current_title,
            "content": "\n".join(current_lines),
            "file_title": file_title
        }
        sections.append(section)
    logger.info(f"完成了第一次粗切，总数为：{title_count}块")
    return sections, title_count, len(lines)


def split_long_section(section, max_length):
    # 定义容器
    sub_sections = []
    # 判断是否超长
    long_content = section['content']
    if len(long_content) <= max_length:
        return [section]
    # 定义切割器
    spliter = RecursiveCharacterTextSplitter(
        chunk_size=max_length,
        chunk_overlap=100,
        separators=["\n\n", "\n", "。", "！", "；", " "]
    )
    # 遍历切割文本，组装数据
    for index, item in enumerate(spliter.split_text(long_content), start=1):
        sub_section = {
            'title': section['title'] + f"_{index}",
            'content': item.strip(),
            'part': index,
            'parent_title': section['title']
        }
        sub_sections.append(sub_section)
    return sub_sections


def merge_short_sections(final_sections, min_length):
    # 短的合并
    # 判断条件
    short_sections = []
    pre_section = None
    for section in final_sections:
        if pre_section is None:
            pre_section = section
            continue
        will_merged_content = pre_section['content'] + "\n\n" + section['content']
        is_merged = len(will_merged_content) <= min_length and pre_section.get('parent_title') and section['parent_title'] == \
                    pre_section['parent_title']
        if is_merged:
            pre_section['content'] = will_merged_content
            pre_section['part'] = section['part']
        else:
            pre_section = section
            short_sections.append(pre_section)
    if pre_section:
        short_sections.append(pre_section)
    return short_sections


def step4_document_second_split(sections):
    # 遍历找出长的
    # 最终的sections
    final_sections = []
    for section in sections:
        # 长的细切
        sub_sections = split_long_section(section, DEFAULT_MAX_CONTENT_LENGTH)
        final_sections.extend(sub_sections)
        # 短的合并

    short_sections = merge_short_sections(final_sections, MIN_CONTENT_LENGTH)
    final_sections = short_sections
    # 补全，part和parent_title
    for section in final_sections:
        section['part'] = section.get('part') or 1
        section['parent_title'] = section.get('parent_title') or section['title']

    return final_sections


def step3_no_title_md(md_content, title_count, file_title, sections):
    if title_count == 0:
        logger.info("[step3_no_title_md] 此文章无标题")
        sections.append({'title': "无标题", 'content': md_content, "file_title": file_title})
    return sections


def step5_store_chunks(chunks, state: ImportGraphState):
    local_dir = state['local_dir']
    backup_file_path = os.path.join(local_dir, "chunk.json")
    with open(backup_file_path, "w", encoding="utf-8") as f:
        json.dump(
            chunks,
            f,
            ensure_ascii=False,  # 中文直接原文存储
            indent=4  # json带有缩进
        )
    logger.info("已经将内容进行备份存储")


def node_document_split(state: ImportGraphState) -> ImportGraphState | None:
    """
    节点: 文档切分 (node_document_split)
    为什么叫这个名字: 将长文档切分成小的 Chunks (切片) 以便检索。
    未来要实现:
    1. 基于 Markdown 标题层级进行递归切分。
    2. 对过长的段落进行二次切分。
    3. 生成包含 Metadata (标题路径) 的 Chunk 列表。
    """
    # 节点开始的日志输出
    task_id = state['task_id']
    function_name = sys._getframe().f_code.co_name
    logger.info(f">>> {function_name} 节点开始执行，现在状态为: {state}")
    add_running_task(task_id, function_name)
    try:
        # 1. 校验参数 md_content是否存在？
        md_content, file_title = step1_split_param(state)
        # 2. 文档按标题切割，粗切
        # 切割后的结果为[{content,title,file_title}]
        sections, title_count, md_lines_length = step2_document_first_split(md_content, file_title)
        # 3. 特殊场景，如果文档没有标题，给默认标题
        sections = step3_no_title_md(md_content, title_count, file_title, sections)
        #   a.长的细切，短的合并
        # todo
        chunks = step4_document_second_split(sections)
        # 3. 将切割完的文档赋值进state
        state["chunks"] = chunks
        # 4. 存储chunks
        step5_store_chunks(chunks, state)
        return state
    except Exception as e:
        logger.exception(" {function_name} 节点执行异常")
        raise
    finally:
        # 节点结束的日志输出
        logger.info(f">>> {function_name} 节点执行结束,节点状态: {state}")
        add_done_task(task_id, function_name)


if __name__ == '__main__':
    """
    单元测试：联合node_md_img（图片处理节点）进行集成测试
    测试条件：1.已配置.env（MinIO/大模型环境） 2.存在测试MD文件 3.能导入node_md_img
    测试流程：先运行图片处理→再运行文档切分，验证端到端流程
    """

    """本地测试入口：单独运行该文件时，执行MD图片处理全流程测试"""
    from app.utils.path_util import PROJECT_ROOT
    from app.import_process.agent.nodes.node_md_img import node_md_img

    logger.info(f"本地测试 - 项目根目录：{PROJECT_ROOT}")

    # 测试MD文件路径（需手动将测试文件放入对应目录）
    test_md_name = os.path.join(r"output\hak180产品安全手册", "hak180产品安全手册.md")
    test_md_path = os.path.join(PROJECT_ROOT, test_md_name)

    # 校验测试文件是否存在
    if not os.path.exists(test_md_path):
        logger.error(f"本地测试 - 测试文件不存在：{test_md_path}")
        logger.info("请检查文件路径，或手动将测试MD文件放入项目根目录的output目录下")
    else:
        # 构造测试状态对象，模拟流程入参
        test_state = {
            "md_path": test_md_path,
            "task_id": "test_task_123456",
            "md_content": "",
            "file_title": "hak180产品安全手册",
            "local_dir": os.path.join(PROJECT_ROOT, "output"),
        }
        logger.info("开始本地测试 - MD图片处理全流程")
        # 执行核心处理流程
        result_state = node_md_img(test_state)
        logger.info(f"本地测试完成 - 处理结果状态：{result_state}")
        logger.info("\n=== 开始执行文档切分节点集成测试 ===")

        logger.info(">> 开始运行当前节点：node_document_split（文档切分）")
        final_state = node_document_split(result_state)
        final_chunks = final_state.get("chunks", [])
        logger.info(f"✅ 测试成功：最终生成{len(final_chunks)}个有效Chunk{final_chunks}")
