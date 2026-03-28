import os
import sys
import time
from pathlib import Path

import requests

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

def step1_validate_param(state: ImportGraphState):
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
        local_dir_obj = local_dir_obj.mkdir(parents=True, exist_ok=True)

    return pdf_path_obj, local_dir_obj


def step2_upload_pdf(pdf_path_obj: Path) -> str:
    token = os.getenv("MINERU_API_TOKEN")
    base_url = os.getenv("MINERU_BASE_URL")
    url = f"{base_url}/file-urls/batch"
    header = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = {
        "files": [
            {"name": f"{pdf_path_obj.name}"}
        ],
        "model_version": "vlm"
    }
    response = requests.post(url, headers=header, json=data)
    if response.status_code != 200 or response.json()["code"] != 0:
        logger.error("[step2_upload_pdf]请求minerU解析接口失败，请检查输入文件路径是否正确！！ ")
        raise RuntimeError("[step2_upload_pdf]请求minerU解析接口失败，请检查输入文件路径是否正确！！")
    batch_id = response.json()["data"]["batch_id"]
    upload_url = response.json()["data"]["file_urls"][0]

    # 2.将文件上传到对应的解析地址
    # put请求使用session
    session = requests.Session()
    session.trust_env = False  # 1.禁止走代理 2. 复用请求对象

    try:
        with open(file=pdf_path_obj, mode="rb") as f:
            res_upload = session.put(url=upload_url, data=f)
            if res_upload.status_code != 200 or res_upload.json()["code"] != 0:
                logger.error("[step2_upload_pdf]请求minerU上传文件失败，请检查输入文件路径是否正确！！ ")
                raise RuntimeError("[step2_upload_pdf]请求minerU上传文件失败，请检查输入文件路径是否正确！！")
    except Exception as e:
        logger.error("[step2_upload_pdf]请求minerU上传文件失败，请检查输入文件路径是否正确！！ ")
        raise RuntimeError("[step2_upload_pdf]请求minerU上传文件失败，请检查输入文件路径是否正确！！ ")
    finally:
        session.close()

    # 3. 轮询上传结果获取文件
    batch_get_task_result_url = f"{base_url}/extract-results/batch/{batch_id}"
    timeout_seconds = 600  # 1s -> 1页pdf
    poll_interval = 3  # 间隔时间是3秒
    start_time = time.time()  # 进去起始时间
    while True:
        # 超时判断
        if time.time() - start_time > timeout_seconds:
            logger.error("[step2_upload_pdf]请求minerU接口超时！！ ")
            raise TimeoutError("[step2_upload_pdf]请求minerU接口超时！！ ")
        task_result = requests.get(batch_get_task_result_url, headers=header)
        if task_result.status_code != 200 or task_result.json()["code"] != 0:
            logger.error("[step2_upload_pdf]获取上传任务结果失败 ")
            raise RuntimeError("[step2_upload_pdf]获取上传任务结果失败")
        # 上传任务结果，取第一个
        extract_result = task_result.json()["extract_result"][0]
        if extract_result["state"] != "done":
            time.sleep(poll_interval)
        else:
            # 说明可以拿到结果
            full_zip_url = extract_result["full_zip_url"]
            logger.info(f"已经完成pdf的解析，耗时：{time.time() - start_time}s,解析结果：{full_zip_url}")
            return full_zip_url


def step3_download_unzip(zip_url: str, local_dir_obj: Path,stem : str ):
    # 1.下载文件
    # 2.将zip文件保存在本地
    # 3.清空旧目录
    # 4.创建新目录
    # 5.解压文件 可能叫 文件.md 低版本 也可能叫 full.md
    # 6.
    # 解压文件

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
        zip_file = step3_download_unzip(zip_url, local_dir_obj, pdf_path_obj.stem)
        return state
    except Exception as e:
        raise e
    finally:
        # 4. 节点结束的日志输出
        logger.info(f">>> {function_name} 节点执行结束,节点状态: {state}")
        add_done_task(task_id, function_name)
