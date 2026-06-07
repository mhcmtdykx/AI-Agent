"""
Agent主程序入口
"""
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import Agent, Config
from agent.utils import load_env_file


def main():
    """主函数"""
    print("=" * 50)
    print("欢迎使用AI Agent聊天机器人!")
    print("=" * 50)

    # 加载.env文件
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_env_file(env_file)

    # 加载配置
    try:
        config = Config.from_env()
        config.validate()
    except ValueError as e:
        print(f"配置错误: {e}")
        print("\n请按照以下步骤配置:")
        print("1. 复制 .env.example 为 .env")
        print("2. 在 .env 文件中填入你的API密钥")
        sys.exit(1)

    # 创建Agent
    agent = Agent(config=config)

    print(f"\nAgent已初始化: {agent}")
    print("输入 'quit' 或 'exit' 退出")
    print("输入 'clear' 清除对话历史")
    print("输入 'tools' 查看可用工具")
    print("-" * 50)

    while True:
        try:
            # 获取用户输入
            user_input = input("\n你: ").strip()

            # 检查退出命令
            if user_input.lower() in ["quit", "exit"]:
                print("\n再见！")
                break

            # 检查清除命令
            if user_input.lower() == "clear":
                agent.clear_memory()
                print("对话历史已清除")
                continue

            # 检查工具列表命令
            if user_input.lower() == "tools":
                print("\n可用工具:")
                from agent.tools import TOOLS_REGISTRY
                for name, tool_info in TOOLS_REGISTRY.items():
                    print(f"  - {name}: {tool_info['description']}")
                continue

            # 检查空输入
            if not user_input:
                continue

            # 与Agent对话
            print("\nAI: ", end="")
            response = agent.chat(user_input)
            print(response)

        except KeyboardInterrupt:
            print("\n\n程序被中断。再见！")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")


if __name__ == "__main__":
    main()
