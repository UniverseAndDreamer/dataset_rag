import sys

from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
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
    #       文件校验

    pass


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

    #       step1_validate_param: 校验参数
    step1_validate_param(state)
    #       step2_upload_pdf: 申请、上传pdf文件
    step2_upload_pdf()
    #       step3_download_zipfile: 下载解压minerU返回的 解压文件
    step3_download_unzip()
    #       日志和任务状态
    logger.info(f">>> [Stub] 执行节点: {sys._getframe().f_code.co_name}")
    return state