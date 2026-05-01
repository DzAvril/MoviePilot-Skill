## system

- `GET /api/v1/system/env` — 查询系统配置
- `POST /api/v1/system/env` — 更新系统配置
- `GET /api/v1/system/global/user` — 查询用户相关系统设置
- `GET /api/v1/system/llm-models` — 获取LLM模型列表
- `POST /api/v1/system/llm-test` — 测试LLM调用
- `GET /api/v1/system/modulelist` — 查询已加载的模块ID列表
- `GET /api/v1/system/moduletest/{moduleid}` — 模块可用性测试
- `GET /api/v1/system/nettest` — 测试网络连通性
- `GET /api/v1/system/nettest/targets` — 获取网络测试目标
- `GET /api/v1/system/restart` — 重启系统
- `GET /api/v1/system/ruletest` — 过滤规则测试
- `GET /api/v1/system/runscheduler` — 运行服务
- `GET /api/v1/system/setting/{key}` — 查询系统设置
- `POST /api/v1/system/setting/{key}` — 更新系统设置
- `GET /api/v1/system/versions` — 查询Github所有Release版本
