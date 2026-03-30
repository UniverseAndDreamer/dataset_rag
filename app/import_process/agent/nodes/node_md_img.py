import sys

from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_done_task, add_running_task


def node_md_img(state: ImportGraphState) -> ImportGraphState:
    """
    节点: 图片处理 (node_md_img)
    为什么叫这个名字: 处理 Markdown 中的图片资源 (Image)。
    未来要实现:
    1. 扫描 Markdown 中的图片链接。
    2. 将图片上传到 MinIO 对象存储。
    3. (可选) 调用多模态模型生成图片描述。
    4. 替换 Markdown 中的图片链接为 MinIO URL。
    """
    # 1. 接口开始的日志输出
    task_id = state['task_id']
    function_name = sys._getframe().f_code.co_name
    logger.info(f">>> {function_name} 节点开始执行，现在状态为: {state}")
    add_running_task(task_id, function_name)
    try:
        # 1. 拿到md文档
        # 2. 使用正则表达式提取出所有图片
        # 3. 将图片上传到minio，并且获取其url
        # 4. 截取图片位置上下各100的上下文
        # 5. 将图片及图片上下文 交给视觉大模型生成图片简介
        # 6. 复制出新的md，stem_new.md
        # 7. 将图片的url，图片的简介替换到新的md中
        return state
    except Exception as e:
        raise e
    finally:
        # 4. 节点结束的日志输出
        logger.info(f">>> {function_name} 节点执行结束,节点状态: {state}")
        add_done_task(task_id, function_name)