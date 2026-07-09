
import os
import datetime
from typing import Annotated, TypedDict, Dict, Any
from graph.subgraph.agent01MainGraph import create_agent01_subgraph
from graph.subgraph.agent02MultilSourceGraph import create_multil_subgraph
from graph.subgraph.agent05DataUnderstandingGraph import Agent05_data_understanding_graph
from graph.subgraph.agent06ToDetermine import create_agent06_subgraph
from graph.subgraph.agent09RiskJudgeGraph import create_agent09_subgraph
from graph.subgraph.agent10DecisionGraph import Agent10_decision_graph
from graph.subgraph.agent12ReportGraph import Agent12_report_graph
from utils.truncateTableUtil import myTruncateAll
import time
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from db.db import SessionLocal

def create_maingraph() -> CompiledStateGraph:
    # 构建主图
    agent01 = create_agent01_subgraph()
    agent02 = create_multil_subgraph()
    agent05 = Agent05_data_understanding_graph()
    agent06 = create_agent06_subgraph()
    agent09 = create_agent09_subgraph()
    agent10 = Agent10_decision_graph()
    agent12 = Agent12_report_graph()
    main_graph = StateGraph(Dict[str, Any])

    # 添加节点
    main_graph.add_node("agent01", agent01)
    main_graph.add_node("agent02", agent02)
    main_graph.add_node("agent05", agent05)
    main_graph.add_node("agent06", agent06)
    main_graph.add_node("agent09", agent09)
    main_graph.add_node("agent10", agent10)
    main_graph.add_node("agent12", agent12)

    # 添加边
    main_graph.add_edge(START, "agent01")
    main_graph.add_edge("agent01", "agent02")
    main_graph.add_edge("agent02", "agent05")
    main_graph.add_edge("agent05", "agent06")
    main_graph.add_edge("agent06", "agent09")
    main_graph.add_edge("agent09", "agent10")
    main_graph.add_edge("agent10", "agent12")
    main_graph.add_edge("agent06", END)
    # 编译图
    agentapp = main_graph.compile()
    return agentapp


