import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

import requests

from app.conf.mineru_config import mineru_config
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState, create_default_state
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
    token = mineru_config.api_key
    base_url = mineru_config.base_url
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
            if res_upload.status_code != 200 :
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
        extract_result = task_result.json()['data']["extract_result"][0]
        if extract_result["state"] != "done":
            time.sleep(poll_interval)
        else:
            # 说明可以拿到结果
            full_zip_url = extract_result["full_zip_url"]
            logger.info(f"已经完成pdf的解析，耗时：{time.time() - start_time}s,解析结果：{full_zip_url}")
            return full_zip_url


def step3_download_unzip(zip_url: str, local_dir_obj: Path, stem: str):
    # 1.下载文件
    response = requests.get(zip_url)
    if response.status_code != 200:
        logger.error(f"[step3_download_unzip]下载文件失败，请检查输入文件路径是否正确！！")
        raise RuntimeError("[step3_download_unzip]下载文件失败，请检查输入文件路径是否正确！！")
    # 2.将zip文件保存在本地
    zip_file_path = local_dir_obj / f'{stem}_result.zip'
    with open(zip_file_path, "wb") as f:
        f.write(response.content)
    # 3.清空旧目录
    extract_target_dir = local_dir_obj / stem
    if extract_target_dir.exists():
        shutil.rmtree(extract_target_dir)
    # 4.创建新目录
    extract_target_dir.mkdir(parents=True, exist_ok=True)
    # 5.解压文件 可能叫 文件.md 低版本 也可能叫 full.md
    with zipfile.ZipFile(zip_file_path, 'r') as zf:
        zf.extractall(extract_target_dir)
    md_list = list(extract_target_dir.rglob("*.md"))
    if not md_list:
        logger.error("[step3_download_unzip] md list 不存在")
    # 循环取出目标md
    target_md = None
    for md in md_list:
        if md.name == stem + ".md":
            target_md = md
            break

    if not target_md:
        for md in md_list:
            if md.name.lower() == "full.md":
                target_md = md
                break

    if not target_md:
        target_md = md_list[0]
    if target_md.stem != stem:
        # target_md.with_name(f"{stem}.md") 修改path对象，返回修改后的path对象
        # target_md.rename(target_md.with_name(f"{stem}.md")) 修改文件名
        target_md = target_md.rename(target_md.with_name(f"{stem}.md"))
    # 返回绝对路径
    return str(target_md.resolve())

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
        md_path = step3_download_unzip(zip_url, local_dir_obj, pdf_path_obj.stem)
        state["md_path"] = md_path
        state["local_dir"] = str(local_dir_obj)
        return state
    except Exception as e:
        raise e
    finally:
        # 4. 节点结束的日志输出
        logger.info(f">>> {function_name} 节点执行结束,节点状态: {state}")
        add_done_task(task_id, function_name)


if __name__ == "__main__":

    # 单元测试：验证PDF转MD全流程
    logger.info("===== 开始node_pdf_to_md节点单元测试 =====")

    from app.utils.path_util import PROJECT_ROOT
    logger.info(f"测试获取根地址：{PROJECT_ROOT}")

    test_pdf_name = os.path.join("doc", "hak180产品安全手册.pdf")
    test_pdf_path = os.path.join(PROJECT_ROOT, test_pdf_name)

    # 构造测试状态
    test_state = create_default_state(
        task_id="test_pdf2md_task_001",
        pdf_path=test_pdf_path,
        local_dir=os.path.join(PROJECT_ROOT, "output")
    )

    node_pdf_to_md(test_state)

    logger.info("===== 结束node_pdf_to_md节点单元测试 =====")