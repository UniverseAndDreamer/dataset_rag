import sys
from pathlib import Path

from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
from app.utils.task_utils import add_done_task, add_running_task


def step1_get_md_content(state: ImportGraphState):
    md_path = state["md_path"]
    if not md_path:
        raise ValueError("md_path不能为空")

    md_path_obj = Path(md_path)
    if not md_path_obj.exists():
        raise FileNotFoundError(f"md_path:{md_path_obj} 文件不存在！")

    if not state["md_content"]:
        with open(f"{md_path}", "r") as f:
            md_content = f.read()
        state["md_content"] = md_content
    images_dir_obj = md_path_obj.parent / "images"
    return md_content, md_path_obj, images_dir_obj


def step2_process_images(md_content, images_dir_obj) -> list[tuple[str, str, tuple[str, str]]]:

    pass


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
        # 1. 校验数据：、
        #       参数：state
        #       响应：md_content
        md_content, md_path_obj, images_dir_obj = step1_get_md_content(state)
        # 2. 使用正则表达式提取出所有图片
        #       响应格式：[(图片名，图片地址，(上文,下文))]
        images_results = step2_process_images(md_content, images_dir_obj)
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
