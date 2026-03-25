import os.path
import sys

from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_running_task, add_done_task


def node_entry(state: ImportGraphState) -> ImportGraphState:
    """
    节点: 入口节点 (node_entry)
    为什么叫这个名字: 作为图的 Entry Point，负责接收外部输入并决定流程走向。
    未来要实现:
    1. 接收文件路径。
    2. 判断文件类型 (PDF/MD)。
    3. 设置 state 中的路由标记 (is_pdf_read_enabled / is_md_read_enabled)。
    """
    # 1. 接口开始的日志输出
    task_id = state['task_id']
    function_name = sys._getframe().f_code.co_name
    logger.info(f">>> {function_name} 节点开始执行，现在状态为: {state}")
    add_running_task(task_id, function_name)

    # 2. 校验数据: local_file_path
    local_file_path = state['local_file_path']
    if not local_file_path:
        return state
    # 3. 记录任务状态
    if local_file_path.endswith('.pdf'):
        state['is_pdf_read_enabled'] = True
        state["pdf_path"] = local_file_path
    elif local_file_path.endswith('.md'):
        state['is_md_read_enabled'] = True
        state["md_path"] = local_file_path
    else:
        logger.error(f">>> {function_name} 节点文件格式非md/pdf，无法继续解析")
    # 提取文件名，防止后续没有解析出file_item
    file_name = os.path.basename(local_file_path).split(".")[0]
    state["file_title"] = file_name
    # 4. 节点结束的日志输出
    logger.info(f">>> {function_name} 节点执行结束,节点状态: {state}")
    add_done_task(task_id, function_name)
    return state
