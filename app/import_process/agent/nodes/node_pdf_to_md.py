import sys
from pathlib import Path

from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
from app.utils.path_util import PROJECT_ROOT
from app.utils.task_utils import add_running_task, add_done_task


# 流程
# 主函数：
#  def node_pdf_to_md:
#       参数：state
#       返回值：state
#       日志和任务状态
#       step1_validate_param: 校验参数
#       step2_upload_pdf: 申请、上传pdf文件
#       step3_download_zipfile: 下载解压minerU返回的
#       日志和任务状态
#   def step1_validate_param:
#       参数：state
#       返回值：文件路径对象，本地存储文件路径？ pdf_path_obj Path  local_dir_obj Path
#       非空校验
#       文件校验
#
#   def step2_upload_pdf:
#       参数：文件路径对象，本地
#
#
#

def step1_validate_param(state:ImportGraphState):
    #       非空校验
    pdf_path = state["pdf_path"]
    local_dir = state["local_dir"]
    if not pdf_path:
        raise ValueError(f"[step1_validate_param] 文件参数错误{state}")
    if not local_dir:
        local_dir = PROJECT_ROOT / "output"
    #       文件校验
    pdf_path_obj = Path(pdf_path)
    local_dir_obj = Path(local_dir)
    if not pdf_path_obj.exists():
        # 如果文件不存在直接报错
        raise FileNotFoundError(f"[step1_validate_param] 文件不存在{state}")
    if not local_dir_obj.exists():
        # 如果工作目录不存在，直接创建工作目录
        local_dir_obj = local_dir_obj.mkdir(parents=True,exist_ok=True)

    return pdf_path_obj,local_dir_obj


def step2_upload_pdf():
    pass


def step3_download_unzip():
    pass


def node_pdf_to_md(state: ImportGraphState) -> ImportGraphState:
    """
    节点: PDF转Markdown (node_pdf_to_md)
    为什么叫这个名字: 核心任务是将 PDF 非结构化数据转换为 Markdown 结构化数据。
    未来要实现:
    1. 调用 MinerU (magic-pdf) 工具。
    2. 将 PDF 转换成 Markdown 格式。
    3. 将结果保存到 state["md_content"]。
    """

    #       日志和任务状态
    # 1. 接口开始的日志输出
    task_id = state['task_id']
    function_name = sys._getframe().f_code.co_name
    logger.info(f">>> {function_name} 节点开始执行，现在状态为: {state}")
    add_running_task(task_id, function_name)
    try:
        #       step1_validate_param: 校验参数
        pdf_path_obj, local_dir_obj = step1_validate_param(state)
        #       step2_upload_pdf: 申请、上传pdf文件
        zip_url = step2_upload_pdf(pdf_path_obj)
        #       step3_download_zipfile: 下载解压minerU返回的 解压文件
        zip_file = step3_download_unzip(zip_url)
        return state
    except Exception as e:
        raise e
    finally:
        # 4. 节点结束的日志输出
        logger.info(f">>> {function_name} 节点执行结束,节点状态: {state}")
        add_done_task(task_id, function_name)




