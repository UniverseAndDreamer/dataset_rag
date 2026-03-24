import sys

from langgraph.constants import END

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
    task_id = state['task_id']
    function_name  = sys._getframe().f_code.co_name
    logger.info(f">>> {function_name} 执行节点: {sys._getframe().f_code.co_name}")
    add_running_task(task_id)
    #1. 接口开始的日志输出
    #2. 校验数据: local_file_path
    local_file_path = state['local_file_path']
    if not local_file_path:
        return END
    #3. 记录任务状态
    if local_file_path.endswith('.pdf'):
        state['is_pdf_read_enabled'] = True
    elif local_file_path.endswith('.md'):
        state['is_md_read_enabled'] = True
    else:
        logger.error()
        raise Exception()
    #4. 节点结束的日志输出
    logger.info(f">>> {function_name} 执行节点: {sys._getframe().f_code.co_name}")
    add_done_task(task_id,function_name)
    return state