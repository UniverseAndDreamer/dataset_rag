import re
import sys

from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task


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
        if strip_line.startwith("```") or strip_line.startwith("~~~"):
            #说明是代码块
            is_code_buffer = not is_code_buffer
            current_lines.append(strip_line)
            continue
        if not is_code_buffer and re.match(pattern,strip_line):
            #说明是标题
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
            current_lines = [strip_line]
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
    return sections,title_count,len(lines)




def node_document_split(state: ImportGraphState) -> ImportGraphState:
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
        sections,title_count,md_lines_length = step2_document_first_split(md_content,file_title)
        #   a.长的细切，短的粗切
        # todo
        # 3. 将切割完的文档赋值进state
        return state
    except Exception as e:
        pass
    finally:
        # 节点结束的日志输出
        logger.info(f">>> {function_name} 节点执行结束,节点状态: {state}")
        add_done_task(task_id, function_name)
