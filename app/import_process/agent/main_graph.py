from pathlib import Path

from langgraph.constants import END
from langgraph.graph import StateGraph

from app.import_process.agent.nodes.node_bge_embedding import node_bge_embedding
from app.import_process.agent.nodes.node_document_split import node_document_split
from app.import_process.agent.nodes.node_entry import node_entry
from app.import_process.agent.nodes.node_import_milvus import node_import_milvus
from app.import_process.agent.nodes.node_item_name_recognition import node_item_name_recognition
from app.import_process.agent.nodes.node_md_img import node_md_img
from app.import_process.agent.nodes.node_pdf_to_md import node_pdf_to_md
from app.import_process.agent.state import ImportGraphState, create_default_state

# 定义主图
# 1.初始化状态图
workflow = StateGraph(ImportGraphState)

# 2.定义节点
workflow.set_entry_point("node_entry")
workflow.add_node("node_entry", node_entry)
workflow.add_node("node_pdf_to_md", node_pdf_to_md)
workflow.add_node("node_md_img", node_md_img)
workflow.add_node("node_item_name_recognition", node_item_name_recognition)
workflow.add_node("node_document_split", node_document_split)
workflow.add_node("node_bge_embedding", node_bge_embedding)
workflow.add_node("node_import_milvus", node_import_milvus)


def identify_the_file_type(state: ImportGraphState):
    if state['is_md_read_enabled']:
        return "node_md_img"
    elif state['is_pdf_read_enabled']:
        return "node_pdf_to_md"
    else:
        return END


# 3.定义条件边
workflow.add_conditional_edges(
    "node_entry",
    identify_the_file_type,
    {
        "node_md_img": "node_md_img",
        "node_pdf_to_md": "node_pdf_to_md",
        END: END
    }
)
# 4.添加边
workflow.add_edge("node_md_img", "node_document_split")
workflow.add_edge("node_pdf_to_md", "node_md_img")
workflow.add_edge("node_document_split", "node_item_name_recognition")
workflow.add_edge("node_item_name_recognition", "node_bge_embedding")
workflow.add_edge("node_bge_embedding", "node_import_milvus")
workflow.add_edge("node_import_milvus",END)
# 5.图编译

dr_graph = workflow.compile()

if __name__ == '__main__':
    initial_state = create_default_state(local_file_path="万用表RS-12的使用.pdf")
