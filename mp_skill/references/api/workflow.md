## workflow

- `GET /api/v1/workflow/` — 所有工作流
- `POST /api/v1/workflow/` — 创建工作流
- `GET /api/v1/workflow/actions` — 所有动作
- `GET /api/v1/workflow/event_types` — 获取所有事件类型
- `POST /api/v1/workflow/fork` — 复用工作流
- `GET /api/v1/workflow/plugin/actions` — 查询插件动作
- `POST /api/v1/workflow/share` — 分享工作流
- `DELETE /api/v1/workflow/share/{share_id}` — 删除分享
- `GET /api/v1/workflow/shares` — 查询分享的工作流
- `DELETE /api/v1/workflow/{workflow_id}` — 删除工作流
- `GET /api/v1/workflow/{workflow_id}` — 工作流详情
- `PUT /api/v1/workflow/{workflow_id}` — 更新工作流
- `POST /api/v1/workflow/{workflow_id}/pause` — 停用工作流
- `POST /api/v1/workflow/{workflow_id}/reset` — 重置工作流
- `POST /api/v1/workflow/{workflow_id}/run` — 执行工作流
- `POST /api/v1/workflow/{workflow_id}/start` — 启用工作流
