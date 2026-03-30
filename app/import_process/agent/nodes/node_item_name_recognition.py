import sys

from app.core.load_prompt import load_prompt
from app.core.logger import logger
from app.import_process.agent.state import ImportGraphState
from app.lm.lm_utils import get_llm_client

"""
1.构建上下文 取前几段chunk
2.使用大模型识别chunks，生成item_name
3.使用嵌入模型向量化item_name，存储稠密稀疏向量
4.修改state，给chunks赋值item_name 
5.
"""
def node_item_name_recognition(state: ImportGraphState) -> ImportGraphState:
    """
    节点: 主体识别 (node_item_name_recognition)
    为什么叫这个名字: 识别文档核心描述的物品/商品名称 (Item Name)。
    未来要实现:
    1. 取文档前几段内容。
    2. 调用 LLM 识别这篇文档讲的是什么东西 (如: "Fluke 17B+ 万用表")。
    3. 存入 state["item_name"] 用于后续数据幂等性清理。
    """


    # 1. 获取参数，chunks，file_title
    # 2. 构建上下文环境 file_title = 为了兜底，没有item_name
    # 3. 调用模型，给出chunks，生成item_name
    # 4. 修改state_chunks :item_name ->chunks[item_name]
    # 5. item_name 生成向量
    # 5. 存储到向量数据库
    logger.info(f">>> [Stub] 执行节点: {sys._getframe().f_code.co_name}")
    return state


def step3_call_llm(context,file_title):
    # 加载提示词
    human_prompt = load_prompt("item_name_recognition",file_title=file_title,context=context)
    system_prompt = load_prompt("product_recognition_system")

    llm = get_llm_client(json_mode=False)
