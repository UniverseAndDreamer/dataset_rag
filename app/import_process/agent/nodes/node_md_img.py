import base64
import os
import re
import sys
from collections import deque
from pathlib import Path

from minio.deleteobjects import DeleteObject

from app.clients.minio_utils import minio_client
from app.conf.lm_config import lm_config
from app.conf.minio_config import minio_config
from app.core.load_prompt import load_prompt
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
from app.lm.lm_utils import get_llm_client
from app.utils.rate_limit_utils import apply_api_rate_limit
from app.utils.task_utils import add_done_task, add_running_task


def step1_get_md_content(state: ImportGraphState):
    md_path = state["md_path"]
    if not md_path:
        raise ValueError("md_path不能为空")

    md_path_obj = Path(md_path)
    if not md_path_obj.exists():
        raise FileNotFoundError(f"md_path:{md_path_obj} 文件不存在！")

    if not state["md_content"]:
        with md_path_obj.open("r", encoding="utf-8") as f:
            md_content = f.read()
        state["md_content"] = md_content
    images_dir_obj = md_path_obj.parent / "images"
    return md_content, md_path_obj, images_dir_obj


def support_image(image) -> bool:
    IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')
    return image.lower().endswith(IMAGE_EXTENSIONS)


def step2_process_images(md_content, images_dir_obj) -> list[tuple[str, str, tuple[str, str]]]:
    if not images_dir_obj:
        # 说明不存在图片
        logger.error("[step2_process_images]图片文件夹中不存在图片")
        raise ValueError("[step2_process_images]图片文件夹中不存在图片")
    results = []
    for image in os.listdir(images_dir_obj):
        if not support_image(image):
            # 说明不是图片
            continue
        # 核心逻辑：构造正则表达式
        # re.escape(image) 类似于 Java 的 Pattern.quote(image)，防止文件名中有特殊字符（如 + . ()）导致正则失效
        # 匹配模式兼容： (images/image.png) 或 (image.png)
        pattern = rf'!\[.*?\]\((?:images/)?{re.escape(image)}\)'
        # 4. 使用 finditer 找到所有引用（一张图可能在文中出现多次）
        for match in re.finditer(pattern, md_content):
            start_idx = match.start()  # 匹配项在全文的开始位置
            end_idx = match.end()  # 匹配项在全文的结束位置
            # 5. 截取上下文
            context_before = md_content[max(0, start_idx - 100): start_idx]
            context_after = md_content[end_idx: end_idx + 100]
            # 6. 结构：(文件名, 匹配到的完整字符串, (上文100字, 下文100字))
            results.append((image, str(images_dir_obj / image), (context_before, context_after)))
    return results


def step3_upload_image_to_minio(images_results,stem):
    client = minio_client
    bucket_name = minio_config.bucket_name
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
    #存储前先删除旧的文件
    object_list = minio_client.list_objects(minio_config.bucket_name,
                                            prefix=f"{minio_config.minio_img_dir[1:]}/{stem}",
                                            recursive=True)
    delete_object_list = [DeleteObject(obj.object_name) for obj in object_list]
    errors = minio_client.remove_objects(minio_config.bucket_name,delete_object_list)
    for errors in errors:
        logger.error(f"删除对象失败：{errors}")
    logger.info(f"已经完成{stem}下的对象清空，本次删除了：{len(delete_object_list)}个对象！！！")

    uploaded_urls = {}
    for image_name, image_path, _ in images_results:
        try:
            client.fput_object(bucket_name=bucket_name,
                               object_name=f"{minio_config.minio_img_dir}/{stem}/{image_name}",
                               file_path=image_path,
                               content_type="image/jpeg")
            uploaded_urls[image_name] = f"http://{minio_config.endpoint}/{bucket_name}{minio_config.minio_img_dir}/{stem}/{image_name}"
            logger.info(f"完成图片{image_name}上传，访问地址为：{uploaded_urls[image_name]}")
        except Exception as e:
            logger.error(f"上传图片失败：{image_name}，失败原因：{e}")
    return uploaded_urls


def step4_generate_summaries_with_llm(images_results, stem):
    # 获取模型
    request_times = deque()
    lm_model = get_llm_client(model=lm_config.lv_model)
    summaries = {}
    for image_name,image_path,context in images_results:
        apply_api_rate_limit(request_times, max_requests=9)
        prompt = load_prompt("image_summary",root_folder=stem,image_content=context)
        # import base64
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")  # 字节转成字符
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            # base64图片转后的字符串  jpg -> image/jpeg
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        },
                    },
                    {"type": "text", "text": f"{prompt}"},
                ],
            },
        ]
        response = lm_model.invoke(messages)
        summary = response.content.strip().replace("\n", "")
        summaries[image_name] = summary
        logger.info(f"图片：{image_name}，总结结果：{summary}")
    return summaries


def step5_copy_md_and_replace_image(upload_urls, summaries,md_path_obj,md_content):
    image_infos = {}
    for image_name, summary in summaries.items():
        if url := upload_urls.get(image_name):
            image_infos[image_name] = (summary, url)
    logger.info(f"图片处理的汇总结果:{image_infos}")

    if image_infos:
        for image_file, (summary, url) in image_infos.items():
            # 使用正则
            # ![](/xxx/xx/image_file) -> ![无所谓](无所谓image_file无所谓)
            rep = re.compile(r"!\[.*?\]\(.*?"+image_file+".*?\)")
            md_content = rep.sub(f"![{summary}]({url})", md_content)
        logger.info(f"已经完成md内容的替换，新的内容为:{md_content}")

    new_md_path_str = os.path.splitext(md_path_obj)[0] + "_new.md"

    with open(new_md_path_str, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info(f"已经完成了新内容的写入，新的地址为:{new_md_path_str}")
    return md_content, new_md_path_str



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
        # 2. 处理图片得到[image_name,image_path]
        images_results = step2_process_images(md_content, images_dir_obj)
        # 3. 将图片上传到minio，并且获取其url
        upload_urls = step3_upload_image_to_minio(images_results,md_path_obj.stem)
        # 4. 将图片及图片上下文 交给视觉大模型生成图片简介
        summaries = step4_generate_summaries_with_llm(images_results,md_path_obj.stem)
        # 5. 复制出新的md，stem_new.md,将图片的url，图片的简介替换到新的md中
        new_md_content,new_md_file_path = step5_copy_md_and_replace_image(upload_urls,summaries,md_path_obj,md_content)
        state["md_path"] = new_md_file_path
        state["md_content"] = new_md_content
        return state
    except Exception as e:
        raise e
    finally:
        # 4. 节点结束的日志输出
        logger.info(f">>> {function_name} 节点执行结束,节点状态: {state}")
        add_done_task(task_id, function_name)


if __name__ == "__main__":

    """本地测试入口：单独运行该文件时，执行MD图片处理全流程测试"""
    from app.utils.path_util import PROJECT_ROOT
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
            "md_content": ""
        }
        logger.info("开始本地测试 - MD图片处理全流程")
        # 执行核心处理流程
        result_state = node_md_img(test_state)
        logger.info(f"本地测试完成 - 处理结果状态：{result_state}")