if __name__ == "__main__":
    os.system('clear')
    myTruncateAll()
    t1 = time.time()

    # 正常流程示例
    # data = '{"deviceId": 500225200000001,"cameraHlsUrl": "http://127.0.0.1:5000","eventId": 247718427094028288,"eventTriggerTimestamp": "2025-11-11 14:26:35","targetLongitude": 34.9963,"targetLatitude": 34.9963,"entaddr": "重庆市沙坪坝区大学城路"}'
    #50010600001310075271：29.613021	106.326955
    # 50010616001320002358：29.610185958401001	106.32643369489
    # 50010616001320002359：29.610191322818999	106.32643369489
    # 50010616001310014549：29.610095000000001	106.32547700000001
    input_state = {
        'input_data': {"deviceId": "50010600001310075271", "event_id": 247718427094028288,
                       "targetLongitude": 106.326955, "targetLatitude": 29.613021,
                       "monitorName": "城兴路摄像头", "areaName": "公园东路与城兴路交叉口","detectpicUrl":"http://183.69.133.116:19500/algorithm_service/anon/file/download/1089596396354473984","pictureUrl":"http://183.69.133.116:19500/algorithm_service/anon/file/download/1089596397914755072",
                       "eventName": "测试", "eventResource": "测试来源",
                       "eventlevel": "一级事件", "eventStatus": "完成", "eventTime": "2025-11-11 14:26:35",
                       "analyseStartTime": "2025-11-11 14:26:35",
                       "analyseEndTime": "2025-11-11 14:26:35",
                       "comment": "备注",
                      'detectResult': [{'code': 3007, 'name': '挖掘机', 'num': 3, 'conf': 0.8},
                                       {'code': 3001, 'name': '卡车', 'num': 3, 'conf': 0.8},
                                       {'code': 1001, 'name': '施工围挡', 'num': 1, 'conf': 0.8}]
    },
        'agent02': {
            'agent02_id': 248625524463767552,
            'secondary_cameraIds': ['500225200000007', '500225200000009', '500225200000012', '500225200000013',
                                    '500225200000015', '500225200000016', '500225200000019'],
            'scanned_cameras_deviceId': ['500225200000001', '500225200000002', '500225200000003', '500225200000004',
                                         '500225200000005', '500225200000006', '500225200000007', '500225200000011',
                                         '500225200000008', '500225200000009', '500225200000010', '500225200000012',
                                         '500225200000014', '500225200000013', '500225200000015', '500225200000017',
                                         '500225200000018', '500225200000020', '500225200000016', '500225200000019',
                                         '500225200000023', '500225200000021'],
            'multil_iterations': 2,
            'extend_iterations': 2,
            "agent02StartTime": "2025-11-11 14:26:35",
            "agent02EndTime": "2025-11-11 14:29:35",
            'scanned_cameras_results':
                {'500225200000002': {'labelList': ['围挡', '挖掘机'], 'labelConfidence': [0.91, 0.65],
                                     'labelNum': [2, 1],
                                     'targetLongitude': 1003, 'targetLatitude': 996,
                                     'monitorName': '城兴路摄像头1', 'areaName': '公园东路与城兴路交叉口1',
                                     'pictureUrl': 'http://219.153.117.208:8090/500225200000024'},
                 '500225200000003': {'labelList': ['围挡', '工人'], 'labelConfidence': [0.99, 0.85], 'labelNum': [2, 2],
                                     'targetLongitude': 1110, 'targetLatitude': 1056,
                                     'monitorName': '城兴路摄像头2', 'areaName': '公园东路与城兴路交叉口2',
                                     'pictureUrl': 'http://219.153.117.208:8090/500225200000097'},
                 '500225200000004': {'labelList': ['围挡', '起重机'], 'labelConfidence': [0.94, 0.66],
                                     'labelNum': [2, 1],
                                     'targetLongitude': 1037, 'targetLatitude': 1124,
                                     'monitorName': '城兴路摄像头3', 'areaName': '公园东路与城兴路交叉口3',
                                     'pictureUrl': 'http://219.153.117.208:8090/500225200000041'},
                 '500225200000005': {'labelList': ['围挡', '货车'], 'labelConfidence': [0.89, 0.76], 'labelNum': [2, 3],
                                     'targetLongitude': 937, 'targetLatitude': 1118,
                                     'monitorName': '城兴路摄像头4', 'areaName': '公园东路与城兴路交叉口4',
                                     'pictureUrl': 'http://219.153.117.208:8090/500225200000001'}}},
        'agent05': {
            'node01': {'node_id': 249715105921634305,
                       'videoInfo': {'starttime': '2025-11-11 14:26:35', 'endtime': '2025-11-11 14:29:35',
                                     'space': '以公园东路与城兴路交叉口（1000, 1000）为中心，周边728米范围为空间范围',
                                     'labels': {'围挡': 8, '挖掘机': 1, '工人': 2, '起重机': 1, '货车': 3},
                                     'confidence': 0.83125, 'max_distance': 728, 'timecost': 180},
                       'networkInfo': None,
                       'permitInfo': None},
            'node02': {'node_id': 249715105921634306},
            'node03': {'node_id': 249715105921634307},
            'node04': {'node_id': 249715105921634308},
            'event_id': 247718427094028288, 'agent_id': 249715105921634304, 'agentName': '数据理解',
            'processContent': None, 'processTime': datetime.datetime(2025, 11, 20, 1, 58, 40, 734355),
            'resultContect': None, 'resultTime': None, 'summary': '数据理解概述', 'comment': '数据理解备注'
        },
        'agent09': {
            'risklevel': '极高'
        }
    }

    input_state = {
        'input_data': {"deviceId": "50010600001310075271", "eventId": 247718427094028218,
                       "targetLongitude": 106.326955, "targetLatitude": 29.613021,
                       "monitorName": "城兴路摄像头", "areaName": "公园东路与城兴路交叉口","detectpicUrl":"http://183.69.133.116:19500/algorithm_service/anon/file/download/1089596396354473984","pictureUrl":"http://183.69.133.116:19500/algorithm_service/anon/file/download/1089596397914755072",
                       "eventName": "测试", "eventResource": "测试来源",
                       "eventlevel": "一级事件", "eventStatus": "完成", "eventTime": "2025-11-11 14:26:35",
                       "analyseStartTime": "2025-11-11 14:26:35",
                       "analyseEndTime": "2025-11-11 14:26:35",
                       "comment": "备注",
                       'detectResult': [{'code': 3007, 'name': '挖掘机', 'num': 3, 'conf': 0.8},
                                        {'code': 3001, 'name': '卡车', 'num': 3, 'conf': 0.8},
                                        {'code': 1001, 'name': '施工围挡', 'num': 1, 'conf': 0.8}]
                       }
    }

    db = SessionLocal()
    input_state["input_data"]["db"] = db
    mainapp = create_maingraph()
    result = mainapp.invoke(input_state)
    t2 = time.time()
    print(f"time cost: {t2 - t1}")
    print("\n\nFinally flow result:")
    # print(result)

    for k, v in result.items():
        print(k)
        print("  %s" % str(v)[:20])
        print("-----------------\n")