"""快速验证 agent 多轮澄清逻辑（不需要启动服务）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import agent

sid = "test_session_1"

print("=" * 40)
q1 = "我想转专业，能不能转？"
print("Q1:", q1)
print("A1:", agent.run(sid, q1))

print("=" * 40)
q2 = "大三，3.1，土木工程"
print("Q2:", q2)
print("A2:", agent.run(sid, q2))

print("=" * 40)
q3 = "3.1"
print("Q3:", q3)
print("A3:", agent.run(sid, q3))

print("=" * 40)
print("槽位状态残留检查:", agent._sessions.get(sid))