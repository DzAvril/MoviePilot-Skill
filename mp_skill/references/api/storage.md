## storage

- `GET /api/v1/storage/auth_url/{name}` — 获取 OAuth2 授权 URL
- `GET /api/v1/storage/check/{name}` — 二维码登录确认
- `GET /api/v1/storage/qrcode/{name}` — 生成二维码内容
- `GET /api/v1/storage/reset/{name}` — 重置存储配置
- `GET /api/v1/storage/transtype/{name}` — 支持的整理方式获取
- `GET /api/v1/storage/usage/{name}` — 存储空间信息
- `POST /api/v1/storage/delete` — 删除文件或目录
- `POST /api/v1/storage/download` — 下载文件
- `POST /api/v1/storage/image` — 预览图片
- `POST /api/v1/storage/list` — 所有目录和文件
- `POST /api/v1/storage/mkdir` — 创建目录
- `POST /api/v1/storage/rename` — 重命名文件或目录
- `POST /api/v1/storage/save/{name}` — 保存存储配置
