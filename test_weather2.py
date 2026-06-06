from agent.skills import reload_skills, get_skill_registry

reload_skills()
registry = get_skill_registry()

print("已加载技能:", [s['name'] for s in registry.list_skills()])
print("\n测试天气查询:")
result = registry.execute('weather', city='北京')
print(result)
